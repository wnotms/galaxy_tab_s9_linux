#!/usr/bin/env python3
"""One registered OFF-mode condition comparison, followed by accepted299 restore.

Import, package creation and host tests do not contact a device. Physical entry
requires a fresh preflight, a committed/pushed registration and exact artifacts.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load('condition306_gate', R / 'gate.py')
old = load('condition306_thermal', R.parent / 'test-300-passive-thermal-registration/host_flow.py')
h = old.h


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def configure():
    global PLAN, PACKAGE, STAGED
    PLAN = read(R / 'registration.json')
    PACKAGE = read(R / 'PACKAGE.json')
    STAGED = read(R / 'staged-files.json')
    h.R, h.PLAN, h.PACKAGE, h.STAGED = R, PLAN, PACKAGE, STAGED
    h.STAGE, h.TMP = 'D:/android/gts9-active/gts9-test306', '/tmp/gts9-test306'
    p.SERIAL = 'gts9wifi-0001'


def verify_stage(local):
    if set(x.name for x in local.iterdir()) != set(STAGED):
        raise ValueError('staging file set')
    for name, meta in STAGED.items():
        target = local / name
        if target.is_symlink() or not target.is_file():
            raise ValueError('nonregular staging file: ' + name)
        data = target.read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('stage drift: ' + name)


def verify_inputs(require_push=False):
    inputs = read(R / 'INPUTS.json')
    for name, expected in inputs.items():
        path = ROOT / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('registered input drift: ' + name)
    verify_stage(Path('/mnt/d/android/gts9-active/gts9-test306'))
    if require_push:
        def git(*args):
            return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
        if git('branch', '--show-current') != 'test' or git('rev-parse', 'HEAD') != git('rev-parse', 'origin/test'):
            raise ValueError('registration must be pushed to origin/test')
        controlled = list(inputs) + [str((R / 'INPUTS.json').relative_to(ROOT))]
        if git('status', '--porcelain', '--', *controlled):
            raise ValueError('uncommitted registered input')
        subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', *controlled],
                       check=True, stdout=subprocess.DEVNULL)


def identity(raw, phase, expected=None):
    sections = h.g.baseline.sections(raw)
    boot = sections['boot'].strip().replace('-', '')
    if not re.fullmatch('[0-9a-f]{32}', boot) or (expected and boot != expected):
        raise ValueError('boot identity changed/invalid')
    if '7.2.0-rc3-gts9wifi-dirty' not in sections['uname'] or sections['cmdline'].strip() != PLAN['runtime_cmdline']:
        raise ValueError('release/normal cmdline')
    pair = [x.split()[0] for x in sections['identity'].splitlines()]
    if pair != [PLAN[phase + '_config_sha256'], PLAN[phase + '_notes_sha256']]:
        raise ValueError('config/notes identity')
    battery = gate.battery_entry(sections['battery'])
    if gate.values(sections['battery']).get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN') != '4440000':
        raise ValueError('float design changed')
    usb = gate.values(sections['usb'])
    if usb.get('POWER_SUPPLY_ONLINE') != '1' or '[SDP]' not in usb.get('POWER_SUPPLY_USB_TYPE', ''):
        raise ValueError('PC USB SDP absent')
    if usb.get('POWER_SUPPLY_INPUT_CURRENT_LIMIT') != '500000':
        raise ValueError('PC USB input policy changed')
    if sections['dcc'].strip() != 'absent' or sections['failed'].strip():
        raise ValueError('DCC/systemd failure')
    if sections['services'].splitlines() != ['active'] * 3 or sections['roles'].splitlines() != ['[sink]', '[device]']:
        raise ValueError('rescue service or Sink/Device role')
    if 'usb0    inet 169.254.42.1/' not in sections['network']:
        raise ValueError('device NCM address unavailable')
    snapshot = gate.values(sections['snapshot'])
    if snapshot.get('pump_enable_supported') != '0' or snapshot.get('sample_valid') != '1':
        raise ValueError('pump capability/missing cached conversion')
    for key in ('sample_mode_before', 'sample_mode_after'):
        if int(snapshot[key], 0) & 12:
            raise ValueError('pump/reverse mode')
    if int(snapshot['sample_ibus_ua']) != 0 or int(snapshot['sample_faults'], 0) not in (0, 128):
        raise ValueError('pump current/new fault')
    if phase == 'baseline' and snapshot.get('condition_test') == '1':
        raise ValueError('diagnostic retained as baseline')
    if phase == 'candidate' and (snapshot.get('condition_condition_error') != '0'
                               or snapshot.get('condition_restore_error') != '0'
                               or snapshot.get('enhiz_restore_pending') != '0'
                               or snapshot.get('last_sample_error') != '0'):
        raise ValueError('ADC/condition/restore error')
    return sections, boot, battery, snapshot


def transfer(rec):
    expected = ''.join(meta['sha256'] + '  ' + h.TMP + '/' + name + '\n'
                       for name, meta in STAGED.items())
    rec.host_adb('push-package', '-s', p.SERIAL, 'push', h.STAGE, '/tmp/', timeout=60)
    rec.adb('verify-package', 'printf %s ' + shlex.quote(expected) + ' | sha256sum -c -', timeout=20)
    rec.adb('mount-root', 'sh ' + h.TMP + '/mount-debian.sh', timeout=15)


def thermal(rec, name, boot):
    command = ('set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@zones; pack=; '
               'for z in /sys/class/thermal/thermal_zone*; do t=$(cat "$z/type"); '
               'm=$(cat "$z/mode"); printf "%s|%s|%s\\n" "$z" "$t" "$m"; '
               'if test "$t" = sm5714-battery; then test -z "$pack"; pack=$z; fi; done; '
               'test -n "$pack"; echo @@pack-temperature; cat "$pack/temp"; '
               'echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent')
    raw, _ = rec.adb(name, command, timeout=10)
    result = old.parse_thermal(raw, boot)
    gate.battery_entry(h.g.baseline.sections(raw)['battery'])
    if not 20000 <= result['pack_millic'] < 38000:
        raise ValueError('real pack sensor outside registered range')
    write(rec.folder / (name + '.json'), result)
    return result


def preflight():
    verify_inputs()
    rec = p.Recorder(R / 'preflight')
    raw, _ = rec.adb('current-state', PLAN['current_command'], timeout=15)
    sec, boot, battery, snap = identity(raw, 'baseline')
    modules = (R / 'rollback-modules.sha256').read_text()
    command = ('set -e; test "$(cat /etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; '
               'cd /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; '
               'test "$(find . -type f | wc -l)" = 181; printf %s ' +
               shlex.quote(modules) + ' | sha256sum -c -')
    jobs = h.parallel({
        'partitions': lambda: rec.adb('partitions', h.PARTS, timeout=20),
        'modules': lambda: rec.adb('modules', command, timeout=20),
        'boots': lambda: rec.adb('boots-before', 'journalctl --list-boots --no-pager', timeout=10),
        'kernel': lambda: rec.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15),
        'windows': lambda: rec.ps('windows-usb', p.PS_USB, timeout=20)})
    h.require_partitions(jobs['partitions'][0], PACKAGE['baseline_partitions'])
    if p.has_code43(jobs['windows'][0]) or not re.search(r'ProblemCode\s*:\s*0\b', jobs['windows'][0]):
        raise ValueError('Windows USB not confirmed Code0')
    if h.g.evidence.boot_list(jobs['boots'][0])[-1] != boot:
        raise ValueError('preflight boot history')
    scan = old.scan_journal(jobs['kernel'][0], boot, float(sec['uptime'].split()[0]), snap)
    write(rec.folder / 'journal-classification.json', scan)
    thermal(rec, 'thermal', boot)
    old.ncm_probe(rec, boot)  # one host probe; device NCM/rescue remain mandatory
    result = dict(verdict='READY_FOR_REGISTERED_ONE_BOOT', boot_id=boot,
                  collected_at_epoch=time.time(), battery=battery, device_NCM=True,
                  device_mutation=False, charging_authorized=False)
    write(rec.folder / 'summary.json', result)
    return result


def admission(folder, phase, before, boots_before):
    rec = p.Recorder(folder)
    p.SERIAL = 'gts9wifi-0001'
    start, index = time.monotonic(), 0
    while time.monotonic() - start < PLAN['readiness_max_seconds']:
        raw, status = rec.adb(f'readiness-{index:02}', PLAN['readiness_command'], timeout=8, required=False)
        index += 1
        sections = h.g.baseline.sections(raw)
        if 'POWER_SUPPLY_HEALTH=' in sections.get('battery', ''):
            gate.battery_entry(sections['battery'])
        if phase == 'candidate':
            # A partial shell command can still contain the first ADC failure.
            # Preserve it and stop even if a later service command also failed.
            s = gate.values(sections.get('snapshot', ''))
            errors = (s.get('condition_condition_error', '0'), s.get('condition_restore_error', '0'),
                      s.get('last_sample_error', '0'))
            if any(int(x) for x in errors):
                raise ValueError('first ADC/restore error')
        if status == 0:
            # Refuse reported condition errors as soon as they exist; do not
            # wait out readiness, reboot again or attempt another conversion.
            if raw.splitlines().count('active') == 3 and 'sample_valid=1' in raw and 'usb0    inet 169.254.42.1/' in raw:
                break
        time.sleep(3)
    else:
        raise TimeoutError('Debian rescue unavailable; no repeated boot')
    raw, _ = rec.adb('current-state', PLAN['current_command'], timeout=15)
    sec, boot, battery, snap = identity(raw, phase)
    jobs = h.parallel({
        'kernel': lambda: rec.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15),
        'boots': lambda: rec.adb('boots-after', 'journalctl --list-boots --no-pager', timeout=10),
        'windows': lambda: rec.ps('windows-usb', p.PS_USB, timeout=20),
        'ncm': lambda: old.ncm_probe(rec, boot)})
    if p.has_code43(jobs['windows'][0]):
        raise ValueError('Windows Code43')
    if before is not None and h.g.evidence.attribute(before, boot, boots_before, jobs['boots'][0]) != 'attributed':
        raise ValueError('unexplained/missing boot attribution')
    scan = old.scan_journal(jobs['kernel'][0], boot, float(sec['uptime'].split()[0]), snap)
    write(folder / 'journal-classification.json', scan)
    thermal(rec, 'thermal', boot)
    result = dict(boot_id=boot, battery=battery, device_NCM=True,
                  host_NCM_probe_status=jobs['ncm'][1], charging_authorized=False,
                  boot_attribution='attributed' if before is not None else 'missing_failed_candidate_history')
    if phase == 'candidate':
        result['condition'] = gate.condition(sec['snapshot'], jobs['kernel'][0], boot)
    write(folder / 'summary.json', result)
    return result, jobs['boots'][0]


def restoration_layout(raw):
    parts = h.partitions(raw)
    expected = PACKAGE['baseline_partitions']
    if set(parts) != set(expected) or any(parts[k] != expected[k] for k in expected if k != 'boot'):
        raise ValueError('non-boot partition drift; no blind recovery write')
    if parts['boot'] not in (expected['boot'], PACKAGE['candidate_partitions']['boot']):
        raise ValueError('unrecognized boot image; manual recovery required')
    return parts['boot']


def restore(from_recovery=False):
    if not (R / 'mutation-state.json').exists():
        raise ValueError('no registered mutation to restore')
    verify_inputs(require_push=True)
    folder = R / ('manual-rollback-install' if from_recovery else 'rollback-install')
    rec = p.Recorder(folder)
    if not from_recovery:
        p.SERIAL = 'gts9wifi-0001'
        target, _ = rec.adb('target-boot-id', 'cat /proc/sys/kernel/random/boot_id', timeout=8)
        boots, _ = rec.adb('target-boots', 'journalctl --list-boots --no-pager', timeout=10)
        target = target.strip().replace('-', '')
        h.enter_recovery(rec)
    else:
        p.SERIAL = 'R52X10045LT'
        # Manual recovery must still identify this board/root. No device write
        # is inferred from an old installation summary or disconnected command.
        ident, _ = rec.adb('manual-twrp-identity', 'getprop ro.product.device; id', timeout=10)
        if 'gts9wifi' not in ident or 'uid=0' not in ident:
            raise ValueError('manual TWRP identity')
        target, boots = None, None
    transfer(rec)
    raw, _ = rec.adb('partitions-before', h.PARTS, timeout=20)
    current = restoration_layout(raw)
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    module_root = '/mnt/debian/usr/lib/modules'
    state, _ = rec.adb('module-layout', f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; '
                      f'if test -d {module_root}/.gts9-test306-original; then echo saved; else echo no-saved; fi', timeout=10)
    if state.strip() == 'saved':
        rec.adb('restore-modules', f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256', timeout=25)
    elif state.strip() != 'no-saved' or current != PACKAGE['baseline_partitions']['boot']:
        raise ValueError('paired rollback modules missing')
    h.verify_modules(rec, 'restored-modules', 'rollback-modules.sha256')
    if current != PACKAGE['baseline_partitions']['boot']:
        h.write_boot(rec, 'restore-boot', 'rollback-accepted299-boot.img', current, PACKAGE['baseline_partitions']['boot'])
    raw, _ = rec.adb('partitions-after', h.PARTS, timeout=20)
    h.require_partitions(raw, PACKAGE['baseline_partitions'])
    h.clear_unmount(rec)
    write(rec.folder / 'summary.json', dict(verdict='ACCEPTED299_ALLFIVE_181_RESTORED'))
    rec.host_adb('normal-reboot', '-s', p.SERIAL, 'reboot', timeout=10)
    # A failed candidate may never have completed journald. Still verify the
    # restored baseline's actual identity/thermal/rescue/journal, while retaining
    # the missing candidate attribution explicitly (never a clean Test306).
    final = admission(R / ('manual-final-acceptance' if from_recovery else 'final-acceptance'),
                      'baseline', target, boots)[0]
    write(R / 'mutation-state.json', dict(rollback_required=False, phase='accepted299-restored', final=final))
    return final


def install_once():
    pre = read(R / 'preflight/summary.json')
    if pre['verdict'] != 'READY_FOR_REGISTERED_ONE_BOOT' or not 0 <= time.time() - pre['collected_at_epoch'] <= PLAN['preflight_max_age_seconds']:
        raise ValueError('fresh successful preflight required')
    rec = p.Recorder(R / 'installation')
    raw, _ = rec.adb('live-boundary', PLAN['current_command'], timeout=15)
    identity(raw, 'baseline', pre['boot_id'])
    # From the first possible BCB request onward, cleanup is required even if
    # no kernel/module write has happened. A failed transfer must not strand a
    # healthy baseline in recovery and leave an armed BCB unreported.
    write(R / 'mutation-state.json', dict(rollback_required=True, phase='recovery-requested-no-kernel-write'))
    h.enter_recovery(rec)
    transfer(rec)
    raw, _ = rec.adb('partitions-before', h.PARTS, timeout=20)
    h.require_partitions(raw, PACKAGE['baseline_partitions'])
    h.verify_modules(rec, 'original-modules', 'rollback-modules.sha256')
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    write(R / 'mutation-state.json', dict(rollback_required=True, phase='before-module-swap'))
    rec.adb('install-modules', f'sh {h.TMP}/module-swap.sh /mnt/debian install {h.TMP}/candidate-modules.sha256 {h.TMP}/candidate-modules.tar.gz {h.TMP}/rollback-modules.sha256', timeout=25)
    h.write_boot(rec, 'write-boot', 'candidate-boot.img', PACKAGE['baseline_partitions']['boot'], PACKAGE['candidate_partitions']['boot'])
    raw, _ = rec.adb('partitions-after', h.PARTS, timeout=20)
    h.require_partitions(raw, PACKAGE['candidate_partitions'])
    h.clear_unmount(rec)
    write(R / 'mutation-state.json', dict(rollback_required=True, phase='candidate-reboot-requested'))
    rec.host_adb('normal-reboot', '-s', p.SERIAL, 'reboot', timeout=10)
    result, _ = admission(R / 'candidate-admission', 'candidate', pre['boot_id'], (R / 'preflight/boots-before.txt').read_text())
    time.sleep(PLAN['endpoint_seconds'])
    end = p.Recorder(R / 'endpoint')
    raw, _ = end.adb('current-state', PLAN['current_command'], timeout=15)
    sec, boot, _, _ = identity(raw, 'candidate', result['boot_id'])
    journal, _ = end.adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15)
    write(end.folder / 'condition.json', gate.condition(sec['snapshot'], journal, boot))
    write(end.folder / 'journal-classification.json', old.scan_journal(journal, boot, float(sec['uptime'].split()[0]), gate.values(sec['snapshot'])))
    thermal(end, 'thermal', boot)
    return result


def run():
    verify_inputs(require_push=True)
    if (R / 'mutation-state.json').exists():
        raise ValueError('one attempt only; inspect existing mutation state')
    result, failure = None, None
    try:
        result = install_once()
    except Exception as exc:
        failure = str(exc)
        write(R / 'first-failure.json', dict(error=failure, stopped=True, charging_authorized=False))
        # Best effort evidence capture never retries the experiment/boot.
        if p.SERIAL == 'gts9wifi-0001':
            p.Recorder(R / 'first-failure').adb('kernel-json', 'journalctl -k -b -o json --no-pager', timeout=15, required=False)
    finally:
        if (R / 'mutation-state.json').exists():
            try:
                final = restore(from_recovery=p.SERIAL == 'R52X10045LT')
                write(R / 'mutation-state.json', dict(rollback_required=False, phase='accepted299-restored', final=final))
            except Exception as exc:
                write(R / 'recovery-required.json', dict(error=str(exc), manual_TWRP_required=True, no_blind_retry=True))
                raise RuntimeError('automatic restoration incomplete; manual TWRP required: ' + str(exc)) from exc
    if failure:
        raise RuntimeError('first non-clean stopped/restored: ' + failure)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'run', 'restore'))
    parser.add_argument('--from-recovery', action='store_true')
    args = parser.parse_args()
    configure()
    if args.from_recovery and args.action != 'restore':
        parser.error('--from-recovery is only for restore')
    action = {'preflight': preflight, 'run': run, 'restore': lambda: restore(args.from_recovery)}[args.action]
    print(json.dumps(action(), indent=2), flush=True)
