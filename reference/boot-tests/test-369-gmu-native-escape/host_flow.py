#!/usr/bin/env python3
"""Test369: independent corrected GMU/native-Escape boot. No sensor/PD experiment."""
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
from uuid import UUID

sys.dont_write_bytecode = True
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

# Reuse recovery transport/parser primitives only, not the old runner profile.
h = load('gmu369_recovery_primitives', R.parent/'test-292-passive-observation/host_flow.py')
parts = load('gmu369_partition_parser', R.parent/'test-323-pc-source-budget/host_flow.py')
ready = load('gmu369_ssh_admission', ROOT/'userspace/sensors/ssh_readiness.py')
recovery = load('gmu369_modules_recovery', R/'recovery.py')
PLAN = json.loads((R/'registration.json').read_text())
PACKAGE = json.loads((R/'PACKAGE.json').read_text())
LOCAL = Path('/mnt/d/android/gts9-active/gts9-test369')
STAGE = 'D:/android/gts9-active/gts9-test369'
TMP = '/tmp/gts9-test369'
CAPTURE = 'python3 -c '+shlex.quote((R/'capture.py').read_text())
GMU_TIMEOUT = r'platform 3d6a000\.gmu: \[drm:a6xx_hfi_wait_for_msg_interrupt\] \*ERROR\* Message HFI_H2F_MSG_GX_BW_PERF_VOTE id ([0-9]+) timed out waiting for response'
GMU_RESPONSE = r'platform 3d6a000\.gmu: \[drm:a6xx_hfi_send_msg\] \*ERROR\* Unexpected message id ([0-9]+) on the response queue'
BASELINE_JOURNAL = R.parent/'test-368-usb-cable-reconnect/preflight-1791516049850962717/before-kernel.jsonl'

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
        (phase == 'candidate' and not allow_desktop and any(d['services'][n] == 'active' for n in ('gdm', 'gts9-pen', 'gts9-palm'))) or
        '[sink]' not in d['roles']['power_role'] or '[device]' not in d['roles']['data_role'] or
        not re.search(r'\busb0\s+inet\s+169\.254\.42\.1/', d['network'])):
        raise ValueError('rescue/data role/text gate')
    if d['host_key'].split()[:2] != PLAN['host_ed25519_key'].split():
        raise ValueError('accepted SSH key mismatch')
    if len(d['adsp']) != 1 or d['adsp'][0]['state'] != 'offline':
        raise ValueError('unexpected ADSP activation in GPU-only scope')
    return boot

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

def verify_stage():
    rows = read(R/'staged-files.json')
    if set(x.name for x in LOCAL.iterdir()) != set(rows):
        raise ValueError('stage file set')
    for n, m in rows.items():
        x = LOCAL/n
        if x.is_symlink() or not x.is_file() or x.stat().st_size != m['bytes'] or sha(x) != m['sha256']:
            raise ValueError('stage drift: '+n)
    return rows

def wifi(rec,name,d):
    trust=Path(PLAN['known_hosts'])
    if trust.is_symlink() or trust.read_text()!=PLAN['alias']+' '+PLAN['host_ed25519_key']+'\n':raise ValueError('SSH trust changed')
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',d['network'])
    if len(addresses)!=1:raise ValueError('WiFi address not unique')
    phase='candidate' if d['config_sha256']==PLAN['candidate_config_sha256'] else 'baseline'
    counters=dict(device=0,probe=0)
    def check(remaining):
        counters['device']+=1
        raw,_=rec.adb(name+'-device-%02d'%counters['device'],CAPTURE,timeout=min(8,remaining))
        packet=json.loads(raw);identity(packet,phase,d['boot_id'].replace('-',''), allow_desktop=d['services']['gdm']=='active')
        return packet['boot_id']
    def probe(remaining):
        counters['probe']+=1;n=name+'-probe-%02d'%counters['probe']
        argv=ssh_argv(PLAN['key'],trust,PLAN['alias'],addresses[0],'cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id',transport=PLAN['ssh_transport'],windows_python=PLAN['windows_python'])
        # Distinguish Windows process startup from the former fragile3s deadline.
        argv=[x.replace('ConnectTimeout=3','ConnectTimeout=5') for x in argv]
        raw,status=rec.command(n,argv,timeout=min(12,remaining),required=False)
        return dict(stdout=raw,stderr=(rec.folder/(n+'.stderr')).read_text(),status=status)
    try:
        result=ready.admit(probe,check,machine_id=PLAN['machine_id'],boot_id=d['boot_id'],seconds=PLAN['ssh_readiness_seconds'],max_attempts=PLAN['ssh_max_attempts'])
    except ready.ReadinessError as exc:
        write(rec.folder/(name+'-admission.json'),exc.summary);raise
    write(rec.folder/(name+'-admission.json'),result)
    return addresses[0]

def snapshot(rec, name, phase, expected=None, *, allow_desktop=False):
    raw, _ = rec.adb(name, CAPTURE, timeout=15)
    d = json.loads(raw)
    identity(d, phase, expected, allow_desktop=allow_desktop)
    return d

def modules(rec, name, candidate, recovery=False):
    manifest = R/('candidate-modules.sha256' if candidate else 'rollback-modules.sha256')
    folder = ('/mnt/debian' if recovery else '')+'/usr/lib/modules/'+PLAN['release']
    links = ('test "$(find . -type l | wc -l)" = 1; test -L build; test "$(readlink build)" = '
             + shlex.quote(PACKAGE['candidate_build_link']) if candidate else
             'test "$(find . -type l | wc -l)" = 0')
    script = ('set -e; cd '+folder+'; test "$(find . -type f | wc -l)" = 181; '+links
              + '; printf %s '+shlex.quote(manifest.read_text())+' | sha256sum -c -')
    rec.adb(name, script, timeout=25)

def transfer(rec):
    rows = verify_stage()
    rec.host_adb('push-package', '-s', p.SERIAL, 'push', STAGE, '/tmp/', timeout=60)
    expected = ''.join(m['sha256']+'  '+TMP+'/'+n+'\n' for n, m in rows.items())
    rec.adb('verify-package', 'printf %s '+shlex.quote(expected)+' | sha256sum -c -', timeout=30)
    rec.adb('mount-root', 'set -e; if grep -q " /mnt/debian " /proc/mounts; then test "$(cat /mnt/debian/etc/machine-id)" = '+PLAN['machine_id']+'; else sh '+TMP+'/mount-debian.sh; fi', timeout=15)

def write_partition(rec, name, source, current, desired):
    if name != 'boot' or not re.fullmatch('[0-9a-f]{64}', current) or not re.fullmatch('[0-9a-f]{64}', desired):
        raise ValueError('unregistered partition write')
    if source not in (name+'.img', 'rollback-'+name+'.img') or PACKAGE['artifacts'][source]['sha256'] != desired:
        raise ValueError('unregistered partition source')
    device = '/dev/block/by-name/'+name
    command = f'set -e; test "$(blockdev --getsize64 {device})" = 100663296; test "$(sha256sum {device} | cut -d " " -f1)" = {current}; test "$(sha256sum {TMP}/{source} | cut -d " " -f1)" = {desired}; dd if={TMP}/{source} of={device} bs=4M; sync; test "$(sha256sum {device} | cut -d " " -f1)" = {desired}'
    rec.adb('write-'+name, command, timeout=30)

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

def mapping(rec, mode, boot):
    # Recovery /tmp does not survive normal boot: transfer only these tiny
    # frozen scripts/data and verify every byte before a settings mutation.
    boot=str(UUID(boot))
    rows=verify_stage(); names=('select-driver.py','evdev','gts9')
    incoming='/tmp/gts9-test369-keyboard-'+mode
    rec.adb('keyboard-dir-'+mode,'mkdir '+incoming,timeout=5)
    for n in names: rec.host_adb('keyboard-push-'+mode+'-'+n, '-s',p.SERIAL,'push',STAGE+'/'+n,incoming+'/'+n,timeout=8)
    expected=''.join(rows[n]['sha256']+'  '+incoming+'/'+n+'\n' for n in names)
    rec.adb('keyboard-hashes-'+mode, 'printf %s '+shlex.quote(expected)+' | sha256sum -c -', timeout=8)
    raw,_=rec.adb('keyboard-mapping-'+mode, 'python3 '+incoming+'/select-driver.py '+mode+' --boot-id '+boot+' --evidence /var/lib/gts9-test369/keyboard-'+mode, timeout=15)
    result=json.loads(raw);write(rec.folder/('keyboard-'+mode+'.json'),result)
    return result


def kernel_rows(raw, boot):
    rows = [json.loads(line) for line in raw.splitlines()]
    if not rows:
        raise ValueError('empty kernel evidence')
    cursors = set()
    for row in rows:
        if (row.get('_BOOT_ID') != UUID(boot).hex or row.get('_TRANSPORT') != 'kernel'
                or not isinstance(row.get('MESSAGE'), str) or not row.get('__CURSOR')
                or row['__CURSOR'] in cursors or not str(row.get('PRIORITY', '')).isdigit()
                or not 0 <= int(row['PRIORITY']) <= 7
                or int(row['__MONOTONIC_TIMESTAMP']) < 0):
            raise ValueError('kernel attribution/metadata')
        cursors.add(row['__CURSOR'])
    return rows


def baseline_errors(raw, boot):
    """Preserve the failed old boot; admit only bounded matching known HFI pairs."""
    rows = kernel_rows(raw, boot)
    original = kernel_rows(BASELINE_JOURNAL.read_text(), boot)
    indexed = {row['__CURSOR']: row for row in rows}
    if any(indexed.get(row['__CURSOR']) != row for row in original):
        raise ValueError('old Test368 evidence missing/changed')
    # Check the full boot for CPU failures as well as accounting for every error.
    cpu = r'(?i)(soft lockup|softlockup:.*CPU|rcu.*(?:stall|non-responsive)|CSD.*(?:stall|non-responsive|timeout)|Kernel panic|\bOops:|\bBUG:|Internal error|\bSError\b|blocked for more than|workqueue lockup|hung task|CPU.*non-responsive)'
    if any(re.search(cpu, row['MESSAGE']) for row in rows):
        raise ValueError('CPU/kernel failure in corrective baseline')
    old_cursors = {row['__CURSOR'] for row in original}
    added = [row for row in rows if row['__CURSOR'] not in old_cursors and int(row['PRIORITY']) <= 3]
    if len(added) % 2 or len(added) > 2*PLAN['baseline_GPU_max_new_pairs']:
        raise ValueError('incomplete/unbounded additional GMU pairs')
    pairs = []
    for i in range(0, len(added), 2):
        timeout, response = added[i:i+2]
        first = re.fullmatch(GMU_TIMEOUT, timeout['MESSAGE'])
        second = re.fullmatch(GMU_RESPONSE, response['MESSAGE'])
        elapsed = int(response['__MONOTONIC_TIMESTAMP'])-int(timeout['__MONOTONIC_TIMESTAMP'])
        if not first or not second or first.group(1) != second.group(1) or not 0 <= elapsed <= 100000:
            raise ValueError('unknown additional baseline error; stop')
        pairs.append(dict(id=int(first.group(1)), timeout_cursor=timeout['__CURSOR'],
                          response_cursor=response['__CURSOR'], response_delay_us=elapsed))
    return dict(verdict='FAULTED_OLD_BOOT_PRESERVED_FOR_CORRECTIVE_TEST',
                old_error_count=sum(int(row['PRIORITY']) <= 3 for row in original),
                additional_GMU_pairs=pairs, clean=False)


def scan(rec, boot, uptime):
    raw, _ = rec.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15)
    rows = kernel_rows(raw, boot)
    # Never inherit old HFI diagnostics as an accepted candidate warning.
    if any(re.fullmatch(GMU_TIMEOUT, row['MESSAGE']) or re.fullmatch(GMU_RESPONSE, row['MESSAGE'])
           for row in rows):
        raise ValueError('GPU HFI error in new boot; stop')
    old = (R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
    known = {json.loads(line)['MESSAGE'] for line in old.splitlines()
             if int(json.loads(line).get('PRIORITY', 7)) <= 3}
    result = h.g.evidence.inspect_journal(raw, UUID(boot).hex, known, require_start=True,
        accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
        accepted_qca_cycles=True, observed_uptime=uptime)
    bounded = {n for group in h.g.startup_triplets(rows, True) for n in group['rows']}
    write(rec.folder/'journal-classification.json', result)
    if result['fault_counts'] or any(item['row'] not in bounded for item in result['suspects']):
        raise ValueError('new kernel fault/suspect; no retry')
    return result


def stage():
    verify_inputs()
    LOCAL.mkdir(parents=True, exist_ok=False)
    sources = {name: ROOT/meta['path'] for name, meta in PACKAGE['artifacts'].items()}
    for name in ('mount-debian.sh', 'module-swap.sh', 'candidate-modules.sha256',
                 'rollback-modules.sha256', 'desktop.py', 'desktop-manifest.json', 'recovery.py'):
        sources[name] = R/name
    sources['select-driver.py'] = ROOT/'reference/desktop-bringup/gmu-hfi-transport/select-driver.py'
    for name in ('evdev', 'gts9'):
        sources[name] = ROOT/'userspace/gnome/keyboard'/name
    for row in read(R/'desktop-manifest.json').values():
        sources[row['incoming']] = ROOT/row['source']
    rows = {}
    for name, source in sources.items():
        shutil.copyfile(source, LOCAL/name)
        rows[name] = dict(bytes=source.stat().st_size, sha256=sha(source))
    write(R/'staged-files.json', rows)
    return dict(verdict='HOST_STAGED_NOT_DEPLOYED', files=len(rows))


def preflight():
    verify_inputs(True); verify_stage()
    if (R/'first-failure.json').exists() or (R/'mutation-state.json').exists():
        raise ValueError('closed/started test; no repeat preflight')
    rec = p.Recorder(R/('preflight-'+str(time.time_ns()))); p.SERIAL='gts9wifi-0001'
    d = snapshot(rec, 'current-state', 'baseline', PLAN['before_boot_id'])
    if d['failed_units']:
        raise ValueError('baseline failed unit')
    address = wifi(rec, 'wifi', d)
    raw, _ = rec.adb('partitions', parts.DEBIAN_PARTS, timeout=25)
    parts.require_debian_partitions(raw, PACKAGE['baseline_partitions'])
    modules(rec, 'modules', False)
    checks=[]
    for name,row in read(R/'desktop-manifest.json').items():
        path='/'+name
        if row['original_sha256']:
            checks.append('test ! -L '+shlex.quote(path)+'; test "$(sha256sum '+shlex.quote(path)+' | cut -d " " -f1)" = '+row['original_sha256'])
        else:
            checks.append('test ! -e '+shlex.quote(path)+'; test ! -L '+shlex.quote(path))
    rec.adb('original-overlay','set -e; '+'; '.join(checks),timeout=10)
    kernel, _ = rec.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15)
    write(rec.folder/'baseline-errors.json', baseline_errors(kernel, d['boot_id']))
    boots, _ = rec.adb('boots', 'journalctl --list-boots --no-pager', timeout=10)
    if h.g.evidence.boot_list(boots)[-1] != UUID(d['boot_id']).hex:
        raise ValueError('boot history incomplete')
    windows, _ = rec.ps('windows-usb', p.PS_USB, timeout=20)
    if p.has_code43(windows) or not re.search(r'ProblemCode\s*:\s*0\b', windows):
        raise ValueError('Windows USB gate')
    result = dict(verdict='READY_FOR_ONE_CORRECTIVE_BOOT', boot_id=d['boot_id'],
                  snapshot=d, wifi=address, epoch=time.time(), folder=rec.folder.name)
    write(rec.folder/'summary.json', result); write(R/'active-preflight.json', result)
    return result


def accept(rec, phase, before, boots_before):
    wait_debian(rec)
    d = snapshot(rec, 'current-state', phase, allow_desktop=phase=='baseline')
    boot = UUID(d['boot_id']).hex
    boots, _ = rec.adb('boots-after', 'journalctl --list-boots --no-pager', timeout=10)
    if h.g.evidence.attribute(UUID(before).hex, boot, boots_before, boots) != 'attributed':
        raise ValueError('extra/missing boot attribution')
    wifi(rec, 'wifi', d)
    raw, _ = rec.adb('partitions', parts.DEBIAN_PARTS, timeout=25)
    parts.require_debian_partitions(raw, PACKAGE[phase+'_partitions'])
    modules(rec, 'modules', phase=='candidate')
    initial = read(R/'active-preflight.json')['snapshot']
    if d['failed_units'] != initial['failed_units']:
        raise ValueError('new failed unit')
    if phase=='candidate':
        state = read(R/'mutation-state.json'); state['boot_id']=d['boot_id']; write(R/'mutation-state.json', state)
    started=time.monotonic(); current=d; i=0
    while time.monotonic()-started < PLAN['observation_seconds']:
        time.sleep(5)
        current=snapshot(rec, 'health-%02d'%i, phase, boot, allow_desktop=phase=='baseline'); i+=1
        if current['failed_units'] != initial['failed_units']:
            raise ValueError('new failed unit during observation')
    faults=scan(rec, boot, current['uptime'])
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows):raise ValueError('Windows Code43')
    result=dict(verdict='CORRECTED_KERNEL_TEXT_ADMISSION_PASS' if phase=='candidate' else 'EXACT331_RESTORED',
        boot_id=boot, attributed=True, observation_seconds=time.monotonic()-started,
        snapshot=current,kernel_fault_counts=faults['fault_counts'],PPS=False,pump_ON=False,
        physical_input_verified=False,USB_reconnect_verified=False,sensors_verified=False)
    write(rec.folder/'summary.json',result); return result


def restore(from_recovery=False):
    state=read(R/'mutation-state.json')
    if not state['rollback_required']:raise ValueError('already restored; no repeat reboot')
    rec=p.Recorder(R/('rollback-'+str(time.time_ns()))); before=boots=None
    if not from_recovery:
        p.SERIAL='gts9wifi-0001'
        before,_=rec.adb('before-boot','cat /proc/sys/kernel/random/boot_id',timeout=5)
        boots,_=rec.adb('boots-before','journalctl --list-boots --no-pager',timeout=10)
        h.enter_recovery(rec)
    else:
        p.SERIAL='R52X10045LT'
        raw,_=rec.adb('twrp-identity','getprop ro.product.device; uname -a; id',timeout=10)
        if 'gts9wifi' not in raw or 'uid=0' not in raw or '7.2.0-rc3' in raw:raise ValueError('recovery identity')
    transfer(rec)
    raw,_=rec.adb('partitions-before',h.PARTS,timeout=25); current=restore_layout(raw)
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    rec.adb('restore-modules',recovery.command('/mnt/debian',PLAN['release'],PLAN['namespace'],
        TMP+'/rollback-modules.sha256',TMP+'/candidate-modules.sha256',PLAN['machine_id']),timeout=30)
    desktop_overlay(rec,'restore'); modules(rec,'restored-modules',False,True)
    if state.get('boot_id'):
        rec.adb('offline-failed-kernel','chroot /mnt/debian /usr/bin/journalctl --directory=/var/log/journal -k _BOOT_ID='+UUID(state['boot_id']).hex+' -o json --no-pager',timeout=20,required=False)
    if current['boot']!=PACKAGE['baseline_partitions']['boot']:
        write_partition(rec,'boot','rollback-boot.img',current['boot'],PACKAGE['baseline_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=25); h.require_partitions(raw,PACKAGE['baseline_partitions'])
    h.clear_unmount(rec)
    write(R/'mutation-state.json',dict(rollback_required=False,phase='exact331-restored-offline'))
    if before is None:
        result=dict(verdict='RESTORED331_TWRP_MANUAL_ENDPOINT',attribution_gap=True)
        write(rec.folder/'summary.json',result); return result
    rec.host_adb('normal-restored-reboot','-s',p.SERIAL,'reboot',timeout=10)
    result=accept(rec,'baseline',before.strip(),boots)
    mapping(rec,'interim',result['boot_id'])
    rec.adb('restored-graphical','set -e; test "$(systemctl get-default)" = graphical.target; systemctl is-active gdm gts9-palm',timeout=10)
    return result


def stop(exc):
    if not (R/'first-failure.json').exists():
        write(R/'first-failure.json',dict(verdict='STOP',error=str(exc),no_retry=True))
    if (R/'mutation-state.json').exists() and read(R/'mutation-state.json')['rollback_required']:
        try:restore(p.SERIAL=='R52X10045LT')
        except Exception as cleanup:
            write(R/'recovery-required.json',dict(error=str(cleanup),manual_TWRP_required=True,no_blind_retry=True))


def install():
    verify_inputs(True); verify_stage()
    if (R/'mutation-state.json').exists() or (R/'first-failure.json').exists():
        raise ValueError('one candidate only; no replay')
    pre=read(R/'active-preflight.json')
    if pre['verdict']!='READY_FOR_ONE_CORRECTIVE_BOOT' or not 0<=time.time()-pre['epoch']<=PLAN['preflight_max_age_seconds']:
        raise ValueError('fresh preflight required')
    rec=p.Recorder(R/'installation'); p.SERIAL='gts9wifi-0001'
    snapshot(rec,'live-boundary','baseline',pre['boot_id'])
    write(R/'mutation-state.json',dict(rollback_required=True,phase='before-recovery'))
    h.enter_recovery(rec); transfer(rec)
    raw,_=rec.adb('partitions-before',h.PARTS,timeout=25); h.require_partitions(raw,PACKAGE['baseline_partitions'])
    modules(rec,'original-modules',False,True)
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    desktop_overlay(rec,'install')
    rec.adb('install-modules',f'sh {TMP}/module-swap.sh /mnt/debian install {TMP}/candidate-modules.sha256 {TMP}/modules-x710.tar.gz {TMP}/rollback-modules.sha256',timeout=30)
    write_partition(rec,'boot','boot.img',PACKAGE['baseline_partitions']['boot'],PACKAGE['candidate_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=25); h.require_partitions(raw,PACKAGE['candidate_partitions'])
    h.clear_unmount(rec)
    write(R/'mutation-state.json',dict(rollback_required=True,phase='installed-awaiting-one-boot'))
    rec.host_adb('ordinary-candidate-boot','-s',p.SERIAL,'reboot',timeout=10)
    result=accept(p.Recorder(R/'candidate-admission'),'candidate',pre['boot_id'],(R/pre['folder']/'boots.txt').read_text())
    write(R/'mutation-state.json',dict(rollback_required=True,phase='candidate-kept-text',boot_id=result['boot_id']))
    return result


def desktop():
    verify_inputs(True); verify_stage()
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-kept-text' or (R/'desktop-acceptance').exists() or (R/'first-failure.json').exists():
        raise ValueError('one desktop admission only')
    rec=p.Recorder(R/'desktop-acceptance'); p.SERIAL='gts9wifi-0001'; boot=state['boot_id']
    snapshot(rec,'before-desktop','candidate',boot)
    mapping(rec,'native',boot)
    rec.adb('desktop-start','set -e; test -f /var/lib/gts9-test369/text-scope; rm /var/lib/gts9-test369/text-scope; systemctl daemon-reload; systemctl start gdm; systemctl is-active gdm gts9-palm',timeout=20)
    raw,_=rec.adb('native-input-state','set -e; cat /proc/sys/kernel/random/boot_id; test -d /sys/module/wacom_wez01; test -d /sys/module/fts1ba90a; cat /proc/bus/input/devices; systemctl get-default',timeout=10)
    if UUID(raw.splitlines()[0])!=UUID(boot):raise ValueError('desktop reboot')
    started=time.monotonic(); i=0
    while time.monotonic()-started<PLAN['desktop_observation_seconds']:
        current=snapshot(rec,'desktop-health-%02d'%i,'candidate',boot,allow_desktop=True); i+=1
        desktop_health(current)
        time.sleep(10)
    faults=scan(rec,boot,current['uptime']); wifi(rec,'desktop-wifi',current)
    state.update(phase='GNOME-awaiting-physical-input-confirmation'); write(R/'mutation-state.json',state)
    result=dict(verdict='BOUNDED_GNOME_NO_NEW_KERNEL_FAULT',boot_id=boot,
        observation_seconds=time.monotonic()-started,physical_input_verified=False,
        kernel_fault_counts=faults['fault_counts'],USB_reconnect_verified=False,sensors_verified=False)
    write(rec.folder/'summary.json',result);return result


def desktop_health(current):
    # The enabled palm-pair loader loads both native modules. The superseded
    # standalone pen unit is normally inactive; do not enable it or fail it.
    if (current['failed_units'] or any(current['services'][n]!='active' for n in ('gdm','gts9-palm'))
            or current['services']['gts9-pen']=='failed'):
        raise ValueError('desktop unit failure')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('verify','stage','preflight','install','desktop','restore','restore-recovery'))
    mode=parser.parse_args().mode
    try:
        if mode=='verify': result=verify_inputs()
        elif mode=='stage': result=stage()
        elif mode=='preflight': result=preflight()
        elif mode=='install': result=install()
        elif mode=='desktop': result=desktop()
        else: result=restore(mode=='restore-recovery')
    except Exception as exc:
        if mode in ('preflight','install','desktop'):stop(exc)
        raise
    print(json.dumps(result,indent=2))
