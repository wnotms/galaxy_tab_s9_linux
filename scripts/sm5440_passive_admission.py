#!/usr/bin/env python3
"""Read-only ADB-first passive admission. Never reboot, retry or change USB."""
import argparse
import json
from pathlib import Path
import re
import sys

import production_reboot_stability as p
import production_stability_evidence as e
from sm5440_passive_evidence import passive_errors

PS_NCM_STATE = r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$nic=@(Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'NCM' })
[ordered]@{
  adapters=@($nic | Select-Object Name,ifIndex,InterfaceDescription,Status,PnPDeviceID)
  addresses=@(foreach($n in $nic){Get-NetIPAddress -InterfaceIndex $n.ifIndex -AddressFamily IPv4 |
    Select-Object InterfaceIndex,IPAddress,AddressState,PrefixLength})
  routes=@(foreach($n in $nic){Get-NetRoute -InterfaceIndex $n.ifIndex -AddressFamily IPv4 |
    Select-Object InterfaceIndex,DestinationPrefix,NextHop,RouteMetric})
  code43=@(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -eq 43 } |
    Select-Object Name,PNPDeviceID,ConfigManagerErrorCode)
} | ConvertTo-Json -Depth 5 -Compress
'''


def require(value, reason):
    if not value:
        raise p.CaptureError(reason)


def startup_evidence(raw, boot):
    """Require retained first event AND bounded completion; no blanket whitelist."""
    require(bool(raw.strip()), 'empty startup journal')
    events, pending, confirmed = [], [], []
    for line in raw.splitlines():
        row = json.loads(line)
        require(e.canonical_boot_id(row['_BOOT_ID']) == boot, 'journal boot mismatch')
        msg = row['MESSAGE']
        if not msg.startswith('sm5440-passive '):
            continue
        stamp = int(row['_SOURCE_BOOTTIME_TIMESTAMP'])
        if 'passive fault bitmap=' in msg:
            match = re.search(r'passive fault bitmap=(0x[0-9a-f]+) INT=.* STATUS=.* ADC=', msg)
            require(match is not None, 'missing raw passive fault provenance')
            require(int(match[1], 16) == 0x80, 'non-REVBLK passive fault')
            events.append(stamp)
        if msg.endswith('passive startup REVBLK awaiting two fresh confirmations'):
            pending.append(stamp)
        if msg.endswith('passive startup REVBLK confirmed inactive; event retained'):
            confirmed.append(stamp)
        require('passive ADC fault' not in msg and 'startup confirmation failed' not in msg,
                'passive conversion/startup failed')
    if events or pending or confirmed:
        require(len(events) == len(pending) == len(confirmed) == 1,
                'missing/repeated startup event or confirmation')
        require(0 <= pending[0] <= events[0] < confirmed[0] <= pending[0] + 5_000_000,
                'startup confirmation order/deadline')
        return {'classification': 'confirmed-inactive-startup-latch',
                'pending_source_us': pending[0], 'event_source_us': events[0],
                'confirmation_source_us': confirmed[0], 'warning_retained': True}
    return {'classification': 'no-startup-event', 'warning_retained': False}


def properties(text):
    return dict(x.split('=', 1) for x in text.splitlines() if x.startswith('POWER_SUPPLY_'))


def admit(rec, boot_id, config_sha256, notes_sha256, known_messages=()):
    """Fail first; ADB evidence is saved before any Windows or SSH probe."""
    boot = e.canonical_boot_id(boot_id)
    identity = rec.adb('identity', 'set -e; cat /proc/sys/kernel/random/boot_id; '
                       'cat /proc/uptime; zcat /proc/config.gz | sha256sum; '
                       'sha256sum /sys/kernel/notes', 20)[0].splitlines()
    require(len(identity) == 4 and e.canonical_boot_id(identity[0]) == boot, 'candidate boot identity')
    require(identity[2].split()[0] == config_sha256 and identity[3].split()[0] == notes_sha256,
            'candidate config/notes identity')
    raw = rec.adb('kernel-json', 'journalctl -b -k --no-pager -o json', 25)[0]
    supplies = rec.adb('health', 'set -e; echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent; '
                       'echo @@passive; cat /sys/class/power_supply/sm5440-passive/uevent; '
                       'echo @@power-role; cat /sys/class/typec/port0/power_role; '
                       'echo @@data-role; cat /sys/class/typec/port0/data_role; '
                       'echo @@failed; systemctl --failed --plain --no-legend --no-pager; '
                       'echo @@boot; cat /proc/sys/kernel/random/boot_id', 20)[0]
    chunks = re.split(r'^@@([^\n]+)\n', supplies, flags=re.M)
    sections = dict(zip(chunks[1::2], chunks[2::2]))
    require(e.canonical_boot_id(sections['boot']) == boot, 'health capture crossed reboot')
    errors = passive_errors(properties(sections['battery']), properties(sections['passive']),
                            sections['power-role'], sections['data-role'])
    require(not errors, '; '.join(errors))
    require(not sections['failed'].strip(), 'systemd failed unit')
    scan = e.inspect_journal(raw, boot, set(known_messages), accepted_startup_variants=True,
                             startup_iova_range=(0xb8000000, 0xbab00000),
                             accepted_qca_cycles=True, observed_uptime=float(identity[1].split()[0]))
    p.write_json(rec.folder / 'kernel-scan.json', scan)
    require(not scan['fault_counts'] and not scan['suspects'], 'kernel fault/suspect')
    startup = startup_evidence(raw, boot)
    p.write_json(rec.folder / 'startup-evidence.json', startup)
    # Persist topology before the first connection: WSL mirroring/APIPA readiness
    # is separate from tablet usb0/sshd and from Windows adapter enumeration.
    try:
        rec.command('wsl-route', ['ip', '-j', 'route', 'get', '169.254.42.1'], required=False)
        rec.command('wsl-addresses', ['ip', '-j', '-4', 'addr', 'show'], required=False)
        text, status = rec.ps('windows-topology', PS_NCM_STATE, timeout=30, required=False)
        require(status == 0, 'Windows topology capture failed')
        topology = json.loads(text)
        require(isinstance(topology.get('code43'), list) and not topology['code43'], 'Windows Code43/missing evidence')
        text, status = rec.ps('ncm-bound-banner', p.PS_NCM_BOUND_BANNER, timeout=20, required=False)
        bound = json.loads(text) if text.strip() else {}
        require(status == 0 and bound.get('ok') is True, 'Windows NCM bound banner unavailable')
        text, status = rec.ssh('ncm-auth', 'cat /proc/sys/kernel/random/boot_id', 15, required=False)
        require(status == 0, 'NCM authentication failed; first failure retained; no retry')
        require(e.canonical_boot_id(text) == boot, 'NCM boot attribution')
    except Exception:
        # Also preserve tablet-side state for a failed Windows bound probe or
        # Code43, not just an authenticated-SSH timeout. Keep the first error.
        rec.adb('ncm-failure-device', 'cat /proc/sys/kernel/random/boot_id; '
                'ip -4 -o addr; systemctl is-active ssh gts9-adbd gts9-usb-acm; '
                'echo @@kernel; journalctl -b -k --no-pager -o json',
                25, required=False)
        raise
    return {'verdict': 'ADB-first passive admission passed', 'boot_id': boot,
            'startup': startup, 'ncm': 'authenticated', 'transport_retries': 0,
            'device_configuration_changed': False, 'physical_window_completed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('boot-id', 'config-sha256', 'notes-sha256', 'out'):
        parser.add_argument('--' + arg, required=True)
    parser.add_argument('--known-journal', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(args.out)
    require(not folder.exists(), 'never overwrite admission evidence')
    rec = p.Recorder(folder)
    known = {r['MESSAGE'] for r in map(json.loads, args.known_journal.read_text().splitlines())
             if int(r.get('PRIORITY', 7)) <= 3}
    try:
        result = admit(rec, args.boot_id, args.config_sha256, args.notes_sha256, known)
    except Exception as exc:
        result = {'verdict': 'STOP first non-clean admission', 'error': str(exc),
                  'transport_retries': 0, 'physical_window_completed': False}
        p.write_json(folder / 'summary.json', result)
        print(json.dumps(result), flush=True)
        return 1
    p.write_json(folder / 'summary.json', result)
    print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
