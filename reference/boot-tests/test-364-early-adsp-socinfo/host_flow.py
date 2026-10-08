#!/usr/bin/env python3
"""Test364: one registered early ADSP/native SoC boot, ordinary charging only.

Import/stage/verify are host-only. preflight is read-only. install requires exact
pushed inputs and a fresh authenticated preflight. Any first unknown/fault stops.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts'))
import production_reboot_stability as p
from windows_ssh_transport import ssh_argv


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


h = load('early364_recovery', R.parent/'test-292-passive-observation/host_flow.py')
parts = load('early364_partitions', R.parent/'test-323-pc-source-budget/host_flow.py')
mapper = load('early364_socinfo', ROOT/'userspace/sensors/map-socinfo.py')
PLAN = json.loads((R/'registration.json').read_text())
PACKAGE = json.loads((R/'PACKAGE.json').read_text())
LOCAL = Path('/mnt/d/android/gts9-active/gts9-test364')
STAGE = 'D:/android/gts9-active/gts9-test364'
TMP = '/tmp/gts9-test364'
CAPTURE = 'python3 -c '+shlex.quote((R/'capture.py').read_text())


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def identity(d, phase, expected=None):
    boot = d['boot_id'].replace('-', '')
    if not re.fullmatch('[0-9a-f]{32}', boot) or (expected and boot != expected):
        raise ValueError('boot identity')
    if (d['machine_id'] != PLAN['machine_id'] or PLAN['release'] not in d['uname'] or
        d['config_sha256'] != PLAN[phase+'_config_sha256'] or d['notes_sha256'] != PLAN[phase+'_notes_sha256'] or
        d['cmdline'] != PLAN['runtime_cmdline'] or not d['dcc_absent']):
        raise ValueError('kernel/ordinary config identity')
    if d['direct_default'] not in ('N', '0'):
        raise ValueError('direct charging unexpectedly enabled')
    b = d['battery']
    if (b['POWER_SUPPLY_HEALTH'] != 'Good' or b['POWER_SUPPLY_PRESENT'] != '1' or
        b['POWER_SUPPLY_VOLTAGE_MAX_DESIGN'] != '4440000' or
        not PLAN['flash_soc_min'] <= int(b['POWER_SUPPLY_CAPACITY']) <= PLAN['flash_soc_max'] or
        not PLAN['pack_temp_min_decic'] <= int(b['POWER_SUPPLY_TEMP']) < PLAN['pack_temp_max_decic'] or
        not 3400000 <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) < 4440000):
        raise ValueError('battery safety gate')
    if (any(d['services'][n] != 'active' for n in ('ssh', 'gts9-adbd', 'gts9-usb-acm')) or
        any(d['services'][n] == 'active' for n in ('gdm', 'gts9-pen', 'gts9-palm')) or
        '[sink]' not in d['roles']['power_role'] or '[device]' not in d['roles']['data_role'] or
        not re.search(r'\busb0\s+inet\s+169\.254\.42\.1/', d['network'])):
        raise ValueError('rescue/data role/text gate')
    if d['host_key'].split()[:2] != PLAN['host_ed25519_key'].split():
        raise ValueError('accepted SSH key mismatch')
    return boot


def native_gate(d):
    if d['native_socinfo'].get('boot_id') != d['boot_id']:
        raise ValueError('stale native SoC snapshot')
    if len(d['adsp']) != 1 or d['adsp'][0]['state'] != 'running' or d['adsp'][0]['firmware'] != 'qcom/sm8550/adsp.mdt':
        raise ValueError('ADSP not uniquely running with accepted firmware')
    return mapper.translate(d['native_socinfo'])


def restore_layout(raw):
    observed = h.partitions(raw)
    if set(observed) != set(PACKAGE['baseline_partitions']):
        raise ValueError('incomplete recovery partition evidence')
    for name, value in observed.items():
        if value not in (PACKAGE['baseline_partitions'][name], PACKAGE['candidate_partitions'][name]):
            raise ValueError('unknown partition; do not overwrite '+name)
    return observed


def verify_inputs(pushed=False):
    for name, expected in read(R/'INPUTS.json').items():
        if sha(ROOT/name) != expected:
            raise ValueError('registered input drift: '+name)
    for name, meta in PACKAGE['artifacts'].items():
        path = ROOT/meta['path']
        if path.is_symlink() or path.stat().st_size != meta['bytes'] or sha(path) != meta['sha256']:
            raise ValueError('candidate/rollback artifact drift: '+name)
    if pushed:
        git = lambda *a: subprocess.check_output(['git', '-C', str(ROOT), *a], text=True).strip()
        if git('branch', '--show-current') != 'test' or git('rev-parse', 'HEAD') != git('rev-parse', 'origin/test'):
            raise ValueError('registration must be pushed to origin/test')
        controlled = list(read(R/'INPUTS.json'))+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status', '--porcelain', '--', *controlled):
            raise ValueError('uncommitted controlled input')
        subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', *controlled], check=True, stdout=subprocess.DEVNULL)


def stage():
    verify_inputs()
    LOCAL.mkdir(parents=True, exist_ok=False)
    names = ('boot.img', 'vendor_boot.img', 'modules-x710.tar.gz', 'rollback-boot.img', 'rollback-vendor_boot.img', 'sensor-assets.tar.gz')
    sources = {n:ROOT/PACKAGE['artifacts'][n]['path'] for n in names}
    for n in ('mount-debian.sh', 'module-swap.sh', 'candidate-modules.sha256', 'rollback-modules.sha256', 'assets.py', 'asset-manifest.json'):
        sources[n] = R/n
    rows = {}
    for n, source in sources.items():
        shutil.copyfile(source, LOCAL/n)
        rows[n] = dict(bytes=source.stat().st_size, sha256=sha(source))
    write(R/'staged-files.json', rows)
    return dict(verdict='HOST_STAGED_NOT_DEPLOYED', files=len(rows))


def verify_stage():
    rows = read(R/'staged-files.json')
    if set(x.name for x in LOCAL.iterdir()) != set(rows):
        raise ValueError('stage file set')
    for n, m in rows.items():
        x = LOCAL/n
        if x.is_symlink() or not x.is_file() or x.stat().st_size != m['bytes'] or sha(x) != m['sha256']:
            raise ValueError('stage drift: '+n)
    return rows


def wifi(rec, name, d):
    trust = Path(PLAN['known_hosts'])
    if trust.is_symlink() or trust.read_text() != PLAN['alias']+' '+PLAN['host_ed25519_key']+'\n':
        raise ValueError('SSH trust changed')
    addresses = re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/', d['network'])
    if len(addresses) != 1:
        raise ValueError('WiFi address not unique')
    argv = ssh_argv(PLAN['key'], trust, PLAN['alias'], addresses[0], 'cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id',
                    transport=PLAN['ssh_transport'], windows_python=PLAN['windows_python'])
    raw, _ = rec.command(name, argv, timeout=15)
    if raw.splitlines() != [PLAN['machine_id'], d['boot_id']]:
        raise ValueError('authenticated WiFi identity')
    return addresses[0]


def snapshot(rec, name, phase, expected=None):
    raw, _ = rec.adb(name, CAPTURE, timeout=15)
    d = json.loads(raw)
    identity(d, phase, expected)
    return d


def scan(rec, boot, uptime):
    raw, _ = rec.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15)
    old = (R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
    known = {json.loads(x)['MESSAGE'] for x in old.splitlines() if int(json.loads(x).get('PRIORITY', 7)) <= 3}
    d = h.g.evidence.inspect_journal(raw, boot, known, require_start=True, accepted_startup_variants=True,
          startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True, observed_uptime=uptime)
    bounded = {n for group in h.g.startup_triplets([json.loads(x) for x in raw.splitlines()], True) for n in group['rows']}
    write(rec.folder/'journal-classification.json', d)
    if d['fault_counts'] or any(x['row'] not in bounded for x in d['suspects']):
        raise ValueError('new kernel fault/suspect; no retry')
    return d


def modules(rec, name, candidate, recovery=False):
    manifest = R/('candidate-modules.sha256' if candidate else 'rollback-modules.sha256')
    folder = ('/mnt/debian' if recovery else '')+'/usr/lib/modules/'+PLAN['release']
    script = 'set -e; cd '+folder+'; test "$(find . -type f | wc -l)" = 181; printf %s '+shlex.quote(manifest.read_text())+' | sha256sum -c -'
    rec.adb(name, script, timeout=25)


def preflight():
    verify_inputs(); verify_stage()
    folder = R/('preflight-'+str(time.time_ns()))
    rec = p.Recorder(folder); p.SERIAL = 'gts9wifi-0001'
    d = snapshot(rec, 'current-state', 'baseline')
    boot = identity(d, 'baseline')
    address = wifi(rec, 'wifi', d)
    raw, _ = rec.adb('partitions', parts.DEBIAN_PARTS, timeout=25)
    parts.require_debian_partitions(raw, PACKAGE['baseline_partitions'])
    modules(rec, 'modules', False)
    scan(rec, boot, d['uptime'])
    boots, _ = rec.adb('boots', 'journalctl --list-boots --no-pager', timeout=10)
    if h.g.evidence.boot_list(boots)[-1] != boot:
        raise ValueError('journal history mismatch')
    windows, _ = rec.ps('windows-usb', p.PS_USB, timeout=20)
    if p.has_code43(windows) or not re.search(r'ProblemCode\s*:\s*0\b', windows):
        raise ValueError('Windows USB gate')
    result = dict(verdict='READY_FOR_ONE_CONTROLLED_BOOT', boot_id=boot, snapshot=d, wifi=address, epoch=time.time(), folder=folder.name)
    write(folder/'summary.json', result)
    write(R/'active-preflight.json', result)
    return result


def transfer(rec):
    rows = verify_stage()
    rec.host_adb('push-package', '-s', p.SERIAL, 'push', STAGE, '/tmp/', timeout=60)
    expected = ''.join(m['sha256']+'  '+TMP+'/'+n+'\n' for n, m in rows.items())
    rec.adb('verify-package', 'printf %s '+shlex.quote(expected)+' | sha256sum -c -', timeout=30)
    rec.adb('mount-root', 'set -e; if grep -q " /mnt/debian " /proc/mounts; then test "$(cat /mnt/debian/etc/machine-id)" = '+PLAN['machine_id']+'; else sh '+TMP+'/mount-debian.sh; fi', timeout=15)


def write_partition(rec, name, source, current, desired):
    if name not in ('boot', 'vendor_boot') or not re.fullmatch('[0-9a-f]{64}', current) or not re.fullmatch('[0-9a-f]{64}', desired):
        raise ValueError('unregistered partition write')
    if source not in (name+'.img', 'rollback-'+name+'.img') or PACKAGE['artifacts'][source]['sha256'] != desired:
        raise ValueError('unregistered partition source')
    device = '/dev/block/by-name/'+name
    command = f'set -e; test "$(blockdev --getsize64 {device})" = 100663296; test "$(sha256sum {device} | cut -d " " -f1)" = {current}; test "$(sha256sum {TMP}/{source} | cut -d " " -f1)" = {desired}; dd if={TMP}/{source} of={device} bs=4M; sync; test "$(sha256sum {device} | cut -d " " -f1)" = {desired}'
    rec.adb('write-'+name, command, timeout=30)


def assets(rec, mode):
    # TWRP has no Python: use Debian's exact interpreter offline, no systemd.
    root = '/mnt/debian'
    if mode == 'install':
        rec.adb('asset-tools', f'set -e; test ! -e {root}{TMP}; mkdir {root}{TMP}; cp {TMP}/assets.py {TMP}/asset-manifest.json {TMP}/sensor-assets.tar.gz {root}{TMP}/', timeout=20)
        args = f'install --archive {TMP}/sensor-assets.tar.gz --manifest {TMP}/asset-manifest.json --sha256 '+PACKAGE['artifacts']['sensor-assets.tar.gz']['sha256']
    elif mode == 'restore':
        # Code is hash-verified in recovery before running, including partial install.
        rec.adb('asset-restore-tool', f'set -e; mkdir -p {root}{TMP}; cp {TMP}/assets.py {root}{TMP}/assets.py', timeout=10)
        args = 'restore'
    else:
        raise ValueError('asset operation')
    rec.adb('assets-'+mode, f'chroot {root} /usr/bin/python3 {TMP}/assets.py '+args, timeout=30)
    rec.adb('remove-owned-tmp', f'set -e; rm -f {root}{TMP}/assets.py {root}{TMP}/asset-manifest.json {root}{TMP}/sensor-assets.tar.gz; rmdir {root}{TMP}', timeout=10)


def wait_debian(rec):
    p.SERIAL = 'gts9wifi-0001'
    start = time.monotonic(); i = 0
    while time.monotonic()-start < PLAN['readiness_max_seconds']:
        raw, status = rec.adb('readiness-%02d'%i, 'cat /proc/sys/kernel/random/boot_id; systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr', timeout=5, required=False)
        i += 1
        if status == 0 and raw.splitlines().count('active') == 3 and '169.254.42.1/' in raw and re.search(r'\bwlp1s0\s+inet\s+', raw):
            return
        time.sleep(2)
    raise TimeoutError('one candidate boot unavailable; no second reboot')


def accept(rec, phase, before, boots_before):
    wait_debian(rec)
    d = snapshot(rec, 'current-state', phase)
    boot = identity(d, phase)
    boots, _ = rec.adb('boots-after', 'journalctl --list-boots --no-pager', timeout=10)
    if h.g.evidence.attribute(before, boot, boots_before, boots) != 'attributed':
        raise ValueError('extra/missing boot attribution')
    wifi(rec, 'wifi', d)
    raw, _ = rec.adb('partitions', parts.DEBIAN_PARTS, timeout=25)
    parts.require_debian_partitions(raw, PACKAGE[phase+'_partitions'])
    modules(rec, 'modules', phase == 'candidate')
    initial = read(R/'active-preflight.json')['snapshot']
    if d['failed_units'] != initial['failed_units']:
        raise ValueError('new systemd failed unit')
    if phase == 'candidate':
        write(rec.folder/'native-mapping.json', native_gate(d))
    started = time.monotonic()
    while time.monotonic()-started < PLAN['observation_seconds']:
        time.sleep(5)
        current = snapshot(rec, 'health-'+str(time.time_ns()), phase, boot)
        if phase == 'candidate': native_gate(current)
        if current['failed_units'] != initial['failed_units']:
            raise ValueError('new failed unit during observation')
    faults = scan(rec, boot, current['uptime'])
    windows, _ = rec.ps('windows-usb', p.PS_USB, timeout=20)
    if p.has_code43(windows):
        raise ValueError('Windows Code43')
    result = dict(verdict='EARLY_ADSP_NATIVE_IDENTITY_PASS' if phase == 'candidate' else 'EXACT331_DEBIAN_RESTORED',
        boot_id=boot, attributed=True, observation_seconds=time.monotonic()-started,
        native_socinfo=d['native_socinfo'], adsp=d['adsp'], fastrpc=d['fastrpc'], snapshot=current,
        SSC_rotation_tested=False, PPS=False, pump_ON=False, kernel_fault_counts=faults['fault_counts'])
    write(rec.folder/'summary.json', result)
    return result


def restore(from_recovery=False):
    state = read(R/'mutation-state.json')
    if not state['rollback_required']:
        raise ValueError('already restored; no repeated reboot')
    rec = p.Recorder(R/('rollback-'+str(time.time_ns())))
    before = boots = None
    if not from_recovery:
        p.SERIAL = 'gts9wifi-0001'
        before, _ = rec.adb('before-boot', 'cat /proc/sys/kernel/random/boot_id', timeout=5)
        boots, _ = rec.adb('boots-before', 'journalctl --list-boots --no-pager', timeout=10)
        h.enter_recovery(rec)
    else:
        p.SERIAL = 'R52X10045LT'
        raw, _ = rec.adb('twrp-identity', 'getprop ro.product.device; uname -a; id', timeout=10)
        if 'gts9wifi' not in raw or 'uid=0' not in raw or '7.2.0-rc3' in raw:
            raise ValueError('recovery identity')
    transfer(rec)
    raw, _ = rec.adb('partitions-before', h.PARTS, timeout=25)
    current = restore_layout(raw)
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    saved, _ = rec.adb('saved-layout', 'if test -d /mnt/debian/usr/lib/modules/.gts9-test364-original; then echo saved; else echo original; fi', timeout=10)
    if saved.strip() == 'saved':
        rec.adb('restore-modules', f'sh {TMP}/module-swap.sh /mnt/debian restore {TMP}/rollback-modules.sha256', timeout=25)
    modules(rec, 'restored-modules', False, True)
    exists, _ = rec.adb('asset-ledger', 'if test -f /mnt/debian/var/lib/gts9-test364/assets.json; then echo present; else echo absent; fi', timeout=10)
    if exists.strip() == 'present': assets(rec, 'restore')
    elif exists.strip() != 'absent': raise ValueError('unknown asset ledger state')
    for name in ('boot', 'vendor_boot'):
        if current[name] != PACKAGE['baseline_partitions'][name]:
            write_partition(rec, name, 'rollback-'+name+'.img', current[name], PACKAGE['baseline_partitions'][name])
    raw, _ = rec.adb('partitions-after', h.PARTS, timeout=25)
    h.require_partitions(raw, PACKAGE['baseline_partitions'])
    h.clear_unmount(rec)
    write(R/'mutation-state.json', dict(rollback_required=False, phase='exact331-restored-offline'))
    # When failed candidate never became readable, preserve attribution gap;
    # do not assert a normal two-boot history or blind reboot without registration.
    if before is None:
        write(rec.folder/'summary.json', dict(verdict='RESTORED331_TWRP_MANUAL_ENDPOINT', attribution_gap=True))
        return
    rec.host_adb('normal-restored-reboot', '-s', p.SERIAL, 'reboot', timeout=10)
    return accept(rec, 'baseline', before.strip().replace('-', ''), boots)


def install():
    verify_inputs(True); verify_stage()
    if (R/'mutation-state.json').exists() or (R/'first-failure.json').exists():
        raise ValueError('one candidate only; no repeat')
    pre = read(R/'active-preflight.json')
    if pre['verdict'] != 'READY_FOR_ONE_CONTROLLED_BOOT' or not 0 <= time.time()-pre['epoch'] <= PLAN['preflight_max_age_seconds']:
        raise ValueError('fresh preflight required')
    rec = p.Recorder(R/'installation'); p.SERIAL = 'gts9wifi-0001'
    snapshot(rec, 'live-boundary', 'baseline', pre['boot_id'])
    write(R/'mutation-state.json', dict(rollback_required=True, phase='before-recovery'))
    try:
        h.enter_recovery(rec); transfer(rec)
        raw, _ = rec.adb('partitions-before', h.PARTS, timeout=25)
        h.require_partitions(raw, PACKAGE['baseline_partitions'])
        modules(rec, 'original-modules', False, True)
        rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
        assets(rec, 'install')
        rec.adb('install-modules', f'sh {TMP}/module-swap.sh /mnt/debian install {TMP}/candidate-modules.sha256 {TMP}/modules-x710.tar.gz {TMP}/rollback-modules.sha256', timeout=25)
        for name in ('boot', 'vendor_boot'):
            write_partition(rec, name, name+'.img', PACKAGE['baseline_partitions'][name], PACKAGE['candidate_partitions'][name])
        raw, _ = rec.adb('partitions-after', h.PARTS, timeout=25)
        h.require_partitions(raw, PACKAGE['candidate_partitions']); h.clear_unmount(rec)
        write(R/'mutation-state.json', dict(rollback_required=True, phase='installed-awaiting-one-boot'))
        rec.host_adb('ordinary-candidate-boot', '-s', p.SERIAL, 'reboot', timeout=10)
        result = accept(p.Recorder(R/'candidate-acceptance'), 'candidate', pre['boot_id'], (R/pre['folder']/'boots.txt').read_text())
        write(R/'mutation-state.json', dict(rollback_required=True, phase='accepted-candidate-kept-text', boot_id=result['boot_id']))
        return result
    except Exception as exc:
        write(R/'first-failure.json', dict(error=str(exc), stopped=True, no_retry=True))
        # Cleanup may run without waiting for any commit/push. If the failed boot
        # cannot answer, stop and request recovery; do not send another blind boot.
        try:
            restore(from_recovery=p.SERIAL == 'R52X10045LT')
        except Exception as cleanup:
            write(R/'recovery-required.json', dict(error=str(cleanup), manual_TWRP_required=True, no_blind_retry=True))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('verify', 'stage', 'preflight', 'install', 'restore', 'restore-recovery'))
    args = parser.parse_args()
    if args.mode == 'verify': result = verify_inputs()
    elif args.mode == 'stage': result = stage()
    elif args.mode == 'preflight': result = preflight()
    elif args.mode == 'install': result = install()
    else: result = restore(args.mode == 'restore-recovery')
    print(json.dumps(result, indent=2))
