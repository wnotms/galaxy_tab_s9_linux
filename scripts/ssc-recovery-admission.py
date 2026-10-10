#!/usr/bin/env python3
"""Read-only TWRP transport admission; never retry a failed command or mutate.

Three successful ADB recovery/root/boot snapshots spanning eight seconds must
precede root remount or installation. This detects early enumeration churn; it
is not a guarantee against a later disconnect or a USB root-cause fix.
"""
import json
import math
import time
from uuid import UUID

SERIAL = 'R52X10045LT'
COMMAND = 'getprop ro.product.device; uname -r; id -u; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime'


def parse(raw):
    lines = raw.replace('\r', '').strip().splitlines()
    if len(lines) != 5 or lines[:3] != ['gts9wifi', '5.15.94-Foldiby-+', '0']:
        raise ValueError('not exact X710 root TWRP')
    boot = str(UUID(lines[3]))
    uptime = float(lines[4].split()[0])
    if not math.isfinite(uptime) or uptime < 0:
        raise ValueError('invalid recovery uptime')
    return dict(boot_id=boot, uptime=uptime)


def capture_fault(rec):
    for name, operation in (
        ('adb-list', lambda: rec.host_adb('recovery-fault-devices', 'devices', '-l', timeout=3, required=False)),
        ('kernel', lambda: rec.adb('recovery-fault-kernel', 'dmesg | tail -n 600', timeout=3, required=False))):
        # Admission and installation may share a first failure. Preserve the
        # first capture without repeating a failed evidence query.
        target = rec.folder / ('recovery-fault-devices.txt' if name == 'adb-list' else 'recovery-fault-kernel.txt')
        error = rec.folder / ('recovery-'+name+'-error.json')
        if target.exists() or error.exists():
            continue
        try:
            operation()
        except Exception as failed:
            error.write_text(json.dumps(dict(error=str(failed)))+'\n')


def admit(rec, *, clock=time.monotonic, sleep=time.sleep):
    start = clock(); samples = []
    try:
        for number in range(3):
            if clock()-start >= 30:
                raise TimeoutError('recovery admission exceeded 30s')
            state, _ = rec.host_adb('recovery-stable-state-%02d'%number, '-s', SERIAL, 'get-state', timeout=3)
            if state.strip() != 'recovery':
                raise ValueError('recovery ADB state changed')
            raw, _ = rec.adb('recovery-stable-shell-%02d'%number, COMMAND, timeout=3)
            sample = parse(raw)
            sample['host_elapsed'] = clock()-start
            if samples and (sample['boot_id'] != samples[0]['boot_id'] or sample['uptime'] < samples[-1]['uptime']):
                raise ValueError('recovery reboot or backwards uptime')
            samples.append(sample)
            if number < 2:
                sleep(4)
        if (samples[-1]['host_elapsed']-samples[0]['host_elapsed'] < 8 or
                samples[-1]['uptime']-samples[0]['uptime'] < 7 or clock()-start > 30):
            raise ValueError('incomplete bounded recovery stability window')
        result = dict(verdict='TWRP_ROOT_SAME_BOOT_THREE_SNAPSHOTS_PASS', samples=samples,
                      seconds=clock()-start, mutation=False, failed_command_retried=False)
        (rec.folder/'recovery-admission.json').write_text(json.dumps(result, indent=2)+'\n')
        return result
    except Exception as exc:
        # Preserve first admission failure, and bounded best-effort transport
        # state. These are read-only evidence queries, not retries or recovery.
        result = dict(verdict='STOP_RECOVERY_ADMISSION', error=str(exc), samples=samples,
                      seconds=clock()-start, mutation=False, failed_command_retried=False)
        (rec.folder/'recovery-admission.json').write_text(json.dumps(result, indent=2)+'\n')
        capture_fault(rec)
        raise
