#!/usr/bin/env python3
"""Exactly one unchanged-baseline normal reboot; no flash or charge activation."""
import json
from pathlib import Path
import re
import shlex
import sys
import time
from gate import sections, props, battery_entry, diagnostic_sample

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
from sm5440_passive_admission import startup_evidence

A = Path(__file__).resolve().parent
PLAN = json.loads((A / 'registration.json').read_text())
CURRENT_CMD = json.loads((ROOT / 'reference/boot-tests/test-270-high-power-readiness/device-state-via-adb/current-state.command.json').read_text())['argv'][-1]
KNOWN_PATH = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
KNOWN = {x['MESSAGE'] for x in map(json.loads, KNOWN_PATH.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}

def require(ok, why):
    if not ok:
        raise p.CaptureError(why)

def main():
    require(not (A / 'physical').exists(), 'no retry/overwrite')
    p.SERIAL = 'gts9wifi-0001'
    r = p.Recorder(A / 'physical')
    boot = None
    samples = []
    reboot_sent = False
    def identity(sec):
        ids = sec['identity'].splitlines()
        require(ids[0].split()[0] == PLAN['config_sha256'] and ids[1].split()[0] == PLAN['notes_sha256'], 'Test263 identity changed')
        require(sec['services'].strip().splitlines() == ['active'] * 3 and not sec['failed'].strip(), 'services')
        require(sec['cmdline'].strip() == PLAN['runtime_cmdline'], 'runtime cmdline changed')
    def kernel(raw, name, uptime, full=False):
        rows = raw.splitlines()
        data = '\n'.join(x for x in rows if x.startswith('{'))
        require(bool(data) or not full, 'empty full kernel journal')
        if data:
            scan = e.inspect_journal(data, boot, KNOWN, require_start=full, accepted_startup_variants=True,
                startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True, observed_uptime=uptime)
            p.write_json(r.folder / (name + '-scan.json'), scan)
            require(not scan['fault_counts'] and not scan['suspects'], 'kernel/CPU fault or suspect')
            if not full:
                require(not any('sm5440-passive' in x['MESSAGE'] and any(v in x['MESSAGE'] for v in ('fault bitmap=', 'ADC fault', 'confirmation failed')) for x in map(json.loads, data.splitlines())), 'new passive fault')
        require(all(x.startswith('{') or x.startswith('-- cursor: ') or x == '-- No entries --' or not x.strip() for x in rows), 'malformed journal')
        cursor = [x[len('-- cursor: '):] for x in rows if x.startswith('-- cursor: ')]
        require(len(cursor) == 1 and cursor[0], 'missing/ambiguous journal cursor')
        return cursor[0], data
    try:
        sec = sections(r.adb('before-state', CURRENT_CMD, 20)[0])
        identity(sec)
        before = e.canonical_boot_id(sec['boot'])
        require(before == PLAN['before_boot_id'], 'source boot changed')
        battery_entry(props(sec['battery']))
        require(props(sec['usb']).get('POWER_SUPPLY_ONLINE') == '1' and '[SDP]' in sec['usb'], 'PC SDP source required')
        require(sec['roles'].strip().splitlines() == ['[sink]', '[device]'], 'PC Sink/Device source')
        oldsec = sections((ROOT / 'reference/boot-tests/test-270-high-power-readiness/device-state-via-adb/current-state.txt').read_text())
        oldsnap = dict(x.split('=', 1) for x in oldsec['snapshot'].splitlines())
        sourcesnap = dict(x.split('=', 1) for x in sec['snapshot'].splitlines())
        require(all(sourcesnap.get(k) == v for k, v in oldsnap.items() if k not in ('capture_jiffies', 'sample_age_ms', 'sample_fresh')), 'source fault/cache provenance changed before diagnostic boot')
        boot = before
        history = r.adb('boots-before', 'journalctl --list-boots --no-pager', 20)[0]
        oldj = r.adb('before-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)[0]
        kernel(oldj, 'before', float(sec['uptime'].split()[0]), True)
        wifi = r.command('before-wifi', ['env', 'GTS9_DEVICE=' + PLAN['wifi'], p.SSH, 'cat /proc/sys/kernel/random/boot_id'], 15)[0]
        require(e.canonical_boot_id(wifi) == before, 'Wi-Fi boot mismatch')
        w = r.ps('before-windows-usb', p.PS_USB, 30)[0]
        require(not p.has_code43(w), 'Windows Code43')
        reboot_sent = True
        r.adb('normal-reboot', 'systemctl reboot', 10, False)
        deadline = time.monotonic() + 90
        for n in range(45):
            text, status = r.adb(f'wait-boot-{n:02}', 'cat /proc/sys/kernel/random/boot_id', 3, False)
            if status == 0 and text.strip() and e.canonical_boot_id(text) != before:
                boot = e.canonical_boot_id(text)
                break
            require(time.monotonic() < deadline, 'new boot unavailable within90s')
            time.sleep(2)
        require(boot != before, 'no changed boot ID')
        after_history = r.adb('boots-after', 'journalctl --list-boots --no-pager', 20)[0]
        require(e.attribute(before, boot, history, after_history) == 'attributed', 'unexpected/unattributed boot')
        sec = sections(r.adb('after-state', CURRENT_CMD, 20)[0])
        identity(sec)
        require(e.canonical_boot_id(sec['boot']) == boot, 'after-state crossed boot')
        # Save the first fresh/failed snapshot before inspecting its readiness.
        first = diagnostic_sample(sec)
        full = r.adb('initial-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)[0]
        cursor, data = kernel(full, 'initial', float(sec['uptime'].split()[0]), True)
        startup = startup_evidence(data, boot)
        p.write_json(r.folder / 'startup-evidence.json', startup)
        initial_protection = {k: first['snapshot'][k] for k in ('sample_cntl2', 'sample_vbuscntl', 'sample_vbatcntl', 'sample_prtncntl')}
        r.adb('dcc', 'set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; ! systemctl is-active --quiet serial-getty@hvc0.service; echo absent', 15)
        start = time.monotonic()
        while True:
            raw = r.adb(f'sample-{len(samples):03}', CURRENT_CMD + '; echo @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor=' + shlex.quote(cursor), 20)[0]
            sec = sections(raw)
            identity(sec)
            require(e.canonical_boot_id(sec['boot']) == boot, 'unexpected reboot')
            sample = diagnostic_sample(sec)
            require({k: sample['snapshot'][k] for k in initial_protection} == initial_protection, 'protection changed')
            cursor, _ = kernel(sec['kernel'], f'sample-{len(samples):03}', float(sec['uptime'].split()[0]))
            sample['elapsed_s'] = round(time.monotonic() - start, 3)
            samples.append(sample)
            print('Passive diagnostic', sample['elapsed_s'], 's; VBAT', sample['snapshot']['sample_vbat_uv'], 'uV; age', sample['snapshot']['sample_age_ms'], 'ms', flush=True)
            if sample['elapsed_s'] >= 30:
                break
            time.sleep(min(5, 30 - sample['elapsed_s']))
        require(len({x['snapshot']['sample_stamp_jiffies'] for x in samples}) >= 2, 'no continuing fresh conversions')
        full = r.adb('final-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)[0]
        _, data = kernel(full, 'final', float(sec['uptime'].split()[0]), True)
        require(startup_evidence(data, boot) == startup, 'startup event repeated/changed')
        r.adb('final-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 25)
        r.adb('ended-target-kernel-json', 'journalctl -b ' + before + ' -k --no-pager -o json', 25)
        addresses = re.findall(r'\bwlp1s0\s+inet (\d+\.\d+\.\d+\.\d+)/', sec['network'])
        require(len(addresses) == 1, 'new-boot Wi-Fi address missing/ambiguous')
        wifi = r.command('final-wifi', ['env', 'GTS9_DEVICE=' + addresses[0], p.SSH, 'cat /proc/sys/kernel/random/boot_id'], 15)[0]
        require(e.canonical_boot_id(wifi) == boot, 'Wi-Fi boot mismatch')
        w = r.ps('final-windows-usb', p.PS_USB, 30)[0]
        require(not p.has_code43(w), 'Windows Code43')
        p.write_json(r.folder / 'summary.json', {'verdict': 'BASELINE_STARTUP_DIAGNOSTIC_COMPLETED', 'before_boot_id': before, 'boot_id': boot, 'wifi_address': addresses[0], 'samples': samples, 'observation_seconds': samples[-1]['elapsed_s'], 'startup': startup, 'high_power_admission': False, 'Test269_live_execution': False, 'fresh_active_100ms_API_qualified': False, 'independent_ADC_calibration': False, 'PPS': False, 'pump_ON': False, 'flash': False, 'normal_reboots': 1})
    except Exception as exc:
        r.adb('first-failure-kernel-json', 'journalctl -b -k --no-pager -o json', 25, False)
        r.adb('first-failure-state', CURRENT_CMD, 20, False)
        p.write_json(r.folder / 'summary.json', {'verdict': 'STOP_BASELINE_STARTUP_DIAGNOSTIC', 'error': str(exc), 'boot_id': boot, 'samples': samples, 'reboot_sent': reboot_sent, 'flash': False, 'PPS': False, 'pump_ON': False, 'high_power_admission': False})
        raise

if __name__ == '__main__':
    main()
