#!/usr/bin/env python3
"""30s fixed9V snapshot endpoint after owner confirms charger attachment."""
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
from sm5440_passive_admission import startup_evidence
from snapshot_gate import validate_snapshot

A = Path(__file__).resolve().parent
accepted = json.loads((A / 'observation/summary.json').read_text())
assert accepted['verdict'].endswith('passed')
boot = accepted['boot_id']
package = json.loads((A / 'PACKAGE.json').read_text())
assert not (A / 'pd-observation').exists()
r = p.Recorder(A / 'pd-observation')
# DHCP may change at the candidate reboot. Use the already verified postboot
# address; never reuse the original Test260 preflight address.
wifi_match = re.search(r'\binet (\d+\.\d+\.\d+\.\d+)/',
                       (A / 'observation/final-wifi-address.txt').read_text())
assert wifi_match is not None, 'accepted candidate Wi-Fi address missing'
wifi = wifi_match.group(1)
samples = []
known_file = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
known = {x['MESSAGE'] for x in map(json.loads, known_file.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}


def ssh(name, command, timeout=20):
    return r.command(name, ['env', 'GTS9_DEVICE=' + wifi, p.SSH, command], timeout)[0]


def require(value, reason):
    if not value:
        raise p.CaptureError(reason)


def properties(text):
    return dict(x.split('=', 1) for x in text.splitlines() if x.startswith('POWER_SUPPLY_'))


def kernel(name):
    raw = ssh(name, 'journalctl -b -k --no-pager -o json', 25)
    uptime = float(ssh(name + '-uptime', 'cat /proc/uptime').split()[0])
    scan = e.inspect_journal(raw, boot, known, accepted_startup_variants=True,
                            startup_iova_range=(0xb8000000, 0xbab00000),
                            accepted_qca_cycles=True, observed_uptime=uptime)
    p.write_json(r.folder / (name + '-scan.json'), scan)
    require(not scan['fault_counts'] and not scan['suspects'], 'kernel fault/suspect')
    require(startup_evidence(raw, boot) == accepted['startup'], 'new/repeated startup event')


try:
    raw = ssh('identity', 'set -e; cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes').splitlines()
    require(e.canonical_boot_id(raw[0]) == boot, 'boot changed')
    require(raw[1].split()[0] == package['artifacts']['out/kernel-x710-263-passive/config']['sha256'], 'config')
    require(raw[2].split()[0] == package['artifacts']['out/kernel-x710-263-passive/kernel-notes.bin']['sha256'], 'notes')
    kernel('initial-kernel-json')
    start = time.monotonic()
    initial_protection = None
    while True:
        raw = ssh(f'sample-{len(samples):03}', 'set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; '
                  'echo @@before; cat /proc/uptime; echo @@snapshot; cat /sys/kernel/debug/sm5440-0-0063/snapshot; '
                  'echo @@after; cat /proc/uptime; echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent; '
                  'echo @@usb; cat /sys/class/power_supply/sm5714-usb/uevent; '
                  'echo @@tcpm; cat /sys/class/power_supply/tcpm-source-psy-3-0033/uevent; '
                  'echo @@passive; cat /sys/class/power_supply/sm5440-passive/uevent; '
                  'echo @@roles; cat /sys/class/typec/port0/power_role /sys/class/typec/port0/data_role; '
                  'echo @@failed; systemctl --failed --plain --no-legend --no-pager')
        chunks = re.split(r'^@@([^\n]+)\n', raw, flags=re.M)
        sections = dict(zip(chunks[1::2], chunks[2::2]))
        require(e.canonical_boot_id(sections['boot']) == boot, 'unexpected reboot')
        snapshot = validate_snapshot(sections['snapshot'], 9)
        b, usb, tcpm, passive = [properties(sections[k]) for k in ('battery', 'usb', 'tcpm', 'passive')]
        require(b['POWER_SUPPLY_HEALTH'] == 'Good' and b['POWER_SUPPLY_PRESENT'] == '1' and b['POWER_SUPPLY_STATUS'] == 'Charging', 'battery health/status')
        require(5 <= int(b['POWER_SUPPLY_CAPACITY']) < 80 and 3500000 <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) < 4300000 and 0 <= int(b['POWER_SUPPLY_TEMP']) < 420 and int(b['POWER_SUPPLY_CURRENT_NOW']) > 0, 'battery safety/current')
        require(tcpm['POWER_SUPPLY_ONLINE'] == '1' and int(tcpm['POWER_SUPPLY_VOLTAGE_NOW']) == 9000000 and 0 < int(tcpm['POWER_SUPPLY_CURRENT_MAX']) <= 1500000 and '[PD]' in tcpm['POWER_SUPPLY_USB_TYPE'], 'fixed9V contract')
        require(usb['POWER_SUPPLY_ONLINE'] == '1' and 0 < int(usb['POWER_SUPPLY_INPUT_CURRENT_LIMIT']) <= 1500000 and '[PD]' in usb['POWER_SUPPLY_USB_TYPE'], 'conservative switching input')
        require(passive['POWER_SUPPLY_HEALTH'] == 'Good' and passive['POWER_SUPPLY_STATUS'] == 'Not charging' and passive['POWER_SUPPLY_ONLINE'] == '1' and int(passive['POWER_SUPPLY_CURRENT_NOW']) == 0, 'passive OFF')
        require(sections['roles'].splitlines() == ['[sink]', '[device]'] and not sections['failed'].strip(), 'roles/systemd')
        protection = {k: snapshot[k] for k in ('sample_cntl2', 'sample_vbuscntl', 'sample_vbatcntl', 'sample_prtncntl')}
        reference = accepted['samples'][0]['snapshot']
        require(all(protection[k] == reference[k] for k in protection), 'protection changed since PC')
        if samples:
            require(int(b['POWER_SUPPLY_TEMP']) - int(samples[0]['battery']['POWER_SUPPLY_TEMP']) < 100, 'abnormal pack heating')
        elapsed = time.monotonic() - start
        samples.append(dict(elapsed_s=round(elapsed, 3), snapshot=snapshot, battery=b, usb=usb, tcpm=tcpm, passive=passive, acquisition_begin=sections['before'].strip(), acquisition_end=sections['after'].strip()))
        print('PD snapshot', round(elapsed, 1), 's', snapshot['sample_vbus_uv'], b['POWER_SUPPLY_TEMP'], flush=True)
        if elapsed >= 30:
            break
        time.sleep(min(5, 30 - elapsed))
    kernel('final-kernel-json')
    require(e.canonical_boot_id(ssh('final-boot', 'cat /proc/sys/kernel/random/boot_id')) == boot, 'final boot changed')
    p.write_json(r.folder / 'summary.json', dict(verdict='fixed9V snapshot endpoint passed', boot_id=boot, samples=samples, observation_seconds=samples[-1]['elapsed_s'], pump_on=False, pps_requested=False, independently_calibrated=False))
except Exception as exc:
    try:
        ssh('first-failure-kernel-json', 'journalctl -b -k --no-pager -o json', 25)
    finally:
        p.write_json(r.folder / 'summary.json', dict(verdict='STOP first non-clean fixed9V snapshot', error=str(exc), boot_id=boot, samples=samples, rollback_required=True, pump_on=False, pps_requested=False))
    raise
