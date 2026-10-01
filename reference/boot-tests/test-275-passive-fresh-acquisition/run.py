#!/usr/bin/env python3
"""One explicit passive observer load. Run only after registered paired install."""
import json
from pathlib import Path
import shlex
import sys
import time

import gate
sys.path.insert(0, str(gate.ROOT / 'scripts'))
import production_reboot_stability as p

A = Path(__file__).resolve().parent
PLAN = json.loads((A / 'registration.json').read_text())
CURRENT = PLAN['current_command']
RESULT = '/sys/kernel/debug/sm5440-fresh-observer/result'
KNOWN_FILE = gate.ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
KNOWN = {row['MESSAGE'] for row in map(json.loads, KNOWN_FILE.read_text().splitlines()) if int(row.get('PRIORITY', 7)) <= 3}


def run():
    gate.require(not (A / 'observation').exists(), 'single physical attempt; no retry')
    install = json.loads((A / 'install/summary.json').read_text())
    gate.require(install['verdict'] == 'PAIRED_INSTALLATION_READBACK_VERIFIED', 'installation unverified')
    rec = p.Recorder(A / 'observation')
    result = dict(PPS=False, pump_ON=False, independently_calibrated=False, samples=[])
    attempted = False
    boot = None
    try:
        sec = gate.baseline.sections(rec.adb('before-load-state', CURRENT, 20)[0])
        boot, value = gate.identity(sec, PLAN, PLAN['candidate_notes_sha256'])
        gate.require(boot != PLAN['before_boot_id'], 'old boot')
        history = rec.adb('boots-after', 'journalctl --list-boots --no-pager')[0]
        before = (A / 'preflight/boots-before.txt').read_text()
        gate.require(gate.evidence.attribute(PLAN['before_boot_id'], boot, before, history) == 'attributed', 'unexpected boot history')
        wifi_ip = gate.wifi_address(sec)
        result['wifi_ip'] = wifi_ip
        rec.command('wifi-before', ['env', 'GTS9_DEVICE=' + wifi_ip, p.SSH, 'cat /proc/sys/kernel/random/boot_id'], 20)
        gate.require(gate.evidence.canonical_boot_id((rec.folder / 'wifi-before.txt').read_text()) == boot, 'WiFi boot')
        usb, _ = rec.ps('windows-before', p.PS_USB, 30)
        gate.require(not p.has_code43(usb), 'Windows Code43 before load')
        raw = rec.adb('kernel-before-json', 'journalctl -b -k --no-pager -o json', 25)[0]
        p.write_json(rec.folder / 'kernel-before-scan.json', gate.journal(raw, boot, KNOWN, float(sec['uptime'].split()[0])))
        cursor = json.loads(raw.splitlines()[-1])['__CURSOR']
        rec.adb('module-boundary', 'set -e; test ! -e /sys/module/sm5440_fresh_observer; test ! -e ' + RESULT + '; test "$(sha256sum /tmp/test275-observer.ko | cut -d " " -f1)" = ' + PLAN['observer_sha256'] + '; grep -w sm5440_passive_request_fresh /proc/kallsyms')
        attempted = True  # No repeat even if insmod response fails.
        rec.adb('load-once', 'insmod /tmp/test275-observer.ko')
        start = time.monotonic()
        while True:
            index = len(result['samples'])
            packet = CURRENT + '; echo @@observer; cat ' + RESULT + '; echo @@kernel; journalctl -b -k --no-pager -o json --after-cursor=' + shlex.quote(cursor)
            sec = gate.baseline.sections(rec.adb(f'sample-{index:02}', packet, 20)[0])
            _, value = gate.identity(sec, PLAN, PLAN['candidate_notes_sha256'], boot)
            value['observer'] = gate.observer(sec['observer'])
            value['elapsed_s'] = round(time.monotonic() - start, 3)
            result['samples'].append(value)
            if sec['kernel'].strip():
                p.write_json(rec.folder / f'sample-{index:02}-kernel-scan.json', gate.journal(sec['kernel'], boot, KNOWN, float(sec['uptime'].split()[0]), False))
                cursor = json.loads(sec['kernel'].splitlines()[-1])['__CURSOR']
            print('passive', value['elapsed_s'], 's; calls', value['observer']['count'], 'state', value['observer']['state'], flush=True)
            if value['observer']['state'] in (2, 3):
                break
            if value['elapsed_s'] >= 30:
                gate.require(value['observer']['state'] == 1, 'observer incomplete at deadline')
                break
            time.sleep(min(2, 30 - value['elapsed_s']))
        result.update(boot_id=boot, observation_seconds=result['samples'][-1]['elapsed_s'], observer=result['samples'][-1]['observer'])
        result['verdict'] = 'DEVICE_NORMAL_ACQUISITION_REFUSED' if result['observer']['first_refusal'] else 'DEVICE_NORMAL_EIGHT_FRESH_DELIVERIES'
    except Exception as exc:
        result.update(verdict='STOP_REQUIRES_ANALYSIS', error=str(exc), boot_id=boot)
        rec.adb('first-failure-state', CURRENT + '; echo @@observer; cat ' + RESULT, 20, False)
    finally:
        # Capture BEFORE unloading; status data disappears after rmmod.
        rec.adb('terminal-observer', 'cat ' + RESULT, 15, False)
        if attempted:
            _, status = rec.adb('unload', 'set -e; if test -e /sys/module/sm5440_fresh_observer; then rmmod sm5440_fresh_observer; fi; test ! -e /sys/module/sm5440_fresh_observer; test ! -e ' + RESULT, 20, False)
            result['unloaded'] = status == 0
            if status:
                result.update(verdict='STOP_REQUIRES_ANALYSIS', unload_error=True)
        raw, status = rec.adb('kernel-final-json', 'journalctl -b -k --no-pager -o json', 25, False)
        rec.adb('kernel-final-journal', 'journalctl -b -k --no-pager -o short-monotonic', 25, False)
        try:
            gate.require(status == 0 and boot is not None, 'final journal unavailable')
            final = gate.baseline.sections(rec.adb('endpoint-state', CURRENT, 20)[0])
            gate.identity(final, PLAN, PLAN['candidate_notes_sha256'], boot)
            p.write_json(rec.folder / 'kernel-final-scan.json', gate.journal(raw, boot, KNOWN, float(final['uptime'].split()[0])))
            wifi, _ = rec.command('wifi-final', ['env', 'GTS9_DEVICE=' + gate.wifi_address(final), p.SSH, 'cat /proc/sys/kernel/random/boot_id'], 20)
            gate.require(gate.evidence.canonical_boot_id(wifi) == boot, 'final WiFi boot')
            usb, _ = rec.ps('windows-usb', p.PS_USB, 30)
            gate.require(not p.has_code43(usb), 'Windows Code43')
            result.update(ADB='responsive', WiFi='same-boot authenticated', device_NCM='usb0/sshd normal', host_NCM_TCP_tested=False)
        except Exception as exc:
            result.update(verdict='STOP_REQUIRES_ANALYSIS', endpoint_error=str(exc))
        p.write_json(rec.folder / 'summary.json', result)
    print(result['verdict'], flush=True)


if __name__ == '__main__':
    run()
