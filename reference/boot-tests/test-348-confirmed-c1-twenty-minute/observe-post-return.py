#!/usr/bin/env python3
"""Test348 post-unbind ordinary charge/discharge observer, no register data writes."""
import gzip
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

FAULT = re.compile(r'\b(?:Kernel panic|BUG:|Oops:|Internal error:|SError|soft lockup|hard LOCKUP|rcu.*(?:detected.*stall|INFO:.*stall)|blocked for more than|non-responsive|workqueue lockup|CSD.*(?:stall|non.response)|WARNING: CPU:)', re.I)
EMIT_LOCK = threading.Lock()


def text(path):
    return Path(path).read_text().strip()


def values(path):
    return dict(x.split('=', 1) for x in text(path).splitlines() if '=' in x)


def pump():
    # Test331/334 accepted atomic CNTL5 pointer/read. No INT, ADC, reset or data write.
    import ctypes as c
    import fcntl
    import os
    class Msg(c.Structure):
        _fields_ = [('addr', c.c_uint16), ('flags', c.c_uint16), ('length', c.c_uint16), ('buf', c.POINTER(c.c_uint8))]
    class Transfer(c.Structure):
        _fields_ = [('msgs', c.POINTER(Msg)), ('nmsgs', c.c_uint32)]
    node = Path('/sys/bus/i2c/devices/0-0063')
    if (node / 'driver').exists() or b'siliconmitus,sm5440' not in (node / 'of_node/compatible').read_bytes().split(b'\0'):
        raise ValueError('pump provider')
    fd = os.open('/dev/i2c-0', os.O_RDWR)
    try:
        pointer, out = (c.c_uint8 * 1)(0x10), (c.c_uint8 * 1)()
        packet = (Msg * 2)(Msg(0x63, 0, 1, pointer), Msg(0x63, 1, 1, out))
        fcntl.ioctl(fd, 0x0707, Transfer(packet, 2))
        return int(out[0])
    finally:
        os.close(fd)


def sample():
    boot = text('/proc/sys/kernel/random/boot_id').replace('-', '')
    supplies = list(Path('/sys/class/power_supply').glob('tcpm-source-psy-*/uevent'))
    zones = [p for p in Path('/sys/class/thermal').glob('thermal_zone*') if text(p / 'type') == 'sm5714-battery']
    if len(supplies) != 1 or len(zones) != 1:
        raise ValueError('TCPM/pack provider identity')
    flag = Path('/sys/module/sm5440_fedora/parameters/fixed_return_check')
    d = dict(boot=boot,
                monotonic=time.monotonic(), uptime=float(text('/proc/uptime').split()[0]),
                direct=text('/sys/module/sm5440_fedora/parameters/direct_charge'),
                fixed_check=text(flag) if flag.exists() else 'absent', pps_check=text('/sys/module/sm5440_fedora/parameters/pps_return_check'), pump=pump(),
                battery=values('/sys/class/power_supply/sm5714-battery/uevent'),
                usb=values('/sys/class/power_supply/sm5714-usb/uevent'), tcpm=values(supplies[0]),
                pack=dict(mode=text(zones[0] / 'mode'), temp=text(zones[0] / 'temp')),
                roles=[text('/sys/class/typec/port0/' + x) for x in ('power_role', 'data_role')],
                config_data_written=False)
    if text('/sys/module/sm5440_fedora/parameters/direct_charge_once') != 'Y' or d['direct'] != 'N' or d['fixed_check'] != 'N' or d['pps_check'] != 'N':
        raise ValueError('one-shot flags drift')
    d['boot_end'] = text('/proc/sys/kernel/random/boot_id').replace('-', '')
    return d


def command(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=8)
    if p.returncode:
        raise ValueError('read-only command failed: ' + repr(argv) + p.stderr)
    return p.stdout


def emit(kind, **data):
    with EMIT_LOCK:
        print(json.dumps(dict(kind=kind, **data)), flush=True)


def main(plan, phase):
    from bounded348_guard import native_proof
    from ordinary_charge_window import ChargeWindow
    from ordinary_charge_window import validate_safety
    follower = None
    errors = []
    verdict = dict(verdict='STOP', phase=phase, PPS=False, pump_ON_observed=True)
    try:
        config = gzip.decompress(Path('/proc/config.gz').read_bytes())
        tokens = text('/proc/cmdline').split()
        if plan.get('pump_window_max_ms')!=1200000 or plan.get('cmdline_flags')!=['sm5440_fedora.direct_charge_once=1','sm5440_fedora.direct_charge_once_ms=1200000']:
            raise ValueError('registered1200s profile missing')
        for flag in plan['cmdline_flags']:
            if tokens.count(flag)!=1:raise ValueError('unique1200s opt-in')
            tokens.remove(flag)
        if text('/sys/module/sm5440_fedora/parameters/direct_charge_once_ms')!='1200000':
            raise ValueError('duration drift')
        if hashlib.sha256(config).hexdigest() != plan['candidate_config_sha256'] or hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() != plan['candidate_notes_sha256'] or text('/etc/machine-id') != plan['machine_id'] or tokens != plan['runtime_cmdline'].split():
            raise ValueError('candidate identity/cmdline')
        if b'# CONFIG_HVC_DCC is not set' not in config or Path('/dev/hvc0').exists() or Path('/sys/class/tty/hvc0').exists() or subprocess.run(['systemctl', 'is-active', '--quiet', 'serial-getty@hvc0.service']).returncode == 0:
            raise ValueError('DCC restored')
        for unit in ('ssh', 'gts9-adbd', 'gts9-usb-acm'):
            if command(['systemctl', 'is-active', unit]).strip() != 'active':
                raise ValueError('rescue service ' + unit)
        if 'usb0    inet 169.254.42.1/' not in command(['ip', '-4', '-o', 'addr']):
            raise ValueError('device NCM')
        if command(['systemctl', '--failed', '--no-legend', '--plain', '--no-pager']).strip():
            raise ValueError('failed systemd unit')
        raw = command(['journalctl', '-k', '-b', '--no-pager', '-o', 'json'])
        emit('journal-before', raw=raw)
        rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
        proof = native_proof(rows, plan['boot_id'], required=True)
        journal_rows = list(rows)
        follower = subprocess.Popen(['journalctl', '-k', '-b', '-f', '--no-pager', '-o', 'json', '--after-cursor='+rows[-1]['__CURSOR']], stdout=subprocess.PIPE, text=True)
        def feed():
            try:
                for line in follower.stdout:
                    row = json.loads(line)
                    with EMIT_LOCK:
                        journal_rows.append(row)
                    emit('kernel', row=row)
                    if row.get('_BOOT_ID') != plan['boot_id'] or FAULT.search(str(row.get('MESSAGE', ''))) or int(row.get('PRIORITY', 7)) <= 3:
                        errors.append('new kernel fault/error')
            except Exception as exc:
                errors.append(repr(exc))
        threading.Thread(target=feed, daemon=True).start()
        initial = sample()
        if phase == 'charge':
            validate_safety(initial, plan)
            window = ChargeWindow(plan, initial['monotonic'])
        else:
            validate_safety(initial, plan)
        emit('armed', phase=phase, initial=initial, wait_seconds=plan['wait_seconds'])
        discharge_start = previous = None
        deadline = initial['monotonic'] + plan['wait_seconds']
        while True:
            d = sample()
            emit('sample', **d)
            if errors or follower.poll() is not None:
                raise ValueError('journal follower failure: ' + repr(errors))
            if phase == 'charge':
                with EMIT_LOCK:
                    snapshot = list(journal_rows)
                progress = window.advance(d)
                native_proof(snapshot, plan['boot_id'], required=True)
            else:
                validate_safety(d, plan)
                if d['pps_check'] not in ('N', '0') or d['fixed_check'] not in ('N', '0'):
                    raise ValueError('check flags changed')
                now = d['monotonic']
                if previous is not None and not 0 < now-previous <= plan['sample_gap_max_seconds']:
                    raise ValueError('response gap')
                previous = now
                unplugged = (d['tcpm'].get('POWER_SUPPLY_ONLINE') == '0' and d['usb'].get('POWER_SUPPLY_ONLINE') == '0' and d['battery']['POWER_SUPPLY_STATUS'] == 'Discharging' and int(d['battery']['POWER_SUPPLY_CURRENT_NOW']) < 0)
                if discharge_start is not None and not unplugged:
                    raise ValueError('discharge lost')
                if discharge_start is None:
                    if now > deadline:
                        raise TimeoutError('unplug wait expired')
                    if unplugged:
                        discharge_start = now
                seconds = 0 if discharge_start is None else now-discharge_start
                progress = dict(state='DISCHARGE' if discharge_start is not None else 'WAIT_UNPLUG', observation_seconds=seconds, complete=seconds >= plan['discharge_seconds'])
            emit('progress', **progress)
            if progress['complete']:
                verdict.update(verdict='PASS', observation_seconds=progress['observation_seconds'], endpoint=d, native=proof)
                break
            time.sleep(1)
    except Exception as exc:
        verdict['error'] = repr(exc)
    finally:
        if follower is not None:
            follower.terminate()
            try:
                follower.wait(timeout=2)
            except subprocess.TimeoutExpired:
                follower.kill()
                follower.wait(timeout=2)
        try:
            raw = command(['journalctl', '-k', '-b', '--no-pager', '-o', 'json'])
            emit('journal-after', raw=raw)
            final_proof = native_proof([json.loads(x) for x in raw.splitlines() if x.strip()], plan['boot_id'], required=verdict['verdict'] == 'PASS')
            failed = command(['systemctl', '--failed', '--no-legend', '--plain', '--no-pager'])
            emit('systemd-failed', raw=failed)
            final = sample()
            if failed.strip() or errors or final['boot'] != plan['boot_id'] or final['boot_end'] != plan['boot_id']:
                raise ValueError('final boot/unit/kernel failure')
            if verdict['verdict'] == 'PASS':
                validate_safety(final, plan)
                if final_proof != verdict['native']:
                    raise ValueError('final native proof drift')
                if phase == 'charge' and (int(final['battery']['POWER_SUPPLY_CURRENT_NOW']) <= 0 or final['tcpm'].get('POWER_SUPPLY_ONLINE') != '1' or int(final['tcpm']['POWER_SUPPLY_VOLTAGE_NOW']) != 9000000):
                    raise ValueError('final charge lost')
        except Exception as exc:
            verdict.update(verdict='STOP', final_error=repr(exc))
        emit('verdict', **verdict)
    return 0 if verdict['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main(json.loads(sys.argv[1]), sys.argv[2]))
