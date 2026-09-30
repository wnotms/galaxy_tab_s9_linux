#!/usr/bin/env python3
"""Bounded, read-only NCM readiness and one authenticated connection (WSL mirrored)."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import sys
import time

import production_reboot_stability as p
from production_stability_evidence import canonical_boot_id

# Query all IPv4 objects and filter afterwards: querying a specific newly
# enumerated NIC with no address can raise ObjectNotFound instead of returning
# an empty address list. Missing APIPA is a readiness state, not capture failure.
PS_NCM_STATE = r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$nic=@(Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'NCM' })
$indices=@($nic | ForEach-Object { [int]$_.ifIndex })
[ordered]@{
  adapters=@($nic | Select-Object Name,ifIndex,InterfaceDescription,Status,PnPDeviceID)
  addresses=@(Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $indices -contains $_.InterfaceIndex } |
    Select-Object InterfaceIndex,IPAddress,AddressState,PrefixLength)
  routes=@(Get-NetRoute -AddressFamily IPv4 |
    Where-Object { $indices -contains $_.InterfaceIndex } |
    Select-Object InterfaceIndex,DestinationPrefix,NextHop,RouteMetric)
  code43=@(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -eq 43 } |
    Select-Object Name,PNPDeviceID,ConfigManagerErrorCode)
} | ConvertTo-Json -Depth 5 -Compress
'''

TARGET = '169.254.42.1'
PNP = 'VID_0525&PID_A4A7&MI_00'


def topology_gate(windows, routes, addresses):
    """Return readiness/reason; malformed or ambiguous evidence is a hard stop."""
    for name in ('adapters', 'addresses', 'routes', 'code43'):
        if not isinstance(windows.get(name), list):
            raise p.CaptureError('missing Windows ' + name)
    if windows['code43']:
        raise p.CaptureError('Windows Code43; stop, do not repair USB')
    nics = [n for n in windows['adapters'] if PNP in str(n.get('PnPDeviceID') or '').upper()
            and 'NCM' in str(n.get('InterfaceDescription') or '').upper()]
    if len(nics) > 1:
        raise p.CaptureError('ambiguous production NCM adapters')
    if not nics or nics[0]['Status'] != 'Up':
        return {'ready': False, 'reason': 'Windows NCM not up'}
    nic = nics[0]
    ips = [a for a in windows['addresses'] if a['InterfaceIndex'] == nic['ifIndex']
           and a['AddressState'] in (4, 'Preferred')
           and ipaddress.IPv4Address(a['IPAddress']).is_link_local and a['PrefixLength'] == 16]
    if len(ips) > 1:
        raise p.CaptureError('ambiguous preferred NCM addresses')
    if not ips:
        return {'ready': False, 'reason': 'Windows NCM APIPA not preferred'}
    source = ips[0]['IPAddress']
    if source == TARGET:
        raise p.CaptureError('NCM host/device address conflict')
    if not isinstance(routes, list) or not isinstance(addresses, list):
        raise p.CaptureError('invalid WSL topology evidence')
    if len(routes) > 1:
        raise p.CaptureError('ambiguous WSL route')
    if not routes:
        return {'ready': False, 'reason': 'WSL NCM route not ready'}
    route = routes[0]
    if route.get('dst') != TARGET or route.get('gateway') or route.get('prefsrc') != source:
        return {'ready': False, 'reason': 'WSL route/source does not match NCM'}
    matches = [a for a in addresses if a['ifname'] == route.get('dev')]
    if len(matches) != 1:
        return {'ready': False, 'reason': 'WSL NCM interface not mirrored'}
    iface = matches[0]
    valid = [a for a in iface['addr_info'] if a.get('family') == 'inet'
             and a.get('local') == source and a.get('prefixlen') == 16
             and not a.get('tentative') and not a.get('dadfailed')]
    if not {'UP', 'LOWER_UP'}.issubset(iface['flags']) or not valid:
        return {'ready': False, 'reason': 'WSL NCM link/address not ready'}
    # A source address shared by another interface would not identify NCM.
    owners = [a['ifname'] for a in addresses if any(x.get('local') == source
              for x in a['addr_info'])]
    if owners != [iface['ifname']]:
        raise p.CaptureError('ambiguous WSL NCM source address')
    return {'ready': True, 'reason': 'Windows/WSL NCM path ready',
            'source_ipv4': source, 'wsl_interface': iface['ifname'],
            'windows_interface_index': nic['ifIndex']}


def wait_ready(rec, window=30, clock=time.monotonic, sleep=time.sleep):
    start = clock()
    samples = []
    while clock() - start < window:
        name = f'readiness-{len(samples) + 1:02d}'
        remaining = lambda: max(0.01, window - (clock() - start))
        text, status = rec.ps(name + '-windows', PS_NCM_STATE,
                              timeout=min(20, remaining()), required=False)
        if status != 0:
            raise p.CaptureError('Windows topology capture failed; no retry')
        windows = json.loads(text)
        route, rs = rec.command(name + '-route', ['ip', '-j', 'route', 'get', TARGET],
                                timeout=min(3, remaining()), required=False)
        addr, ads = rec.command(name + '-addresses', ['ip', '-j', '-4', 'addr', 'show'],
                               timeout=min(3, remaining()), required=False)
        if ads != 0 or rs not in (0, 2):
            raise p.CaptureError('WSL topology capture failed; no retry')
        # iproute2 uses status 2 for a missing route; the raw stderr is retained.
        gate = topology_gate(windows, json.loads(route) if rs == 0 else [], json.loads(addr))
        elapsed = round(clock() - start, 3)
        samples.append(dict(gate, elapsed_seconds=elapsed))
        p.write_json(rec.folder / 'readiness.json', samples)
        if clock() - start >= window:
            break
        if gate['ready']:
            return dict(gate, readiness_seconds=elapsed, samples=len(samples),
                        delayed_readiness=any(not x['ready'] for x in samples))
        sleep(min(1, remaining()))
    raise p.CaptureError(f'NCM host readiness deadline ({window}s); no SSH attempted')


def connect(rec, key, window=30):
    """Only metadata is polled. First SSH failure always stops, never retries."""
    if not Path(key).is_file():
        raise p.CaptureError('missing existing SSH key')
    before, status = rec.adb('before-identity',
                             'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime',
                             timeout=10, required=False)
    if status != 0:
        raise p.CaptureError('ADB identity unavailable; no NCM attempt')
    boot = canonical_boot_id(before.splitlines()[0])
    ready = wait_ready(rec, window)
    argv = ['ssh', '-F', '/dev/null', '-4', '-T', '-b', ready['source_ipv4'],
            '-i', str(key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'ConnectionAttempts=1', '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR', 'root@' + TARGET,
            'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime']
    text, status = rec.command('ncm-auth', argv, timeout=15, required=False)
    if status != 0:
        raise p.CaptureError('first NCM SSH failed; no retry')
    if canonical_boot_id(text.splitlines()[0]) != boot:
        raise p.CaptureError('ADB/NCM boot mismatch; stop')
    return dict(ready, verdict='NCM authenticated on verified host path',
                boot_id=boot, ssh_attempts=1, device_configuration_changed=False)


def failure_evidence(rec):
    # Diagnostic probes after STOP never turn the first failure into a pass.
    actions = [
        lambda: rec.adb('failure-device', 'cat /proc/sys/kernel/random/boot_id; '
                       'ip -4 -o addr; systemctl is-active ssh gts9-adbd gts9-usb-acm; '
                       'journalctl -b -k -n 100 --no-pager', timeout=15, required=False),
    ]
    if (rec.folder / 'ncm-auth.command.json').exists():
        actions.append(lambda: rec.ps('failure-windows-banner', p.PS_NCM_BOUND_BANNER,
                                     timeout=20, required=False))
    for action in actions:
        try:
            action()
        except Exception as exc:
            with (rec.folder / 'failure-capture-errors.txt').open('a') as out:
                out.write(str(exc) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--wait', type=float, default=30)
    parser.add_argument('--key', type=Path,
                        default=Path(os.environ.get('GTS9_SSH_KEY', str(Path.home() / '.ssh/gts9_ed25519'))))
    args = parser.parse_args()
    if not 0 < args.wait <= 60:
        parser.error('--wait must be >0 and <=60 seconds')
    if args.out.exists():
        parser.error('refusing to overwrite evidence directory')
    rec = p.Recorder(args.out)
    # This helper operates on Debian, never a recovery-mode serial.
    p.SERIAL = 'gts9wifi-0001'
    try:
        result = connect(rec, args.key, args.wait)
        code = 0
    except Exception as exc:
        result = {'verdict': 'STOP', 'error': str(exc), 'ssh_retries': 0,
                  'device_configuration_changed': False}
        p.write_json(rec.folder / 'summary.json', result)
        failure_evidence(rec)
        code = 1
    p.write_json(rec.folder / 'summary.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
