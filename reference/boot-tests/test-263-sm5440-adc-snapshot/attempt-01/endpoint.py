#!/usr/bin/env python3
"""Owner-confirmed endpoints only; no cable waiting or device writes."""
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
import sm5714_fixed_charge_regression as f
from sm5440_passive_admission import startup_evidence
from sm5440_ready_admission import ReadyRecorder
from snapshot_gate import validate_snapshot

A = Path(__file__).resolve().parent
assert len(sys.argv) == 2 and sys.argv[1] in {'unplug', 'pc'}
mode = sys.argv[1]
previous = json.loads((A / ('pd-observation' if mode == 'unplug' else 'unplug-endpoint') / 'summary.json').read_text())
assert previous['verdict'].endswith('passed')
accepted = json.loads((A / 'observation/summary.json').read_text())
boot = accepted['boot_id']
folder = A / (mode + '-endpoint')
assert not folder.exists()
r = ReadyRecorder(folder)
wifi = re.search(r'\binet (\d+\.\d+\.\d+\.\d+)/', (A / 'observation/final-wifi-address.txt').read_text()).group(1)
argv = ['env', 'GTS9_DEVICE=' + wifi, p.SSH]
rows = []
p.SERIAL = 'gts9wifi-0001'

try:
    start = time.monotonic()
    while True:
        raw = r.command(f'sample-{len(rows):03}', argv + [f.COMMAND +
                        '\necho @@snapshot; cat /sys/kernel/debug/sm5440-0-0063/snapshot'], 15)[0]
        sample = f.parse(raw)
        error = f.safety(sample, boot, rows)
        if error:
            raise p.CaptureError(error)
        snapshot_raw = raw.split('\n@@snapshot\n', 1)[1]
        snapshot = dict(x.split('=', 1) for x in snapshot_raw.splitlines())
        for k, value in {'sample_present': '1', 'sample_valid': '1', 'sample_fresh': '1',
                         'fault': '0', 'stopped': '0', 'startup_pending': '0',
                         'last_sample_error': '0', 'sample_faults': '0x0'}.items():
            if snapshot.get(k) != value:
                raise p.CaptureError('endpoint snapshot unavailable/fault')
        if (not 0 <= int(snapshot['sample_age_ms']) <= 2500 or
                any(int(snapshot[k], 16) & 0x0c for k in ('sample_mode_before', 'sample_mode_after'))):
            raise p.CaptureError('endpoint stale/active snapshot')
        if mode == 'unplug':
            if not (sample['usb_online'] == sample['tcpm_online'] == sample['passive_online'] == 0 and
                    sample['battery_status'] == 'Discharging' and sample['battery_current_ua'] < 0):
                raise p.CaptureError('confirmed unplug endpoint not discharging/offline')
        else:
            validate_snapshot(snapshot_raw, 5)
            if not (sample['usb_online'] == sample['passive_online'] == 1 and
                    sample['power_role'] == 'sink' and sample['data_role'] == 'device'):
                raise p.CaptureError('PC endpoint roles/online')
        reference = accepted['samples'][0]['snapshot']
        if any(snapshot[k] != reference[k] for k in ('sample_cntl2', 'sample_vbuscntl', 'sample_vbatcntl', 'sample_prtncntl')):
            raise p.CaptureError('protection changed')
        sample['elapsed_seconds'] = round(time.monotonic() - start, 3)
        sample['snapshot'] = snapshot
        rows.append(sample)
        if mode == 'pc' or sample['elapsed_seconds'] >= 15:
            break
        time.sleep(min(5, 15 - sample['elapsed_seconds']))
    known_file = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
    known = {x['MESSAGE'] for x in map(json.loads, known_file.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}
    raw = r.command('kernel-json', argv + ['journalctl -b -k --no-pager -o json'], 25)[0]
    scan = e.inspect_journal(raw, boot, known, accepted_startup_variants=True,
                            startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True,
                            observed_uptime=rows[-1]['uptime_seconds'])
    p.write_json(r.folder / 'kernel-scan.json', scan)
    if scan['fault_counts'] or scan['suspects'] or startup_evidence(raw, boot) != accepted['startup']:
        raise p.CaptureError('new kernel/passive fault')
    if mode == 'pc':
        from sm5440_passive_admission import admit
        package = json.loads((A / 'PACKAGE.json').read_text())
        identity = admit(r, boot, package['artifacts']['out/kernel-x710-263-passive/config']['sha256'],
                         package['artifacts']['out/kernel-x710-263-passive/kernel-notes.bin']['sha256'], known)
        if r.ready['delayed_readiness']:
            raise p.CaptureError('delayed readiness; first evidence retained')
        p.write_json(r.folder / 'admission.json', identity)
        raw = r.adb('dcc-services', 'set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; ! systemctl is-active --quiet serial-getty@hvc0.service; systemctl is-active ssh gts9-adbd; cat /proc/sys/kernel/random/boot_id', 15)[0].splitlines()
        if raw[:2] != ['active', 'active'] or e.canonical_boot_id(raw[-1]) != boot:
            raise p.CaptureError('ADB/DCC/services')
    result = dict(verdict=mode + ' endpoint passed', boot_id=boot, samples=rows,
                  observed_seconds=rows[-1]['elapsed_seconds'], transition_captured=False,
                  physical_recovery_time_measured=False, pump_on=False, pps_requested=False)
except Exception as exc:
    result = dict(verdict='STOP first non-clean ' + mode + ' endpoint', error=str(exc),
                  boot_id=boot, samples=rows, rollback_required=True)
    try:
        r.command('first-failure-kernel-json', argv + ['journalctl -b -k --no-pager -o json'], 25, required=False)
        r.command('first-failure-supplies', argv + [f.COMMAND], 15, required=False)
    finally:
        p.write_json(folder / 'summary.json', result)
    raise
p.write_json(folder / 'summary.json', result)
print(result['verdict'], len(rows), 'samples', result['observed_seconds'], 'seconds', flush=True)
