#!/usr/bin/env python3
"""Read-only current accepted Test255 identity and rescue gates for Test258."""
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e

A = Path(__file__).resolve().parent
OLD = A.parent / 'test-255-sm5714-fixed-pd'
phase = sys.argv[1] if len(sys.argv) > 1 else 'preflight'
if phase not in {'preflight', 'baseline-diagnosis', 'normal-preflight'}:
    raise SystemExit('invalid evidence phase')
if (A / phase).exists():
    raise SystemExit('refusing evidence overwrite')
r = p.Recorder(A / phase)
p.SERIAL = 'gts9wifi-0001'
checks = {}


def check(name, valid):
    checks[name] = bool(valid)


def remote(name, script, timeout=20):
    return r.ssh(name, script, timeout)[0]


try:
    state = remote('initial-boot', 'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime')
    boot = e.canonical_boot_id(state.splitlines()[0])
    uptime = float(state.splitlines()[1].split()[0])
    remote('uname', 'uname -a')
    remote('boot-history', 'journalctl --list-boots --no-pager')
    cmdline = remote('cmdline', 'cat /proc/cmdline')
    check('cmdline', cmdline.strip() == (OLD / 'attempt-01/preflight/cmdline.txt').read_text().strip())
    config = remote('embedded-config', 'zcat /proc/config.gz', 30)
    check('embedded-config', hashlib.sha256(config.encode()).hexdigest() == hashlib.sha256((OLD / 'validation/candidate.config').read_bytes()).hexdigest())
    notes = remote('notes-hash', 'sha256sum /sys/kernel/notes').split()[0]
    check('notes', notes == hashlib.sha256((ROOT / 'out/kernel-sm5714-stage2/kernel-notes.bin').read_bytes()).hexdigest())
    parts = p.parse_hashes(remote('partitions', 'set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done', 90), '/dev/disk/by-partlabel/')
    check('partitions', parts == json.loads((OLD / 'attempt-01/install/summary.json').read_text())['partitions'])
    prefix = '/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/'
    modules = p.parse_hashes(remote('current-modules', f'find {prefix} -type f -exec sha256sum {{}} +', 90), prefix)
    check('181-current-modules', len(modules) == 181 and modules == json.loads((OLD / 'validation/module-hashes.json').read_text()))
    for name, directory in [('test254', '.gts9-test255-original'), ('test252', '.gts9-test254-original'), ('test249', '.gts9-test252-original')]:
        prefix = '/usr/lib/modules/' + directory + '/'
        actual = p.parse_hashes(remote('rollback-' + name, f'find {prefix} -type f -exec sha256sum {{}} +', 90), prefix)
        expected = p.parse_hashes((OLD / f'attempt-01/postboot/modules-{name}.txt').read_text(), prefix)
        check('181-rollback-' + name, len(actual) == 181 and actual == expected)
    expected = p.parse_hashes((OLD / 'attempt-01/preflight/protected-settings.txt').read_text(), '/')
    actual = p.parse_hashes(remote('protected-settings', 'set -e; sha256sum ' + ' '.join(shlex.quote('/' + n) for n in expected), 30), '/')
    check('protected-settings', actual == expected)
    remote('dcc', 'set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; if systemctl is-active --quiet serial-getty@hvc0.service; then exit 1; fi; echo DCC-absent')
    failed = remote('failed-units', 'systemctl --failed --no-legend --plain --no-pager')
    check('failed-units', not failed.strip())
    raw = remote('battery', 'cat /sys/class/power_supply/sm5714-battery/uevent')
    battery = dict(line.split('=', 1) for line in raw.splitlines() if line.startswith('POWER_SUPPLY_'))
    check('battery', battery['POWER_SUPPLY_HEALTH'] == 'Good' and battery['POWER_SUPPLY_PRESENT'] == '1' and 5 <= int(battery['POWER_SUPPLY_CAPACITY']) < 80 and 200 <= int(battery['POWER_SUPPLY_TEMP']) < 380 and 3500000 <= int(battery['POWER_SUPPLY_VOLTAGE_NOW']) < 4300000)
    remote('power-supplies', 'for f in /sys/class/power_supply/*/uevent; do echo "$f"; cat "$f"; done')
    role = remote('typec', 'for f in power_role data_role power_operation_mode; do echo "$f"; cat /sys/class/typec/port0/$f; done')
    check('sink-device', '[sink]' in role and '[device]' in role)
    remote('usb-services', 'ip -4 -o addr show; for f in /sys/class/udc/*/state; do echo "$f"; cat "$f"; done; systemctl is-active ssh gts9-adbd gts9-usb-acm')
    check('ADB', p.SERIAL in r.host_adb('adb-devices', 'devices', '-l')[0])
    check('ADB-shell', e.canonical_boot_id(r.adb('adb-boot', 'cat /proc/sys/kernel/random/boot_id')[0].strip()) == boot)
    wifi = remote('wifi-address', 'ip -4 -o addr show dev wlp1s0')
    wifi = re.search(r'\binet (\d+\.\d+\.\d+\.\d+)/', wifi).group(1)
    check('Wi-Fi-SSH', e.canonical_boot_id(r.command('wifi-boot', ['env', 'GTS9_DEVICE=' + wifi, p.SSH, 'cat /proc/sys/kernel/random/boot_id'])[0].strip()) == boot)
    r.ps('windows-pnp', 'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match "VID_0525" -or $_.FriendlyName -match "Descriptor|NCM|ADB" } | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 3', timeout=30)
    raw = r.ps('windows-code43', 'Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -eq 43 } | Select-Object Name,PNPDeviceID,ConfigManagerErrorCode | ConvertTo-Json', timeout=30)[0]
    check('no-Code43', not raw.strip())
    r.ps('windows-network', 'Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,ifIndex | ConvertTo-Json', timeout=30)
    journal = remote('kernel-json', 'journalctl -b -k --no-pager -o json', 90)
    remote('kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 90)
    baseline = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
    known = {x['MESSAGE'] for x in map(json.loads, baseline.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}
    scan = e.inspect_journal(journal, boot, known, accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True, observed_uptime=uptime)
    p.write_json(r.folder / 'kernel-scan.json', scan)
    check('kernel-health', not scan['fault_counts'] and not scan['suspects'])
    check('same-boot', e.canonical_boot_id(remote('final-boot', 'cat /proc/sys/kernel/random/boot_id').strip()) == boot)
    if not all(checks.values()):
        raise p.CaptureError('failed gates: ' + ','.join(k for k, v in checks.items() if not v))
    p.write_json(r.folder / 'summary.json', {'verdict': 'read-only accepted Test255 software/rescue preflight passed', 'checks': checks, 'boot_id': boot, 'partitions': parts, 'config_sha256': hashlib.sha256(config.encode()).hexdigest(), 'notes_sha256': notes, 'wifi': wifi, 'battery': battery, 'device_writes': False})
    print('Passed', len(checks), 'preflight gates', boot, flush=True)
except Exception as exc:
    p.write_json(r.folder / 'summary.json', {'verdict': 'STOP before device writes', 'checks': checks, 'error': str(exc), 'device_writes': False})
    raise
