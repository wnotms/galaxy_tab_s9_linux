#!/usr/bin/env python3
"""Manual-cable, unchanged fixed-PD observation. No hardware/configuration writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
import tcpm_source_capabilities as caps

A = Path(__file__).resolve().parent
PLAN = json.loads((A / 'registration.json').read_text())
SPEC = importlib.util.spec_from_file_location('baseline_diagnostic_gate', ROOT / 'reference/boot-tests/test-271-baseline-passive-startup/gate.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
CURRENT = json.loads((ROOT / 'reference/boot-tests/test-270-high-power-readiness/device-state-via-adb/current-state.command.json').read_text())['argv'][-1] + r'; echo @@dcc; if test ! -e /dev/hvc0 && test ! -e /sys/class/tty/hvc0 && ! systemctl is-active --quiet serial-getty@hvc0.service; then echo absent; else echo present; fi'
# Original preparation stopped on a host-only omitted field; preserve it unchanged.
PREPARE_PHASE = 'prepare-completion'

KNOWN_FILE = ROOT / 'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
KNOWN = {x['MESSAGE'] for x in map(json.loads, KNOWN_FILE.read_text().splitlines()) if int(x.get('PRIORITY', 7)) <= 3}
BASE_SUSPECTS = json.loads((A / 'preflight/kernel-scan.json').read_text())['suspects']
SOURCE_CMD = r'''echo @@sourcecaps
pd=$(readlink -f /sys/class/typec/port0-partner/usb_power_delivery || true)
printf 'PD_PARTNER_LINK=%s\n' "$pd"
if test -d "$pd/source-capabilities"; then
  for obj in "$pd"/source-capabilities/*; do
    test -d "$obj" || continue
    printf 'PDO_PATH=%s\n' "$obj"
    for attr in voltage minimum_voltage maximum_voltage maximum_current maximum_power pps_power_limited; do
      if test -f "$obj/$attr"; then printf '%s=' "$attr"; cat "$obj/$attr"; fi
    done
  done
fi'''
TCPM_CMD = '; echo @@tcpm; cat /sys/class/power_supply/tcpm-source-psy-3-0033/uevent'


def require(ok, message):
    if not ok:
        raise p.CaptureError(message)



def fixed_budget_history(parsed):
    """TCPM budgets are not measurements or SM5714 programmed input current.

    Pinned TCPM SNK_DISCOVERY reports up to 5V/3A from Rp before PD negotiation;
    sm5714_battery_set_pd_contract stores that grant while configure_charging
    separately clamps actual draw. Accepted Test263 already contains this budget.
    Current fixed contract and charger input are checked independently in sample.
    """
    for entry in parsed['limits']:
        mv, ma = entry['voltage_mv'], entry['current_ma']
        ceiling = {0: 0, 5000: 3000, 9000: 1500}.get(mv)
        require(ceiling is not None and 0 <= ma <= ceiling,
                'unapproved TCPM reported voltage/current budget')
    return {'limits_are_measured_draw': False, 'limits': parsed['limits'],
            'actual_input_checked_separately': True,
            'fixed5V_input_ceiling_ma': 1800, 'fixed9V_input_ceiling_ma': 1500}


def identity(sec):
    require(e.canonical_boot_id(sec['boot']) == PLAN['boot_id'], 'boot changed')
    ids = sec['identity'].splitlines()
    require(ids[0].split()[0] == PLAN['config_sha256'] and ids[1].split()[0] == PLAN['notes_sha256'], 'Test263 identity changed')
    require(sec['cmdline'].strip() == PLAN['runtime_cmdline'], 'runtime cmdline changed')
    require(sec['services'].splitlines() == ['active'] * 3 and not sec['failed'].strip(), 'services/failed unit')
    require(sec['roles'].splitlines() == ['[sink]', '[device]'], 'Sink/Device role changed')
    require(sec.get('dcc', '').strip() == 'absent', 'DCC absence evidence missing/restored')


def sample(sec, source=False):
    identity(sec)
    if not source:
        require('usb0' in sec['network'], 'device NCM interface missing')
        return gate.diagnostic_sample(sec)
    battery, usb, monitor, tcpm = [gate.props(sec[k]) for k in ('battery', 'usb', 'passive', 'tcpm')]
    gate.battery_entry(battery)  # Normal fixed-charge scope; NEVER active admission.
    require(battery['POWER_SUPPLY_STATUS'] == 'Charging' and int(battery['POWER_SUPPLY_CURRENT_NOW']) > 0, 'battery charging/current')
    require('[PD]' in tcpm.get('POWER_SUPPLY_USB_TYPE', '') and tcpm.get('POWER_SUPPLY_ONLINE') == '1', 'fixed PD unavailable')
    mv = int(tcpm['POWER_SUPPLY_VOLTAGE_NOW']) // 1000
    require(int(tcpm['POWER_SUPPLY_VOLTAGE_NOW']) in (5000000, 9000000), 'unapproved selected voltage')
    ceiling = 1500000 if mv == 9000 else 1800000
    require(0 < int(tcpm['POWER_SUPPLY_CURRENT_MAX']) <= ceiling, 'PD contract current ceiling')
    require(usb.get('POWER_SUPPLY_ONLINE') == '1' and '[PD]' in usb.get('POWER_SUPPLY_USB_TYPE', '') and
            0 < int(usb['POWER_SUPPLY_INPUT_CURRENT_LIMIT']) <= ceiling, 'SM5714 fixed input policy')
    require(monitor.get('POWER_SUPPLY_HEALTH') == 'Good' and monitor.get('POWER_SUPPLY_STATUS') == 'Not charging' and
            monitor.get('POWER_SUPPLY_ONLINE') == '1' and monitor.get('POWER_SUPPLY_CURRENT_NOW') == '0', 'passive OFF/health')
    snapshot = gate.snapshot_gate.validate_snapshot(sec['snapshot'], mv // 1000)
    require(225 <= int(snapshot['sample_die_decic']) < 420, 'passive die temperature')
    before = gate.diagnostic_sample(gate.sections((A / 'preflight/current-state.txt').read_text()))['snapshot']
    require(all(snapshot[k] == before[k] for k in ('sample_cntl2', 'sample_vbuscntl', 'sample_vbatcntl', 'sample_prtncntl')), 'protection changed')
    return dict(battery=battery, usb=usb, passive=monitor, tcpm=tcpm, snapshot=snapshot,
                negotiated_voltage_mv=mv, active_charge_admission=False)


def kernel(rec, name, raw, uptime, full=False):
    lines = raw.splitlines()
    require(all(not x.strip() or x.startswith(('{', '-- cursor: ')) or x == '-- No entries --' for x in lines), 'malformed journal')
    data = '\n'.join(x for x in lines if x.startswith('{'))
    require(bool(data) or not full, 'missing full journal')
    if data:
        scan = e.inspect_journal(data, PLAN['boot_id'], KNOWN, require_start=full,
            accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
            accepted_qca_cycles=True, observed_uptime=uptime)
        p.write_json(rec.folder / (name + '-scan.json'), scan)
        require(not scan['fault_counts'], 'new CPU/kernel failure')
        require(scan['suspects'] == BASE_SUSPECTS if full else not scan['suspects'], 'new kernel suspect; original20 startup gap retained')
        require(not any('sm5440-passive' in x['MESSAGE'] and any(v in x['MESSAGE'] for v in ('fault bitmap=', 'ADC fault', 'confirmation failed')) for x in map(json.loads, data.splitlines())), 'new passive fault')
    cursors = [x[len('-- cursor: '):] for x in lines if x.startswith('-- cursor: ')]
    require(len(cursors) == 1 and cursors[0], 'journal cursor missing/ambiguous')
    return cursors[0]


def ssh(rec, name, command, timeout=20, required=True):
    return rec.command(name, ['env', 'GTS9_DEVICE=' + PLAN['wifi'], p.SSH, command], timeout, required)[0]


def execute(phase, owner_confirmed=False):
    folder = A / (PREPARE_PHASE if phase == 'prepare' else phase)
    require(not folder.exists(), 'no phase retry/overwrite')
    require(phase == 'prepare' or owner_confirmed, 'owner cable confirmation required')
    if phase != 'prepare':
        prepared = json.loads((A / PREPARE_PHASE / 'summary.json').read_text())
        require(prepared['verdict'] == 'READY_FOR_OWNER_C1_ATTACH', 'prepare not qualified')
    rec = p.Recorder(folder)
    samples = []
    outcome = dict(phase=phase, boot_id=PLAN['boot_id'], owner_confirmed=owner_confirmed,
                   samples=samples, flash=False, reboot=False, PPS=False, pump_ON=False,
                   active_charge_admission=False, raw_startup_classification_gap_retained=True)
    try:
        if phase == 'prepare':
            sec = gate.sections(ssh(rec, 'state', CURRENT))
            samples.append(sample(sec))
            raw = ssh(rec, 'kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)
            cursor = kernel(rec, 'kernel', raw, float(sec['uptime'].split()[0]), True)
            # Consumes the ring: preserve the complete first read before cable action.
            ssh(rec, 'tcpm-before', 'cat ' + shlex.quote(PLAN['tcpm_log_path']))
            outcome.update(verdict='READY_FOR_OWNER_C1_ATTACH', cursor=cursor, fresh_log_boundary=True)
        elif phase == 'source':
            time.sleep(PLAN['settle_seconds_after_owner_confirmation'])
            cursor = prepared['cursor']
            cmd = CURRENT + TCPM_CMD + '; ' + SOURCE_CMD + '; echo @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor=' + shlex.quote(cursor)
            sec = gate.sections(ssh(rec, 'initial-state', cmd))
            first = sample(sec, True)
            cursor = kernel(rec, 'initial', sec['kernel'], float(sec['uptime'].split()[0]))
            rawlog = ssh(rec, 'tcpm-source-first', 'cat ' + shlex.quote(PLAN['tcpm_log_path']))
            parsed = caps.parse_source_capabilities(rawlog, same_boot=True, owner_confirmed=owner_confirmed,
                                                    fresh_log_boundary=prepared['fresh_log_boundary'])
            p.write_json(rec.folder / 'source-capabilities-first.json', parsed)
            partner = caps.corroborate_partner(parsed, sec['sourcecaps'])
            p.write_json(rec.folder / 'tcpm-budgets-first.json', fixed_budget_history(parsed))
            start = time.monotonic()
            first['elapsed_s'] = 0.0
            samples.append(first)
            while samples[-1]['elapsed_s'] < PLAN['observation_seconds']:
                time.sleep(min(PLAN['sample_interval_seconds'], PLAN['observation_seconds'] - samples[-1]['elapsed_s']))
                raw = ssh(rec, f'sample-{len(samples):03}', CURRENT + TCPM_CMD + '; echo @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor=' + shlex.quote(cursor))
                sec = gate.sections(raw)
                value = sample(sec, True)
                cursor = kernel(rec, f'sample-{len(samples):03}', sec['kernel'], float(sec['uptime'].split()[0]))
                require(int(value['battery']['POWER_SUPPLY_TEMP']) - int(first['battery']['POWER_SUPPLY_TEMP']) < 100, 'abnormal heating')
                value['elapsed_s'] = round(time.monotonic() - start, 3)
                samples.append(value)
                print('C1 fixed-PD', value['elapsed_s'], 's;', value['negotiated_voltage_mv'], 'mV; pack', value['battery']['POWER_SUPPLY_TEMP'], 'deciC', flush=True)
            require(len({x['snapshot']['sample_stamp_jiffies'] for x in samples}) >= 2, 'no advancing ADC')
            end = gate.sections(ssh(rec, 'final-state', CURRENT + TCPM_CMD + '; ' + SOURCE_CMD))
            sample(end, True)
            tail = ssh(rec, 'tcpm-source-tail', 'cat ' + shlex.quote(PLAN['tcpm_log_path']))
            final = caps.parse_source_capabilities(rawlog + tail, same_boot=True, owner_confirmed=True, fresh_log_boundary=True)
            partner_final = caps.corroborate_partner(final, end['sourcecaps'])
            require(partner == partner_final, 'partner source changed')
            p.write_json(rec.folder / 'tcpm-budgets.json', fixed_budget_history(final))
            full = ssh(rec, 'final-kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)
            cursor = kernel(rec, 'final', full, float(end['uptime'].split()[0]), True)
            ssh(rec, 'final-kernel-journal', 'journalctl -b -k --no-pager -o short-monotonic', 25)
            p.write_json(rec.folder / 'source-capabilities.json', final)
            outcome.update(verdict='SOURCE_IDENTIFIED_FIXED_PD_WINDOW_COMPLETED', source_capabilities=final,
                           partner_source_objects=partner_final, observation_seconds=samples[-1]['elapsed_s'], cursor=cursor)
        elif phase == 'pc':
            # PC return is a rescue endpoint; allowed even after source UNKNOWN/STOP.
            time.sleep(PLAN['settle_seconds_after_owner_confirmation'])
            sec = gate.sections(rec.adb('adb-state', CURRENT)[0])
            samples.append(sample(sec))
            wifi = ssh(rec, 'wifi-state', 'cat /proc/sys/kernel/random/boot_id')
            require(e.canonical_boot_id(wifi) == PLAN['boot_id'], 'Wi-Fi boot mismatch')
            raw = ssh(rec, 'kernel-json', 'journalctl -b -k --no-pager -o json --show-cursor', 25)
            kernel(rec, 'kernel', raw, float(sec['uptime'].split()[0]), True)
            usb = rec.ps('windows-usb', p.PS_USB, 30)[0]
            require(not p.has_code43(usb), 'Windows Code43')
            outcome.update(verdict='PC_DEVICE_ENDPOINT_COMPLETED', ADB='responsive', WiFi='same-boot authenticated',
                           host_NCM_tested=False, device_usb0_present='usb0' in sec['network'])
        p.write_json(rec.folder / 'summary.json', outcome)
    except Exception as exc:
        ssh(rec, 'first-failure-state', CURRENT + TCPM_CMD, 20, False)
        ssh(rec, 'first-failure-kernel-json', 'journalctl -b -k --no-pager -o json', 25, False)
        outcome.update(verdict='STOP_FIRST_NON_CLEAN', error=str(exc), source_identification='UNKNOWN unless complete saved evidence proves otherwise')
        p.write_json(rec.folder / 'summary.json', outcome)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'source', 'pc'))
    parser.add_argument('--owner-confirmed', action='store_true')
    args = parser.parse_args()
    execute(args.phase, args.owner_confirmed)
