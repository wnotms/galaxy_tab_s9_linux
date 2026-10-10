#!/usr/bin/env python3
"""Test394: read actual Samsung recovery SoC fields, return unchanged Test370.

Only BCB boot-mode control is written. No image/module/rootfs/registry install,
DSP/RPC startup, TCPC request or service/configuration change.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import time
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load('soc394_accepted393', R.parent/'test-393-standard-pdr-listener/host_flow.py')
COMPARE = load('soc394_compare', ROOT/'userspace/sensors/stock-socinfo-compare.py')
ADMISSION = load('soc394_recovery', ROOT/'scripts/ssc-recovery-admission.py')
GUARD = load('soc394_health', R.parent/'test-371-usb-lifecycle-gmu/host_flow.py')
p = BASE.p
PLAN = json.loads((R/'registration.json').read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def verify(pushed=False):
    for name, digest in json.loads((R/'INPUTS.json').read_text()).items():
        path = ROOT/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('registered input drift: '+name)
    if pushed:
        git = lambda *args: subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
        if (git('branch', '--show-current') != 'test' or
                git('rev-parse', 'HEAD') != git('rev-parse', 'origin/test') or
                git('status', '--porcelain')):
            raise ValueError('clean registration must be pushed to origin/test')


def snapshot(rec, name, expected=None):
    raw, _ = rec.adb(name, BASE.CAPTURE, timeout=15)
    data = json.loads(raw)
    BASE.identity(data, 'baseline', expected)
    if data['services']['gdm'] != 'active' or any(x['state'] != 'offline' for x in data['adsp']):
        raise ValueError('accepted desktop/ADSP-offline baseline changed')
    if data['native_socinfo']['boot_id'] != data['boot_id']:
        raise ValueError('native SoC snapshot not boot-bound')
    COMPARE.MAPPER.translate(data['native_socinfo'])
    return data


def partitions(rec, name):
    raw, _ = rec.adb(name, BASE.parts.DEBIAN_PARTS, timeout=25)
    BASE.parts.require_debian_partitions(raw, BASE.PACKAGE['baseline_partitions'])


def preflight():
    verify()
    folder = R/'preflight'
    folder.mkdir(exist_ok=False)
    rec = p.Recorder(folder)
    p.SERIAL = 'gts9wifi-0001'
    data = snapshot(rec, 'identity', PLAN['before_boot_id'])
    partitions(rec, 'partitions')
    BASE.modules(rec, 'modules', False)
    raw, _ = rec.adb('kernel', 'journalctl -k -b -o json --no-pager', timeout=15)
    rows = GUARD.journal(raw, data['boot_id'])
    old = ROOT/PLAN['enrolled_kernel']
    if hashlib.sha256(old.read_bytes()).hexdigest() != PLAN['enrolled_kernel_sha256']:
        raise ValueError('enrolled baseline changed')
    GUARD.health(rows, GUARD.journal(old.read_text(), data['boot_id']), {})
    boots, _ = rec.adb('boots', BASE.PLAN['boot_history_command'], timeout=10)
    if BASE.h.g.evidence.boot_list(boots)[-1] != UUID(data['boot_id']).hex:
        raise ValueError('baseline boot history mismatch')
    windows, _ = rec.ps('windows-usb', p.PS_USB, timeout=20)
    if p.has_code43(windows):
        raise ValueError('Windows Code43')
    result = dict(verdict='READONLY_PREFLIGHT_PASS', epoch=time.time(),
                  snapshot=data, expected=COMPARE.MAPPER.translate(data['native_socinfo']))
    write(folder/'summary.json', result)
    return result


def return_to_baseline(rec, recovery_boot, before):
    p.SERIAL = ADMISSION.SERIAL
    # Same known recovery and unchanged image set are required before the normal
    # return. A transport loss cannot authorize a blind reboot.
    raw, _ = rec.adb('return-identity', ADMISSION.COMMAND, timeout=5)
    if ADMISSION.parse(raw)['boot_id'] != recovery_boot:
        raise ValueError('recovery changed before return; manual recovery needed')
    raw, _ = rec.adb('recovery-partitions', BASE.h.PARTS, timeout=25)
    BASE.h.require_partitions(raw, BASE.PACKAGE['baseline_partitions'])
    # Existing port workflow uses the first2048-byte BCB only. No boot/image
    # partition is written; no Debian filesystem is mounted from recovery.
    rec.adb('clear-bcb', 'set -e; test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576; '
            'dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc; sync', timeout=10)
    raw, _ = rec.adb('verify-bcb', 'dd if=/dev/block/by-name/misc bs=2048 count=1 2>/dev/null | od -An -v -tx1', timeout=5)
    if len(raw.split()) != 2048 or any(x != '00' for x in raw.split()):
        raise ValueError('BCB clear readback incomplete')
    rec.host_adb('normal-return', '-s', p.SERIAL, 'reboot', timeout=10)
    p.SERIAL = 'gts9wifi-0001'
    started = time.monotonic()
    number = 0
    while time.monotonic()-started < PLAN['readiness_seconds']:
        raw, status = rec.adb('readiness-%02d'%number,
                'cat /proc/sys/kernel/random/boot_id; systemctl is-active gdm gts9-adbd gts9-usb-acm',
                timeout=5, required=False)
        number += 1
        if status == 0 and raw.splitlines().count('active') == 3:
            break
        time.sleep(2)
    else:
        raise TimeoutError('normal desktop unavailable; no second reboot')
    data = snapshot(rec, 'identity')
    if UUID(data['boot_id']) in (UUID(before['boot_id']), UUID(recovery_boot)):
        raise ValueError('ordinary return boot did not change')
    boots, _ = rec.adb('boots-after', BASE.PLAN['boot_history_command'], timeout=10)
    prior = (R/'preflight/boots.txt').read_text()
    if BASE.h.g.evidence.attribute(UUID(before['boot_id']).hex, UUID(data['boot_id']).hex,
                                    prior, boots) != 'attributed':
        raise ValueError('unexplained Debian boot in recovery round trip')
    partitions(rec, 'partitions')
    raw, _ = rec.adb('kernel', 'journalctl -k -b -o json --no-pager', timeout=15)
    classified = BASE.h.g.evidence.inspect_journal(raw, UUID(data['boot_id']).hex,
        {json.loads(x)['MESSAGE'] for x in (R/'preflight/kernel.txt').read_text().splitlines()
         if int(json.loads(x).get('PRIORITY', 7)) <= 3},
        require_start=True, accepted_startup_variants=True,
        startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True,
        observed_uptime=data['uptime'])
    write(rec.folder/'kernel-verdict.json', classified)
    if classified['fault_counts'] or classified['suspects']:
        raise ValueError('new kernel fault/suspect after return')
    result = dict(verdict='UNCHANGED370_DESKTOP_RETURNED', boot_id=data['boot_id'],
                  snapshot=data, ADB=True, device_NCM=True, partitions_unchanged=True,
                  config_notes_unchanged=True, modules_written=False, rootfs_written=False)
    write(rec.folder/'summary.json', result)
    return result


def run():
    verify(pushed=True)
    if (R/'execution').exists():
        raise ValueError('one attempt already consumed; no replay')
    before = json.loads((R/'preflight/summary.json').read_text())
    if time.time()-before['epoch'] > PLAN['preflight_max_age_seconds']:
        raise ValueError('preflight stale; no mutation')
    rec = p.Recorder(R/'execution')
    p.SERIAL = 'gts9wifi-0001'
    snapshot(rec, 'live-boundary', before['snapshot']['boot_id'])
    write(R/'execution-state.json', dict(return_required=True, phase='before-BCB-request'))
    try:
        rec.adb('helper-check', 'TMPDIR=/tmp gts9-debian-to-recovery --check', timeout=10)
        rec.adb('BCB-request', 'TMPDIR=/tmp gts9-debian-to-recovery --yes --no-reboot', timeout=10)
        rec.adb('ordinary-reboot', 'systemctl reboot', timeout=10, required=False)
        wait = BASE.h.recovery.wait_recovery(rec, timeout=PLAN['readiness_seconds'])
        write(rec.folder/'recovery-wait.json', wait)
        p.SERIAL = ADMISSION.SERIAL
        admission = ADMISSION.admit(rec)
        boot = admission['samples'][-1]['boot_id']
        if UUID(boot) == UUID(before['snapshot']['boot_id']):
            raise ValueError('recovery boot unchanged')
    except Exception as error:
        write(rec.folder/'entry-error.json', dict(error=str(error), no_blind_reboot=True))
        raise

    def observe():
        rec.adb('recovery-dmesg', 'dmesg', timeout=10)
        rec.adb('recovery-persistent', 'ls -la /sys/fs/pstore; '
            'for f in /sys/fs/pstore/* /proc/last_kmsg; do '
            'if test -f "$f"; then printf "source=%s\\n" "$f"; cat "$f"; '
            'else printf "unavailable=%s\\n" "$f"; fi; done', timeout=15)
        raw, _ = rec.adb('stock-socinfo', COMPARE.COMMAND, timeout=10)
        result = COMPARE.compare(raw, boot, before['snapshot']['native_socinfo'])
        write(rec.folder/'comparison.json', result)
        return result

    returned = p.Recorder(R/'return')
    result = COMPARE.observe_then_return(observe,
        lambda: return_to_baseline(returned, boot, before['snapshot']))
    result.update(test='Test394', recovery_boot_id=boot, kernel_rebuilt=False,
                  image_write=False, registry_write=False, DSP_started=False,
                  PPS=False, pump_ON=False, sensor_acceptance=False)
    write(R/'summary.json', result)
    write(R/'execution-state.json', dict(return_required=result['return_error'] is not None,
                                       phase='returned' if not result['return_error'] else 'manual-recovery-required'))
    if result['observation_error'] or result['return_error']:
        raise ValueError('first failure retained; no repeat: '+str(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('verify', 'preflight', 'run'))
    args = parser.parse_args()
    print(json.dumps(globals()[args.mode](), indent=2))
