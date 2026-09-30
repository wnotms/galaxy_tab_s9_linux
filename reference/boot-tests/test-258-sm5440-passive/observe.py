#!/usr/bin/env python3
"""Read-only passive PC-USB observation; no PPS, pump or configuration writes."""
import hashlib
import json
import re
import shlex
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
from sm5440_passive_evidence import passive_errors

A = Path(__file__).resolve().parent
M = json.loads((A / 'ARTIFACTS.json').read_text())
BASE = json.loads((A / 'normal-preflight/summary.json').read_text())
assert not (A / 'observation').exists(), 'never overwrite/retry an observation'
r = p.Recorder(A / 'observation')
p.SERIAL = 'gts9wifi-0001'
boot = None
samples = []
known_file = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
known = {x['MESSAGE'] for x in map(json.loads, known_file.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}


def require(value, reason):
    if not value:
        raise p.CaptureError(reason)


def props(text):
    return dict(x.split('=', 1) for x in text.splitlines() if x.startswith('POWER_SUPPLY_'))


def journal(raw, name, uptime, previous=None):
    lines = raw.splitlines()
    data = '\n'.join(x for x in lines if not x.startswith('-- cursor:') and x != '-- No entries --')
    require(bool(data.strip()) or previous is not None, 'empty full kernel journal')
    if data.strip():
        scan = e.inspect_journal(data, boot, known, accepted_startup_variants=True,
                                 startup_iova_range=(0xb8000000, 0xbab00000),
                                 accepted_qca_cycles=True, observed_uptime=uptime)
        p.write_json(r.folder / (name + '-scan.json'), scan)
        require(not scan['fault_counts'] and not scan['suspects'], 'kernel fault/suspect: ' + name)
    cursor = [x[len('-- cursor: '):] for x in lines if x.startswith('-- cursor: ')]
    if not cursor and not data.strip() and previous is not None:
        require(all(not x.strip() or x == '-- No entries --' for x in lines), 'invalid incremental journal response')
        return previous
    require(len(cursor) == 1 and bool(cursor[0]), 'missing/ambiguous journal cursor')
    return cursor[0]


def transport(name):
    require(e.canonical_boot_id(r.adb(name + '-adb', 'cat /proc/sys/kernel/random/boot_id')[0]) == boot, 'ADB boot mismatch')
    require(e.canonical_boot_id(r.ssh(name + '-ncm', 'cat /proc/sys/kernel/random/boot_id')[0]) == boot, 'NCM boot mismatch')
    raw = r.ssh(name + '-wifi-address', 'ip -4 -o addr show dev wlp1s0')[0]
    ip = re.search(r'\binet (\d+\.\d+\.\d+\.\d+)/', raw)
    require(ip is not None, 'Wi-Fi address missing')
    require(e.canonical_boot_id(r.command(name + '-wifi', ['env', 'GTS9_DEVICE=' + ip.group(1), p.SSH, 'cat /proc/sys/kernel/random/boot_id'])[0]) == boot, 'Wi-Fi boot mismatch')
    raw = r.ps(name + '-windows', 'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match "VID_0525" } | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json; Write-Output "@@code43"; Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -eq 43 } | Select-Object Name,PNPDeviceID,ConfigManagerErrorCode | ConvertTo-Json; Write-Output "@@network"; Get-NetAdapter | Select-Object Name,InterfaceDescription,Status | ConvertTo-Json', timeout=30)[0]
    require('@@code43' in raw and '@@network' in raw, 'Windows evidence incomplete')
    require(not raw.split('@@code43', 1)[1].split('@@network', 1)[0].strip(), 'Windows Code43')


try:
    raw = r.ssh('identity', 'set -e; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; uname -a; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; cat /proc/cmdline', 30)[0]
    lines = raw.splitlines()
    boot = e.canonical_boot_id(lines[0]); uptime = float(lines[1].split()[0])
    require(boot != BASE['boot_id'], 'candidate boot ID unchanged')
    require(lines[3].split()[0] == M['artifacts']['out/kernel-x710-258-passive/config']['sha256'], 'candidate config mismatch')
    require(lines[4].split()[0] == M['artifacts']['out/kernel-x710-258-passive/kernel-notes.bin']['sha256'], 'candidate notes mismatch')
    normal = (A.parent / 'test-255-sm5714-fixed-pd/attempt-01/preflight/cmdline.txt').read_text().strip()
    require(lines[5].strip() == normal, 'candidate cmdline mismatch')
    full = r.ssh('initial-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 30)[0]
    require(full.strip() and any(x.startswith('{') for x in full.splitlines()), 'empty kernel journal')
    cursor = journal(full, 'initial-kernel', uptime)
    r.ssh('initial-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 30)
    require('passive SM5440 revision' in full, 'passive driver probe absent')
    r.ssh('dcc-and-driver', 'set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; ! systemctl is-active --quiet serial-getty@hvc0.service; readlink -f /sys/class/power_supply/sm5440-passive/device/driver; cat /sys/firmware/devicetree/base/soc@0/geniqup@9c0000/i2c@98c000/charger@63/status; echo; systemctl is-active ssh gts9-adbd gts9-usb-acm', 20)
    transport('initial')
    initial_die = None
    start = time.monotonic()
    while True:
        n = len(samples)
        script = ('set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@uptime; cat /proc/uptime; '
                  'echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent; '
                  'echo @@passive; cat /sys/class/power_supply/sm5440-passive/uevent; '
                  'echo @@power-role; cat /sys/class/typec/port0/power_role; '
                  'echo @@data-role; cat /sys/class/typec/port0/data_role; '
                  'echo @@failed; systemctl --failed --no-legend --plain --no-pager; '
                  'echo @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor=' + shlex.quote(cursor))
        raw = r.ssh(f'sample-{n:03}', script, 15)[0]
        chunks = re.split(r'^@@([^\n]+)\n', raw, flags=re.M)
        sections = dict(zip(chunks[1::2], chunks[2::2]))
        require(e.canonical_boot_id(sections['boot']) == boot, 'unexpected reboot')
        uptime = float(sections['uptime'].split()[0])
        b, monitor = props(sections['battery']), props(sections['passive'])
        errors = passive_errors(b, monitor, sections['power-role'], sections['data-role'])
        require(not errors, '; '.join(errors))
        require(not sections['failed'].strip(), 'systemd failed unit')
        die = int(monitor['POWER_SUPPLY_TEMP']); temp = int(b['POWER_SUPPLY_TEMP'])
        if initial_die is None:
            initial_die = die
            initial_pack = temp
            require(200 <= temp < 380, 'initial battery temperature outside entry limits')
        require(die - initial_die < 100 and temp - initial_pack < 100, 'abnormal temperature rise')
        cursor = journal(sections['kernel'], f'sample-{n:03}', uptime, previous=cursor)
        elapsed = time.monotonic() - start
        samples.append({'elapsed_s': round(elapsed, 3), 'uptime_s': uptime, 'battery': b, 'passive': monitor})
        if n % 6 == 0:
            require(e.canonical_boot_id(r.adb(f'sample-{n:03}-adb', 'cat /proc/sys/kernel/random/boot_id')[0]) == boot, 'ADB response/boot lost')
            print('Passive', round(elapsed, 1), 's; battery', temp / 10, 'C; reported VBUS', monitor['POWER_SUPPLY_VOLTAGE_NOW'], flush=True)
        if elapsed >= 150:
            break
        time.sleep(min(5, 150 - elapsed))
    full = r.ssh('final-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 30)[0]
    journal(full, 'final-kernel', uptime)
    r.ssh('final-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 30)
    prefix = '/usr/lib/modules/' + M['kernel_release'] + '/'
    actual = p.parse_hashes(r.ssh('candidate-modules', f'find {prefix} -type f -exec sha256sum {{}} +', 60)[0], prefix)
    require(len(actual) == 181 and actual == json.loads((A / 'validation/module-hashes.json').read_text()), 'module identity mismatch')
    transport('final')
    require(e.canonical_boot_id(r.ssh('final-boot', 'cat /proc/sys/kernel/random/boot_id')[0]) == boot, 'final boot mismatch')
    p.write_json(r.folder / 'summary.json', {'verdict': 'passive probe and bounded PC-USB observation passed', 'boot_id': boot, 'observation_seconds': samples[-1]['elapsed_s'], 'samples': samples, 'module_file_count': 181, 'offline_qualification_reused': 'f3a266b5', 'pump_on': False, 'pps_requested': False, 'independent_ADC_calibration': False, 'active_stage3_ready': False})
    print('PASS passive observation; active Stage3 remains NOT READY', flush=True)
except Exception as exc:
    try:
        r.ssh('first-failure-kernel-json', 'journalctl -b -k --no-pager -o json', 30, required=False)
        r.ssh('first-failure-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 30, required=False)
        r.adb('first-failure-supplies', 'for f in /sys/class/power_supply/*/uevent; do echo "$f"; cat "$f"; done', 20, required=False)
    finally:
        p.write_json(r.folder / 'summary.json', {'verdict': 'STOP first non-clean passive observation', 'error': str(exc), 'boot_id': boot, 'samples': samples, 'pump_on': False, 'pps_requested': False, 'rollback_required': True})
    raise
