#!/usr/bin/env python3
"""One registered read-only passive PC window; never deploy or repair hardware."""
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
from sm5440_passive_admission import startup_evidence
from sm5440_ready_admission import ReadyRecorder
from device_gate import properties, validate_device
from snapshot_gate import validate_snapshot

A = Path(__file__).resolve().parent


def require(ok, reason):
    if not ok:
        raise p.CaptureError(reason)


def main():
    require(not (A / 'observation').exists(), 'never overwrite/retry physical observation')
    package = json.loads((A / 'PACKAGE.json').read_text())
    boot = json.loads((A / 'candidate-boot/summary.json').read_text())['boot_id']
    p.SERIAL = 'gts9wifi-0001'
    r = ReadyRecorder(A / 'observation')
    known_path = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
    known = {x['MESSAGE'] for x in map(json.loads, known_path.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}
    samples = []
    cursor = None

    def scan(raw, name, uptime, first=False):
        nonlocal cursor
        lines = raw.splitlines()
        data = '\n'.join(x for x in lines if x.startswith('{'))
        if first:
            require(bool(data), 'empty full journal')
        if data:
            result = e.inspect_journal(data, boot, known, require_start=first,
                accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
                accepted_qca_cycles=True, observed_uptime=uptime)
            p.write_json(r.folder / (name + '-scan.json'), result)
            require(not result['fault_counts'] and not result['suspects'], 'kernel fault/suspect')
        elif not first:
            require(all(not x.strip() or x == '-- No entries --' or x.startswith('-- cursor: ') for x in lines), 'malformed incremental journal')
        cursors = [x[len('-- cursor: '):] for x in lines if x.startswith('-- cursor: ')]
        if cursors:
            require(len(cursors) == 1 and bool(cursors[0]), 'ambiguous cursor')
            cursor = cursors[0]
        require(cursor is not None, 'no journal cursor')
        return data

    try:
        identity = r.adb('identity', 'set -e; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; uname -a; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; cat /proc/cmdline', 20)[0].splitlines()
        require(len(identity) == 6 and e.canonical_boot_id(identity[0]) == boot, 'candidate identity')
        for line, key in [(identity[3], 'config'), (identity[4], 'kernel-notes.bin')]:
            require(line.split()[0] == package['artifacts'][key]['sha256'], 'candidate '+key+' mismatch')
        normal = (ROOT / '.work/test267-package-inputs/cmdline.txt').read_text().strip()
        require(identity[5] == normal, 'cmdline changed')
        raw = r.adb('initial-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)[0]
        initial = scan(raw, 'initial', float(identity[1].split()[0]), True)
        startup = startup_evidence(initial, boot)
        require('passive SM5440 revision' in initial, 'passive driver absent')
        r.adb('initial-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 25)
        r.adb('dcc-services', 'set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; ! systemctl is-active --quiet serial-getty@hvc0.service; systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr show dev usb0; readlink -f /sys/class/power_supply/sm5440-passive/device/driver', 15)
        start = time.monotonic()
        while True:
            n = len(samples)
            command = ('set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@uptime; cat /proc/uptime; '
                'echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent; '
                'echo @@passive; cat /sys/class/power_supply/sm5440-passive/uevent; '
                'echo @@power-role; cat /sys/class/typec/port0/power_role; echo @@data-role; cat /sys/class/typec/port0/data_role; '
                'echo @@failed; systemctl --failed --no-legend --plain --no-pager; '
                'echo @@snapshot; cat /sys/kernel/debug/sm5440-0-0063/snapshot; '
                'echo @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor=' + shlex.quote(cursor))
            raw = r.adb(f'sample-{n:03}', command, 20)[0]
            chunks = re.split(r'^@@([^\n]+)\n', raw, flags=re.M)
            sec = dict(zip(chunks[1::2], chunks[2::2]))
            require(e.canonical_boot_id(sec['boot']) == boot, 'unexpected reboot')
            battery, passive = properties(sec['battery']), properties(sec['passive'])
            validate_device(battery, passive, sec['power-role'], sec['data-role'])
            snapshot = validate_snapshot(sec['snapshot'])
            protection = {k:snapshot[k] for k in ['sample_cntl2','sample_vbuscntl','sample_vbatcntl','sample_prtncntl']}
            if not samples:
                initial_protection = protection
                initial_pack = int(battery['POWER_SUPPLY_TEMP'])
                initial_die = int(passive['POWER_SUPPLY_TEMP'])
                require(200 <= initial_pack < 380, 'battery entry temperature')
            require(protection == initial_protection, 'protection changed')
            require(int(battery['POWER_SUPPLY_TEMP']) - initial_pack < 100 and int(passive['POWER_SUPPLY_TEMP']) - initial_die < 100, 'abnormal temperature rise')
            require(not sec['failed'].strip(), 'new systemd failed unit')
            scan(sec['kernel'], f'sample-{n:03}', float(sec['uptime'].split()[0]))
            elapsed = time.monotonic() - start
            samples.append({'elapsed_s':round(elapsed,3),'uptime':sec['uptime'].strip(),'battery':battery,'passive':passive,'snapshot':snapshot})
            print('Passive', round(elapsed,1), 's; pack', int(battery['POWER_SUPPLY_TEMP'])/10, 'C; SOC',battery['POWER_SUPPLY_CAPACITY'],'; pump OFF', flush=True)
            if elapsed >= 30:
                break
            time.sleep(min(5, 30-elapsed))
        raw = r.adb('final-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)[0]
        final = scan(raw, 'final', float(samples[-1]['uptime'].split()[0]), True)
        require(startup_evidence(final, boot) == startup, 'startup event repeated/changed')
        r.adb('final-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 25)
        r.adb('final-device-endpoint', 'set -e; cat /proc/sys/kernel/random/boot_id; systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr show dev usb0; ip -4 -o addr show dev wlp1s0; cat /sys/class/udc/*/state', 15)
        host_gaps = []
        try:
            topology, status = r.ps('windows-topology', '', timeout=30)
            topo = json.loads(topology)
            require(not topo['code43'], 'Windows Code43')
            text, rc = r.ssh('final-ncm-auth', 'cat /proc/sys/kernel/random/boot_id', 15, required=False)
            if rc != 0 or e.canonical_boot_id(text) != boot:
                host_gaps.append('NCM host authentication incomplete; see raw record')
        except Exception as exc:
            if 'Code43' in str(exc):
                raise
            host_gaps.append(str(exc))
        wifi = r.adb('wifi-address', 'ip -4 -o addr show dev wlp1s0')[0]
        address = re.search(r'\binet (\d+\.\d+\.\d+\.\d+)/', wifi)
        require(address is not None, 'device Wi-Fi unavailable')
        text, rc = r.command('wifi-auth', ['env','GTS9_DEVICE='+address.group(1),p.SSH,'cat /proc/sys/kernel/random/boot_id'],15,required=False)
        require(rc == 0 and e.canonical_boot_id(text) == boot, 'Wi-Fi rescue authentication unavailable')
        p.write_json(r.folder/'summary.json', {'verdict':'DEVICE_PASSIVE_REGRESSION_COMPLETED','boot_id':boot,'observation_seconds':samples[-1]['elapsed_s'],'samples':samples,'startup':startup,'host_evidence_gaps':host_gaps,'ADB':'responsive same boot','device_NCM':'usb0/sshd active','NCM_host_authenticated':not host_gaps,'WiFi':'authenticated same boot','cached_API_physically_called':False,'fixed9V_charging_test_executed':False,'pump_on':False,'PPS':False,'active_Stage3_ready':False})
        print('PASS device passive regression; host gaps:', host_gaps, flush=True)
    except Exception as exc:
        for name, script in [('failure-kernel-json','journalctl -b -k --no-pager -o json'),('failure-supplies','for f in /sys/class/power_supply/*/uevent; do echo "$f"; cat "$f"; done')]:
            r.adb(name, script,25,required=False)
        p.write_json(r.folder/'summary.json', {'verdict':'STOP_DEVICE_CHECK','error':str(exc),'boot_id':boot,'samples':samples,'pump_on':False,'PPS':False,'device_acceptance_complete':False})
        raise

if __name__ == '__main__':
    main()
