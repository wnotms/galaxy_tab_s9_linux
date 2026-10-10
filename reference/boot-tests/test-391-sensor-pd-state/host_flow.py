#!/usr/bin/env python3
"""Test391: one registered early ADSP/native SoC boot, ordinary charging only.

Import/stage/verify are host-only. preflight is read-only. install requires exact
pushed inputs and a fresh authenticated preflight. Any first unknown/fault stops.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts'))
import production_reboot_stability as p


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


h = load('early372_recovery', R.parent/'test-292-passive-observation/host_flow.py')
parts = load('early372_partitions', R.parent/'test-323-pc-source-budget/host_flow.py')
mapper = load('early372_socinfo', ROOT/'userspace/sensors/map-socinfo.py')
recovery_admission = load('ssc390_recovery_admission', ROOT/'scripts/ssc-recovery-admission.py')
stat_evidence = load('ssc379_stat_evidence', ROOT/'userspace/sensors/rpc_stat_evidence.py')
return_evidence = load('ssc390_return_evidence', ROOT/'userspace/sensors/rpc_return_evidence.py')
missing_evidence = load('ssc390_missing_evidence', R/'missing_file_evidence.py')
PLAN = json.loads((R/'registration.json').read_text())
PACKAGE = json.loads((R/'PACKAGE.json').read_text())
LOCAL = Path('/mnt/d/android/gts9-active/gts9-test391')
STAGE = 'D:/android/gts9-active/gts9-test391'
TMP = '/tmp/gts9-test391'
CAPTURE = 'python3 -c '+shlex.quote((R/'capture.py').read_text())


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def identity(d, phase, expected=None, *, allow_desktop=False):
    boot = d['boot_id'].replace('-', '')
    if not re.fullmatch('[0-9a-f]{32}', boot) or (expected and boot != UUID(expected).hex):
        raise ValueError('boot identity')
    if (d['machine_id'] != PLAN['machine_id'] or PLAN['release'] not in d['uname'] or
        d['config_sha256'] != PLAN[phase+'_config_sha256'] or d['notes_sha256'] != PLAN[phase+'_notes_sha256'] or
        d['cmdline'] != PLAN['runtime_cmdline' if phase == 'candidate' else 'baseline_runtime_cmdline'] or not d['dcc_absent']):
        raise ValueError('kernel/ordinary config identity')
    if d['failed_units'] or d['usb_lifecycle'] != PLAN['usb_lifecycle']:
        raise ValueError('failed unit or permanent USB baseline changed')
    if d['direct_default'] not in ('N', '0'):
        raise ValueError('direct charging unexpectedly enabled')
    b = d['battery']
    if (b['POWER_SUPPLY_HEALTH'] != 'Good' or b['POWER_SUPPLY_PRESENT'] != '1' or
        b['POWER_SUPPLY_VOLTAGE_MAX_DESIGN'] != '4440000' or
        not PLAN['flash_soc_min'] <= int(b['POWER_SUPPLY_CAPACITY']) <= PLAN['flash_soc_max'] or
        not PLAN['pack_temp_min_decic'] <= int(b['POWER_SUPPLY_TEMP']) < PLAN['pack_temp_max_decic'] or
        not PLAN['voltage_observation_min_uv'] <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) <= PLAN['voltage_observation_max_uv']):
        raise ValueError('battery safety gate')
    if (any(d['services'][n] != 'active' for n in ('ssh', 'gts9-adbd', 'gts9-usb-acm')) or
        (phase == 'candidate' and not allow_desktop and any(d['services'][n] == 'active' for n in ('gdm',))) or
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
    for name, row in read(R/'desktop-manifest.json').items():
        path=ROOT/row['source']
        if path.is_symlink() or not path.is_file() or sha(path)!=row['sha256']:
            raise ValueError('paired overlay artifact drift: '+name)
    if pushed:
        git = lambda *a: subprocess.check_output(['git', '-C', str(ROOT), *a], text=True).strip()
        if git('branch', '--show-current') != 'test' or git('rev-parse', 'HEAD') != git('rev-parse', 'origin/test'):
            raise ValueError('registration must be pushed to origin/test')
        controlled = list(read(R/'INPUTS.json'))+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status', '--porcelain', '--', *controlled):
            raise ValueError('uncommitted controlled input')
        subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', *controlled], check=True, stdout=subprocess.DEVNULL)
    return dict(verdict='HOST_INPUTS_EXACT_NOT_DEPLOYED',kernel_rebuilt=False,write_partitions=PACKAGE['write_partitions'])


def _stage_kernel():
    verify_inputs()
    LOCAL.mkdir(parents=True, exist_ok=False)
    names = ('vendor_boot.img', 'rollback-vendor_boot.img', 'sensor-assets.tar.gz')
    sources = {n:ROOT/PACKAGE['artifacts'][n]['path'] for n in names}
    for n in ('mount-debian.sh', 'candidate-modules.sha256', 'rollback-modules.sha256', 'assets.py', 'asset-manifest.json'):
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


def transport_admit(rec, name, d, phase='candidate'):
    if PLAN['control_transport'] != 'adb':
        raise ValueError('unregistered control transport')
    identity(d, phase, d['boot_id'])
    raw, _ = rec.host_adb(name+'-state', '-s', p.SERIAL, 'get-state', timeout=5)
    if raw.strip() != 'device':
        raise ValueError('ADB device transport unavailable')
    raw, _ = rec.adb(name+'-identity',
        'cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; id -u; cat /proc/sys/kernel/random/boot_id', timeout=8)
    if raw.replace('\r', '').splitlines() != [PLAN['machine_id'], d['boot_id'], '0', d['boot_id']]:
        raise ValueError('ADB root shell/boot identity mismatch')
    result = dict(verdict='ADB_ROOT_SAME_BOOT_READY', control_transport='adb',
                  boot_id=d['boot_id'], ADB=True, root_shell=True,
                  authenticated_WiFi=None, SSH_tested=False, host_NCM_tested=False,
                  device_NCM_present=True,
                  wifi_ipv4=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/', d['network']))
    write(rec.folder/(name+'-admission.json'), result)
    return result



def snapshot(rec, name, phase, expected=None, *, allow_desktop=False):
    raw, _ = rec.adb(name, CAPTURE, timeout=15)
    d = json.loads(raw)
    if phase == 'candidate':
        UUID(d['boot_id'])
        if (R/'mutation-state.json').exists():
            state=read(R/'mutation-state.json')
            if not state.get('boot_id') and (expected is None or UUID(expected)==UUID(d['boot_id'])):
                state['boot_id']=d['boot_id'];write(R/'mutation-state.json',state)
    identity(d, phase, expected, allow_desktop=allow_desktop)
    return d


def scan(rec, boot, uptime):
    raw, _ = rec.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15)
    if re.search(r'Message HFI_H2F_MSG_GX_BW_PERF_VOTE id [0-9]+ timed out|Unexpected message id [0-9]+ on the response queue',raw):
        raise ValueError('GMU HFI regression; no historical waiver')
    old = (R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
    known = {json.loads(x)['MESSAGE'] for x in old.splitlines() if int(json.loads(x).get('PRIORITY', 7)) <= 3}
    d = h.g.evidence.inspect_journal(raw, boot, known, require_start=True, accepted_startup_variants=True,
          startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True, observed_uptime=uptime)
    bounded = {n for group in h.g.startup_triplets([json.loads(x) for x in raw.splitlines()], True) for n in group['rows']}
    write(rec.folder/'journal-classification.json', d)
    if d['fault_counts'] or any(x['row'] not in bounded for x in d['suspects']):
        raise ValueError('new kernel fault/suspect; no retry')
    return d


def native_mapper(rec, boot):
    raw,_=rec.adb('native-mapper', 'python3 '+TMP+'/native-mapper-snapshot.py --boot-id '+boot, timeout=5)
    data=json.loads(raw)
    if UUID(data['boot_id'])!=UUID(boot) or data['binding_state']!='bound':
        raise ValueError('native auxiliary mapper not bound')
    write(rec.folder/'native-mapper.json',data)
    return data



def servreg(rec, boot, inventory):
    endpoints=[r for r in inventory['services'] if r['service']==64 and r['instance']==257]
    if len(endpoints)!=1:
        raise ValueError('native Servreg endpoint not unique; no RPC launch')
    if UUID(inventory['boot_id'])!=UUID(boot) or not inventory['complete']:
        raise ValueError('native Servreg inventory not boot-bound/complete')
    node,port=endpoints[0]['node'],endpoints[0]['port']
    script='python3 -c '+shlex.quote('from pathlib import Path; Path('+repr(TMP+'/qrtr-inventory.json')+').write_text('+repr(json.dumps(inventory))+')')
    rec.adb('servreg-inventory',script,timeout=5)
    raw,_=rec.adb('servreg-domains','python3 '+TMP+'/servreg-domain-snapshot.py --boot-id '+boot+' --inventory '+TMP+'/qrtr-inventory.json --node '+str(node)+' --port '+str(port)+' --layout linux-7.2 --seconds '+str(PLAN['servreg_query_seconds']),timeout=5)
    result=json.loads(raw);write(rec.folder/'servreg-domains.json',result)
    if UUID(result['boot_id'])!=UUID(boot) or not result['complete'] or not result['sensor_domain_present']:
        raise ValueError('native mapper did not answer complete X710 sensor domain')
    return result

def preflight_scan(rec, d):
    raw,_=rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
    guard=load('ssc372_usb_guard',R.parent/'test-371-usb-lifecycle-gmu/host_flow.py')
    plan,_=guard.load()
    registration=PLAN['baseline_observation']
    prior=ROOT/registration['path']
    if sha(prior)!=registration['sha256']:
        raise ValueError('enrolled baseline evidence changed')
    rows=guard.journal(raw,d['boot_id']);original=guard.journal(prior.read_text(),d['boot_id'])
    guard.health(rows,original,plan['existing_errors'])
    write(rec.folder/'journal-classification.json',dict(verdict='SAME_BOOT_ACCEPTED_BASELINE_DELTA_PASS',baseline=registration['path'],boot_id=d['boot_id'],future_error_waiver=False))


def modules(rec, name, candidate, recovery=False):
    manifest = R/('candidate-modules.sha256' if candidate else 'rollback-modules.sha256')
    folder = ('/mnt/debian' if recovery else '')+'/usr/lib/modules/'+PLAN['release']
    links = 'test "$(find . -type l | wc -l)" = 1; test -L build; test "$(readlink build)" = '+shlex.quote(PACKAGE['candidate_build_link'])
    script = 'set -e; cd '+folder+'; test "$(find . -type f | wc -l)" = 181; '+links+'; printf %s '+shlex.quote(manifest.read_text())+' | sha256sum -c -'
    rec.adb(name, script, timeout=25)


def preflight():
    verify_inputs(); verify_stage()
    folder = R/('preflight-'+str(time.time_ns()))
    rec = p.Recorder(folder); p.SERIAL = 'gts9wifi-0001'
    d = snapshot(rec, 'current-state', 'baseline')
    boot = identity(d, 'baseline', PLAN['before_boot_id'])
    admission = transport_admit(rec, 'transport', d, phase='baseline')
    raw, _ = rec.adb('partitions', parts.DEBIAN_PARTS, timeout=25)
    parts.require_debian_partitions(raw, PACKAGE['baseline_partitions'])
    modules(rec, 'modules', False)
    preflight_scan(rec, d)
    boots, _ = rec.adb('boots', PLAN['boot_history_command'], timeout=10)
    if h.g.evidence.boot_list(boots)[-1] != boot:
        raise ValueError('journal history mismatch')
    windows, _ = rec.ps('windows-usb', p.PS_USB, timeout=20)
    if p.has_code43(windows) or not re.search(r'ProblemCode\s*:\s*0\b', windows):
        raise ValueError('Windows USB gate')
    result = dict(verdict='READY_FOR_ONE_CONTROLLED_BOOT', boot_id=boot, snapshot=d, transport=admission, epoch=time.time(), folder=folder.name)
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
    if name != 'vendor_boot' or not re.fullmatch('[0-9a-f]{64}', current) or not re.fullmatch('[0-9a-f]{64}', desired):
        raise ValueError('unregistered partition write')
    if name not in PACKAGE['write_partitions'] or source not in (name+'.img', 'rollback-'+name+'.img') or PACKAGE['artifacts'][source]['sha256'] != desired:
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
        if status == 0 and raw.splitlines().count('active') == 3 and '169.254.42.1/' in raw:
            return
        time.sleep(2)
    raise TimeoutError('one candidate boot unavailable; no second reboot')


def accept(rec, phase, before, boots_before):
    wait_debian(rec)
    if phase == 'candidate':
        raw,_ = rec.adb('observer-state-before-admission', 'python3 /usr/local/lib/gts9-test391/glink_trace.py state --boot-id $(cat /proc/sys/kernel/random/boot_id)', timeout=8, required=False)
    d = snapshot(rec, 'current-state', phase)
    boot = identity(d, phase)
    boots, _ = rec.adb('boots-after', PLAN['boot_history_command'], timeout=10)
    if h.g.evidence.attribute(before, boot, boots_before, boots) != 'attributed':
        raise ValueError('extra/missing boot attribution')
    transport_admit(rec, 'transport', d, phase=phase)
    raw, _ = rec.adb('partitions', parts.DEBIAN_PARTS, timeout=25)
    parts.require_debian_partitions(raw, PACKAGE[phase+'_partitions'])
    modules(rec, 'modules', phase == 'candidate')
    initial = read(R/'active-preflight.json')['snapshot']
    if d['failed_units'] != initial['failed_units']:
        raise ValueError('new systemd failed unit')
    if phase == 'candidate':
        write(rec.folder/'native-mapping.json', native_gate(d))
        state = read(R/'mutation-state.json')
        state['boot_id'] = d['boot_id']
        write(R/'mutation-state.json', state)
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
    result = dict(verdict='EARLY_ADSP_NATIVE_IDENTITY_PASS' if phase == 'candidate' else 'EXACT370_DEBIAN_RESTORED',
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
        boots, _ = rec.adb('boots-before', PLAN['boot_history_command'], timeout=10)
        rec.adb('stop-owned-runtime', 'set -e; test "$(cat /etc/machine-id)" = '+PLAN['machine_id']+'; rm -f /run/gts9-ssc-test/ready; systemctl stop iio-sensor-proxy hexagonrpcd-adsp-sensorspd hexagonrpcd-adsp-rootpd gts9-glink-test391.service', timeout=20)
        h.enter_recovery(rec)
    else:
        p.SERIAL = 'R52X10045LT'
        raw, _ = rec.adb('twrp-identity', 'getprop ro.product.device; uname -a; id', timeout=10)
        if 'gts9wifi' not in raw or 'uid=0' not in raw or '7.2.0-rc3' in raw:
            raise ValueError('recovery identity')
    recovery_admission.admit(rec)
    transfer(rec)
    raw, _ = rec.adb('partitions-before', h.PARTS, timeout=25)
    current = restore_layout(raw)
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    desktop_overlay(rec, 'restore')
    modules(rec, 'restored-modules', False, True)
    exists, _ = rec.adb('asset-ledger', 'if test -f /mnt/debian/var/lib/gts9-test391/assets.json; then echo present; else echo absent; fi', timeout=10)
    if exists.strip() == 'present': assets(rec, 'restore')
    elif exists.strip() != 'absent': raise ValueError('unknown asset ledger state')
    target_boot = state.get('boot_id')
    if target_boot:
        target_boot = UUID(target_boot).hex
        for name, selection in (('kernel', '_TRANSPORT=kernel'), ('runtime', '-u hexagonrpcd-adsp-rootpd -u hexagonrpcd-adsp-sensorspd -u gts9-glink-test391.service')):
            _, status = rec.adb('offline-target-'+name, 'chroot /mnt/debian /usr/bin/journalctl --directory=/var/log/journal '+selection+' _BOOT_ID='+target_boot+' -o json --no-pager', timeout=20, required=False)
            if status: write(rec.folder/('offline-'+name+'-collection-failed.json'),dict(status=status,baseline_recovery_still_required=True))
    for name in ('vendor_boot',):
        if current[name] != PACKAGE['baseline_partitions'][name]:
            write_partition(rec, name, 'rollback-'+name+'.img', current[name], PACKAGE['baseline_partitions'][name])
    raw, _ = rec.adb('partitions-after', h.PARTS, timeout=25)
    h.require_partitions(raw, PACKAGE['baseline_partitions'])
    h.clear_unmount(rec)
    write(R/'mutation-state.json', dict(rollback_required=False, phase='exact370-restored-offline'))
    # When failed candidate never became readable, preserve attribution gap;
    # do not assert a normal two-boot history or blind reboot without registration.
    if before is None:
        write(rec.folder/'summary.json', dict(verdict='RESTORED370_TWRP_MANUAL_ENDPOINT', attribution_gap=True))
        return
    rec.host_adb('normal-restored-reboot', '-s', p.SERIAL, 'reboot', timeout=10)
    result = accept(rec, 'baseline', before.strip().replace('-', ''), boots)
    rec.adb('graphical-restored', 'set -e; test "$(systemctl get-default)" = graphical.target; systemctl is-active gdm gts9-palm', timeout=10)
    return result


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
        h.enter_recovery(rec); recovery_admission.admit(rec); transfer(rec)
        raw, _ = rec.adb('partitions-before', h.PARTS, timeout=25)
        h.require_partitions(raw, PACKAGE['baseline_partitions'])
        modules(rec, 'original-modules', False, True)
        rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
        assets(rec, 'install')
        desktop_overlay(rec, 'install')
        for name in ('vendor_boot',):
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
        recovery_admission.capture_fault(rec)
        # Cleanup may run without waiting for any commit/push. If the failed boot
        # cannot answer, stop and request recovery; do not send another blind boot.
        try:
            restore(from_recovery=p.SERIAL == 'R52X10045LT')
        except Exception as cleanup:
            write(R/'recovery-required.json', dict(error=str(cleanup), manual_TWRP_required=True, no_blind_retry=True))
        raise


def stage():
    result=_stage_kernel()
    sources={n:R/n for n in ('runtime.py','runtime-packages.json','runtime-overrides.json','capture.py','desktop.py','desktop-manifest.json')}
    for n in ('map-socinfo.py','qrtr-native-snapshot.py','native-mapper-snapshot.py','servreg-domain-snapshot.py','servreg-state-snapshot.py','ssc_lifecycle.py'):
        sources[n]=ROOT/'userspace/sensors'/n
    for row in read(R/'desktop-manifest.json').values(): sources[row['incoming']]=ROOT/row['source']
    for row in read(R/'runtime-packages.json'): sources[row['filename']]=ROOT/row['path']
    rows=read(R/'staged-files.json')
    for n,source in sources.items():
        shutil.copyfile(source,LOCAL/n);rows[n]=dict(bytes=source.stat().st_size,sha256=sha(source))
    write(R/'staged-files.json',rows)
    return dict(result,files=len(rows))


def sample(raw):
    rows=re.findall(r'Accelerometer sensor measurement: X=([^\s]+) Y=([^\s]+) Z=([^\s]+) m/s²',raw)
    if not rows:return None
    values=tuple(float(x) for x in rows[-1])
    if not all(math.isfinite(x) for x in values) or not 1<=math.sqrt(sum(x*x for x in values))<=40:
        raise ValueError('invalid accelerometer measurement')
    return dict(x=values[0],y=values[1],z=values[2],unit='m/s²')


def runtime(rec,mode,boot):
    name='runtime-'+mode
    if mode=='prepare':
        plan=dict(PLAN,boot_id=boot)
        rec.adb('live-runtime-plan','python3 -c '+shlex.quote('from pathlib import Path; p=Path('+repr(TMP+'/live-plan.json')+'); p.write_text('+repr(json.dumps(plan))+')'),timeout=8)
    command='python3 '+TMP+'/runtime.py '+mode+' --incoming '+TMP+' --plan '+TMP+'/live-plan.json'
    raw,_=rec.adb(name,command,timeout=70 if mode=='prepare' else 20)
    value=json.loads(raw);write(rec.folder/(name+'.json'),value);return value


def collect_runtime(rec, prefix='', *, require_metadata=False):
    raw,_ = rec.adb(prefix+'unit-journal','journalctl -b -u hexagonrpcd-adsp-rootpd -u hexagonrpcd-adsp-sensorspd -u iio-sensor-proxy -o json --no-pager',timeout=15)
    if len(raw.encode()) > PLAN['unit_journal_max_bytes']:
        raise ValueError('bounded unit journal size exceeded')
    try:
        metadata=stat_evidence.inspect(raw, read(R/'mutation-state.json')['boot_id'], read(R/'registry-metadata.json'))
        write(rec.folder/(prefix+'rpc-stat-metadata.json'),metadata)
        if require_metadata and not metadata['complete']:
            raise ValueError('config RPC stat metadata incomplete or changed')
    except Exception as exc:
        write(rec.folder/(prefix+'rpc-stat-metadata-error.json'),dict(error=str(exc),complete=False))
        raise
    try:
        returned=return_evidence.inspect(raw, read(R/'mutation-state.json')['boot_id'])
        write(rec.folder/(prefix+'rpc-return-frames.json'), returned)
        contents=return_evidence.registry_contents(returned, read(R/'asset-manifest.json'))
        write(rec.folder/(prefix+'rpc-return-content.json'), contents)
        if require_metadata and (not returned['complete'] or not contents['complete']):
            raise ValueError('bounded RPC return framing/content incomplete or mismatched')
        if require_metadata:
            write(rec.folder/(prefix+'missing-file-status.json'), missing_evidence.inspect(returned))
    except Exception as exc:
        write(rec.folder/(prefix+'rpc-return-error.json'),dict(error=str(exc),complete=False))
        raise
    rec.adb(prefix+'unit-state','systemctl status --no-pager -l hexagonrpcd-adsp-rootpd hexagonrpcd-adsp-sensorspd iio-sensor-proxy; ls -l /dev/fastrpc*; ls -l /sys/bus/auxiliary/drivers/qcom_pd_mapper.qcom-pdm-mapper; ls -la /usr/share/qcom/sm8550/Samsung/gts9wifi/socinfo /usr/share/qcom/sm8550/Samsung/gts9wifi/sensors',timeout=12,required=False)


def notifier(rec, name, boot, inventory, domains):
    # Fresh current-boot inventories only; two independent private clients max.
    payload = {'inventory': inventory, 'domains': domains}
    code = 'from pathlib import Path; import json; d=json.loads('+repr(json.dumps(payload))+'); '
    code += 'Path('+repr(TMP+'/notifier-inventory.json')+').write_text(json.dumps(d["inventory"])); '
    code += 'Path('+repr(TMP+'/notifier-domains.json')+').write_text(json.dumps(d["domains"]))'
    rec.adb(name+'-inputs', 'python3 -c '+shlex.quote(code), timeout=5)
    raw, status = rec.adb(name, 'python3 '+TMP+'/servreg-state-snapshot.py --boot-id '+boot+
        ' --inventory '+TMP+'/notifier-inventory.json --domains '+TMP+'/notifier-domains.json --seconds '+str(PLAN['notifier_query_seconds']), timeout=5, required=False)
    result=json.loads(raw);write(rec.folder/(name+'.json'),result)
    if status or UUID(result['boot_id'])!=UUID(boot) or not result['complete'] or result['domain_state']=='LOCATOR_ERROR':
        raise ValueError('notifier state unknown/failure; no subscribe/retry')
    if result['enable']!=0 or result['listener_registered'] or result['DSP_started']:
        raise ValueError('unexpected notifier operation')
    return result


def discover():
    state=read(R/'mutation-state.json')
    if state['phase']!='accepted-candidate-kept-text' or (R/'runtime-discovery').exists():
        raise ValueError('one state observation only from accepted candidate')
    p.SERIAL='gts9wifi-0001';rec=p.Recorder(R/'runtime-discovery');boot=state['boot_id']
    try:
        d=snapshot(rec,'boundary','candidate',boot);native_gate(d);transport_admit(rec,'transport',d)
        rows=verify_stage()
        wanted=['runtime.py','capture.py','map-socinfo.py','qrtr-native-snapshot.py','native-mapper-snapshot.py','servreg-domain-snapshot.py','servreg-state-snapshot.py','ssc_lifecycle.py','runtime-packages.json','runtime-overrides.json']+[x['filename'] for x in read(R/'runtime-packages.json')]
        rec.adb('incoming-dir','mkdir '+TMP,timeout=8)
        for i,n in enumerate(wanted):rec.host_adb('push-%02d'%i,'-s',p.SERIAL,'push',STAGE+'/'+n,TMP+'/'+n,timeout=12)
        checks=''.join(rows[n]['sha256']+'  '+TMP+'/'+n+'\n' for n in wanted)
        rec.adb('incoming-hashes','printf %s '+shlex.quote(checks)+' | sha256sum -c -',timeout=8)
        if d['uptime']>PLAN['trace_boot_deadline_seconds']-PLAN['ssc_readiness_seconds']-30:
            raise ValueError('insufficient trace window; no runtime launch')
        trace_inventory(rec,'glink-before-rpc',boot)
        runtime(rec,'prepare',boot);native_mapper(rec,boot)
        before_inventory=qrtr(rec,'qrtr-before',boot)
        domains=servreg(rec,boot,before_inventory)
        before=notifier(rec,'sensor-pd-before',boot,before_inventory,domains)
        # Unknown initial state stops before any RPC launch.
        runtime(rec,'start',boot)
        started=time.monotonic();index=0
        while time.monotonic()-started<PLAN['ssc_readiness_seconds']:
            current=snapshot(rec,'ssc-health-%02d'%index,'candidate',boot);native_gate(current)
            if current['failed_units']:raise ValueError('new failed unit')
            raw,_=rec.adb('ssc-units-%02d'%index,'systemctl is-active hexagonrpcd-adsp-rootpd hexagonrpcd-adsp-sensorspd',timeout=5)
            if raw.splitlines()!=['active','active']:raise ValueError('RPC daemon failed; no retry')
            index+=1
            time.sleep(min(5,max(0,PLAN['ssc_readiness_seconds']-(time.monotonic()-started))))
        after_inventory=qrtr(rec,'qrtr-after',boot)
        after=notifier(rec,'sensor-pd-after',boot,after_inventory,domains)
        ssc_present=any(row['service']==400 for row in after_inventory['services'])
        measurement=None
        if ssc_present:
            raw,_=rec.adb('accelerometer','timeout 4 ssccli --sensor accelerometer --timeout 2',timeout=6,required=False)
            measurement=sample(raw)
        collect_runtime(rec,'discovery-',require_metadata=True);trace_collect(rec,boot)
        runtime(rec,'deactivate',boot)
        current=snapshot(rec,'final-identity','candidate',boot);native_gate(current);transport_admit(rec,'final-transport',current)
        faults=scan(rec,boot,current['uptime'])
        result=dict(verdict='SENSOR_PD_STATE_OBSERVED',boot_id=boot,
                    before_state=before['domain_state'],after_state=after['domain_state'],
                    SSC_service_present=ssc_present,accelerometer_sample=measurement,
                    sensor_acceptance=False,physical_rotation_tested=False,
                    observation_seconds=time.monotonic()-started,registered_query_window_seconds=PLAN['ssc_readiness_seconds'],
                    notifier_queries=2,enable=0,listener_registered=False,
                    ADB=True,device_NCM_present=True,control_transport='adb',
                    kernel_fault_counts=faults['fault_counts'],PPS=False,pump_ON=False)
        write(rec.folder/'summary.json',result)
    except Exception as exc:
        write(R/'first-runtime-failure.json',dict(error=str(exc),stopped=True,no_retry=True))
        try:trace_collect(rec,boot,'failure-glink')
        except Exception as e:write(rec.folder/'glink-collection-error.json',dict(error=str(e)))
        try:collect_runtime(rec,'failure-')
        except Exception as e:write(rec.folder/'runtime-collection-error.json',dict(error=str(e)))
        try:runtime(rec,'deactivate',boot)
        except Exception as e:write(rec.folder/'runtime-cleanup-error.json',dict(error=str(e)))
        try:restore()
        except Exception as e:write(R/'recovery-required.json',dict(error=str(e),manual_TWRP_required=True))
        raise
    # Always restore the normal desktop; a state observation is not sensor acceptance.
    restore()
    return result


def desktop_overlay(rec, mode):
    root='/mnt/debian'; rows=read(R/'desktop-manifest.json')
    scratch=TMP+'-desktop-'+mode
    names=['desktop.py','desktop-manifest.json'] + ([row['incoming'] for row in rows.values()] if mode=='install' else [])
    rec.adb('desktop-tools-'+mode, 'set -e; test ! -e '+root+scratch+'; mkdir '+root+scratch+'; cp '+' '.join(TMP+'/'+n for n in names)+' '+root+scratch+'/', timeout=15)
    args=mode+' --incoming '+scratch+' --manifest '+scratch+'/desktop-manifest.json'
    failed=False
    try:
        rec.adb('desktop-overlay-'+mode, 'chroot '+root+' /usr/bin/python3 '+scratch+'/desktop.py '+args, timeout=20)
    except Exception:
        failed=True
        raise
    finally:
        _,status=rec.adb('desktop-tools-remove-'+mode, 'set -e; rm -f '+' '.join(root+scratch+'/'+n for n in names)+'; rmdir '+root+scratch, timeout=10,required=False)
        if status and not failed: raise ValueError('desktop scratch cleanup incomplete')


def qrtr(rec, name, boot):
    raw,_=rec.adb(name, 'python3 '+TMP+'/qrtr-native-snapshot.py --boot-id '+boot+' --seconds '+str(PLAN['qrtr_lookup_seconds']), timeout=5)
    data=json.loads(raw)
    if UUID(data['boot_id'])!=UUID(boot) or not data['complete']: raise ValueError('incomplete QRTR service inventory')
    write(rec.folder/(name+'.json'), data)
    return data


def trace_inventory(rec, name, boot):
    raw,_=rec.adb(name,'python3 /usr/local/lib/gts9-test391/glink_trace.py inventory --boot-id '+boot,timeout=8)
    value=json.loads(raw)
    if UUID(value['boot_id'])!=UUID(boot):raise ValueError('GLINK inventory boot mismatch')
    write(rec.folder/(name+'.json'),value)
    return value


def trace_collect(rec, boot, name='glink-complete'):
    raw,_=rec.adb(name,'python3 /usr/local/lib/gts9-test391/glink_trace.py collect --boot-id '+boot,timeout=15)
    value=json.loads(raw)
    if UUID(value['boot_id'])!=UUID(boot) or not value['trace_stopped'] or not value['complete'] or len(raw.encode())>PLAN['trace_max_bytes']:
        raise ValueError('GLINK trace collection identity/size')
    write(rec.folder/(name+'.json'),value)
    (rec.folder/(name+'.trace')).write_text(value['trace'])
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('verify','stage','preflight','install','discover','restore','restore-recovery','run'))
    mode=parser.parse_args().mode
    if mode=='verify': result=verify_inputs()
    elif mode=='stage': result=stage()
    elif mode=='preflight': result=preflight()
    elif mode=='install': result=install()
    elif mode=='discover': result=discover()
    elif mode=='run':
        if (R/'mutation-state.json').exists(): raise ValueError('one attempt only')
        preflight(); install(); result=discover()
    else: result=restore(mode=='restore-recovery')
    print(json.dumps(result,indent=2))
