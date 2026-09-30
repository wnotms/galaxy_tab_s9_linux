#!/usr/bin/env python3
"""Read-only fixed-PD battery telemetry with the SM5440 passive monitor OFF."""
import argparse
import json
from pathlib import Path
import re
import shlex
import sys
import time

import production_reboot_stability as p
import production_stability_evidence as e
import sm5714_pd_telemetry as telemetry
from sm5440_passive_admission import startup_evidence

COMMAND = telemetry.SAMPLE_COMMAND + '''
echo @@passive; cat /sys/class/power_supply/sm5440-passive/uevent
echo @@failed; systemctl --failed --plain --no-legend --no-pager
'''


def parse(raw):
    # Splitting off the incremental journal leaves an empty @@failed at EOF.
    # That is a captured empty failed-unit list, not a missing section.
    parts = re.split(r'^@@([^\n]+)(?:\n|\Z)', raw, flags=re.M)
    sample = telemetry.parse_sample(parts[0])
    sections = dict(zip(parts[1::2], parts[2::2]))
    monitor = dict(x.split('=', 1) for x in sections['passive'].splitlines()
                   if x.startswith('POWER_SUPPLY_'))
    sample.update(passive_health=monitor['POWER_SUPPLY_HEALTH'],
                  passive_status=monitor['POWER_SUPPLY_STATUS'],
                  passive_online=int(monitor['POWER_SUPPLY_ONLINE']),
                  passive_vbus_uv=int(monitor['POWER_SUPPLY_VOLTAGE_NOW']),
                  passive_ibus_ua=int(monitor['POWER_SUPPLY_CURRENT_NOW']),
                  passive_die_deciC=int(monitor['POWER_SUPPLY_TEMP']),
                  failed_units=sections['failed'].strip())
    return sample


def safety(sample, boot, previous=(), attached=False):
    error = telemetry.assess(sample, boot, previous, attached)
    if error:
        return error
    if not 5 <= sample['battery_soc'] < 80 or not 3500000 <= sample['battery_voltage_uv'] < 4300000:
        return 'battery-outside-bringup-range'
    if not 0 <= sample['battery_temp_deciC'] < 420:
        return 'battery-temperature-bringup-limit'
    if sample['failed_units']:
        return 'systemd-failed-unit'
    if sample['passive_health'] != 'Good' or sample['passive_status'] != 'Not charging':
        return 'passive-fault-or-unavailable-OFF-sample'
    if sample['passive_ibus_ua'] != 0:
        return 'passive-current-not-zero'
    if not 225 <= sample['passive_die_deciC'] < 420:
        return 'passive-die-temperature'
    if not 0 <= sample['passive_vbus_uv'] <= 9500000:
        return 'reported-VBUS-outside-bringup-limit'
    return None


def charger_ready(sample):
    """PC SDP is never mistaken for the owner's independent charger."""
    voltage = sample['contract_voltage_uv']
    tolerance = 500000
    return (sample['usb_online'] == sample['tcpm_online'] == sample['passive_online'] == 1
            and sample['usb_type'] in {'C', 'PD', 'DCP'}
            and sample['tcpm_type'] in {'C', 'PD'}
            and voltage in {5000000, 9000000}
            and sample['contract_current_ua'] >= 100000
            and abs(sample['passive_vbus_uv'] - voltage) <= tolerance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--wifi', required=True)
    parser.add_argument('--boot', required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('never overwrite evidence')
    rec = p.Recorder(args.out)
    argv = ['env', 'GTS9_DEVICE=' + args.wifi, p.SSH]
    source = p.ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
    known = {r['MESSAGE'] for r in map(json.loads, source.read_text().splitlines())
             if int(r.get('PRIORITY', 7)) <= 3}
    all_samples, charging = [], []
    window = first_charger = None
    started = time.monotonic()

    def journal(raw, name, uptime, complete):
        rows = '\n'.join(x for x in raw.splitlines() if x.startswith('{'))
        if rows:
            scan = e.inspect_journal(rows, args.boot, known, require_start=complete,
                     accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
                     accepted_qca_cycles=True, observed_uptime=uptime)
            p.write_json(rec.folder / (name + '-scan.json'), scan)
            if scan['fault_counts'] or scan['suspects']:
                raise RuntimeError('kernel-fault-or-suspect')
            if not complete and any('sm5440-passive ' in r['MESSAGE'] and
               ('fault' in r['MESSAGE'] or 'startup' in r['MESSAGE'])
               for r in map(json.loads, rows.splitlines())):
                raise RuntimeError('new-passive-fault-or-startup-event')
        elif complete:
            raise RuntimeError('empty-complete-kernel-journal')
        cursors = [x.removeprefix('-- cursor: ') for x in raw.splitlines() if x.startswith('-- cursor: ')]
        if len(cursors) > 1 or (complete and len(cursors) != 1):
            raise RuntimeError('missing-or-ambiguous-journal-cursor')
        return rows, cursors[0] if cursors else None

    try:
        # First sample and complete journal qualify this unchanged running boot
        # before the owner is asked to remove PC USB/attach the charger.
        sample = parse(rec.command('initial-state', argv + [COMMAND], 15)[0])
        error = safety(sample, args.boot)
        if error or not 200 <= sample['battery_temp_deciC'] < 380:
            raise RuntimeError(error or 'initial-pack-temperature')
        full = rec.command('initial-kernel', argv + ['journalctl -b -k --no-pager -o json --show-cursor'], 25)[0]
        rows, cursor = journal(full, 'initial-kernel', sample['uptime_seconds'], True)
        startup = startup_evidence(rows, args.boot)
        p.write_json(rec.folder / 'initial-startup.json', startup)
        print('ARMED: Wi-Fi capture ready; waiting for independent charger, pump remains OFF', flush=True)
        while True:
            tick = time.monotonic()
            name = f'sample-{len(all_samples):03d}'
            command = COMMAND + '\necho @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor=' + shlex.quote(cursor)
            raw = rec.command(name, argv + [command], 15)[0]
            sections = raw.split('\n@@kernel\n', 1)
            if len(sections) != 2:
                raise RuntimeError('missing-incremental-kernel-evidence')
            sample = parse(sections[0])
            error = safety(sample, args.boot, all_samples, window is not None)
            sample['elapsed_seconds'] = round(tick - started, 3)
            all_samples.append(sample)
            p.write_json(rec.folder / 'samples.json', all_samples)
            if error:
                raise RuntimeError(error)
            _, next_cursor = journal(sections[1], name, sample['uptime_seconds'], False)
            if next_cursor:
                cursor = next_cursor
            is_charger = sample['usb_online'] and sample['usb_type'] in {'C', 'PD', 'DCP'}
            if is_charger and first_charger is None:
                first_charger = tick
            ready = charger_ready(sample)
            if first_charger is not None and not ready and tick - first_charger > 45:
                raise RuntimeError('charger-contract-or-reported-VBUS-not-ready-within-45s')
            if ready and window is None:
                window = tick
                print('CHARGE_WINDOW_STARTED', sample['contract_voltage_uv'], flush=True)
            if window is not None:
                if not ready:
                    raise RuntimeError('charging-contract-or-reported-VBUS-changed')
                charging.append(sample)
                if len(charging) % 12 == 1:
                    print('Charge', round(tick - window, 1), 's;', sample['battery_net_power_w'],
                          'W net battery;', sample['battery_temp_deciC'] / 10, 'C', flush=True)
                if tick - window >= 300:
                    break
            elif tick - started > 600:
                raise RuntimeError('charger-not-connected-within-600s')
            time.sleep(max(.05, 5 - (time.monotonic() - tick)))
        full = rec.command('final-kernel', argv + ['journalctl -b -k --no-pager -o json --show-cursor'], 25)[0]
        rows, _ = journal(full, 'final-kernel', sample['uptime_seconds'], True)
        if startup_evidence(rows, args.boot) != startup:
            raise RuntimeError('startup-evidence-changed')
        stats = telemetry.summarize(charging)
        if stats['positive_current_samples'] * 2 <= len(charging) or stats['soc_end'] < stats['soc_start']:
            raise RuntimeError('charging-trend-suspect')
        result = dict(verdict='PASS bounded fixed-PD battery telemetry; passive pump OFF',
                      boot_id=e.canonical_boot_id(args.boot), observation_seconds=round(tick - window, 3),
                      statistics=stats, startup=startup, pps_requested=False, pump_on=False,
                      device_configuration_writes=False, actual_vbus_independently_calibrated=False)
    except Exception as exc:
        result = dict(verdict='STOP first non-clean charging observation', error=str(exc),
                      boot_id=args.boot, samples=len(all_samples), pps_requested=False, pump_on=False)
        p.write_json(rec.folder / 'summary.json', result)
        print('STOP: disconnect charger; first evidence retained:', exc, flush=True)
        rec.command('first-failure-kernel', argv + ['journalctl -b -k --no-pager -o json'], 20, required=False)
        return 1
    p.write_json(rec.folder / 'summary.json', result)
    print('FIVE_MINUTE_FIXED_CHARGE_PASSED; unplug follow-up pending', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
