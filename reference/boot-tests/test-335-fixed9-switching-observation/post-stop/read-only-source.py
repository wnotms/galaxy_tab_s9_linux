#!/usr/bin/env python3
"""Read-only, same-boot ordinary charging observer; no register programming."""
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


def validate(d, plan, phase=None):
    if d['boot'] != plan['boot_id'] or d['boot_end'] != d['boot']:
        raise ValueError('unexpected/mixed boot')
    if d['direct'] not in ('N', '0') or d['fixed_check'] not in ('absent', 'N', '0'):
        raise ValueError('active/one-shot parameter')
    if not isinstance(d['pump'], int) or not 0 <= d['pump'] <= 255 or d['pump'] & 12:
        raise ValueError('pump not OFF')
    b, u, p = d['battery'], d['usb'], d['tcpm']
    if b.get('POWER_SUPPLY_HEALTH') != 'Good' or b.get('POWER_SUPPLY_PRESENT') != '1' or b.get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN') != '4440000':
        raise ValueError('battery health/design')
    for key, low, high in [('CAPACITY', plan['soc_min'], plan['soc_max_exclusive']),
                           ('VOLTAGE_NOW', plan['vbat_min_uv'], plan['vbat_max_exclusive_uv']),
                           ('TEMP', plan['temp_min_decic'], plan['temp_max_exclusive_decic'])]:
        if not low <= int(b['POWER_SUPPLY_' + key]) < high:
            raise ValueError('registered pack ' + key)
    if d['pack']['mode'] != 'enabled' or abs(int(d['pack']['temp']) - 100 * int(b['POWER_SUPPLY_TEMP'])) > 500 or not 20000 <= int(d['pack']['temp']) < 38000:
        raise ValueError('real pack thermal sensor')
    online = p.get('POWER_SUPPLY_ONLINE')
    if online not in ('0', '1') or '[PD_PPS]' in p.get('POWER_SUPPLY_USB_TYPE', ''):
        raise ValueError('PPS/unknown source')
    if online == '1':
        voltage = int(p['POWER_SUPPLY_VOLTAGE_NOW'])
        ceiling = 1800000 if voltage == 5000000 else plan['fixed9_input_max_ua']
        limit = int(u['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])
        if voltage not in (5000000, 9000000) or int(p['POWER_SUPPLY_VOLTAGE_MAX']) != voltage:
            raise ValueError('unapproved fixed voltage')
        if d['roles'] != ['[sink]', '[device]'] or not 100000 <= limit <= min(ceiling, int(p['POWER_SUPPLY_CURRENT_MAX'])) or (limit - 100000) % 25000:
            raise ValueError('role/input current policy')
    if phase == 'charge':
        if online != '1' or int(p['POWER_SUPPLY_VOLTAGE_NOW']) != 9000000 or u.get('POWER_SUPPLY_ONLINE') != '1' or '[PD]' not in u.get('POWER_SUPPLY_USB_TYPE', '') or b.get('POWER_SUPPLY_STATUS') != 'Charging' or int(b['POWER_SUPPLY_CURRENT_NOW']) <= 0:
            raise ValueError('fixed9 ordinary charging missing')
    if phase == 'discharge':
        if online != '0' or u.get('POWER_SUPPLY_ONLINE') != '0' or b.get('POWER_SUPPLY_STATUS') != 'Discharging' or int(b['POWER_SUPPLY_CURRENT_NOW']) >= 0:
            raise ValueError('unplug did not restore discharge')
    return d


def inspect_journal(raw, boot, known_errors=()):
    rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
    if not rows or min(int(x['__MONOTONIC_TIMESTAMP']) for x in rows) > 5000000:
        raise ValueError('missing/empty/incomplete kernel journal')
    for row in rows:
        message = str(row.get('MESSAGE', ''))
        if row.get('_BOOT_ID') != boot or FAULT.search(message):
            raise ValueError('kernel fault/boot attribution')
        if int(row.get('PRIORITY', 7)) <= 3 and message not in known_errors:
            raise ValueError('new unclassified kernel error: ' + message)
    return rows


def progress(d, plan, phase, started, previous):
    now = d['monotonic']
    if previous is not None and not 0 < now - previous <= plan['sample_gap_max_seconds']:
        raise ValueError('sample response gap')
    if started is None:
        target = (d['tcpm'].get('POWER_SUPPLY_ONLINE') == '1' and int(d['tcpm'].get('POWER_SUPPLY_VOLTAGE_NOW', 0)) == 9000000) if phase == 'charge' else d['tcpm'].get('POWER_SUPPLY_ONLINE') == '0'
        if target:
            validate(d, plan, phase)
            started = now
    else:
        validate(d, plan, phase)
    duration = 0 if started is None else now - started
    return started, duration >= plan[phase + '_seconds'], duration


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
    if (node / 'driver').resolve(strict=True).name != 'sm5440-fedora' or b'siliconmitus,sm5440' not in (node / 'of_node/compatible').read_bytes().split(b'\0'):
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
                fixed_check=text(flag) if flag.exists() else 'absent', pump=pump(),
                battery=values('/sys/class/power_supply/sm5714-battery/uevent'),
                usb=values('/sys/class/power_supply/sm5714-usb/uevent'), tcpm=values(supplies[0]),
                pack=dict(mode=text(zones[0] / 'mode'), temp=text(zones[0] / 'temp')),
                roles=[text('/sys/class/typec/port0/' + x) for x in ('power_role', 'data_role')],
                config_data_written=False)
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
    follower = None
    verdict = dict(verdict='STOP', phase=phase, PPS=False, pump_ON=False)
    journal_errors = []
    try:
        config = gzip.decompress(Path('/proc/config.gz').read_bytes())
        if hashlib.sha256(config).hexdigest() != plan['config_sha256'] or hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() != plan['notes_sha256'] or text('/etc/machine-id') != plan['machine_id'] or text('/proc/cmdline').split() != plan['runtime_cmdline'].split():
            raise ValueError('baseline identity/cmdline')
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
        # Existing same-boot startup errors are retained, not counted as new faults.
        known = {json.loads(x)['MESSAGE'] for x in raw.splitlines() if int(json.loads(x).get('PRIORITY', 7)) <= 3}
        rows = inspect_journal(raw, plan['boot_id'], known)
        follower = subprocess.Popen(['journalctl', '-k', '-b', '-f', '--no-pager', '-o', 'json', '--after-cursor=' + rows[-1]['__CURSOR']], stdout=subprocess.PIPE, text=True)
        def feed():
            try:
                for line in follower.stdout:
                    row = json.loads(line)
                    emit('kernel', row=row)
                    if row.get('_BOOT_ID') != plan['boot_id'] or FAULT.search(str(row.get('MESSAGE', ''))) or int(row.get('PRIORITY', 7)) <= 3:
                        journal_errors.append('new kernel fault/error')
            except Exception as e:
                journal_errors.append(repr(e))
        threading.Thread(target=feed, daemon=True).start()
        initial = validate(sample(), plan)
        emit('armed', phase=phase, initial=initial, wait_seconds=plan['wait_seconds'], observation_seconds=plan[phase + '_seconds'])
        deadline = time.monotonic() + plan['wait_seconds']
        started = previous = None
        while True:
            d = validate(sample(), plan)
            emit('sample', **d)
            if journal_errors or follower.poll() is not None:
                raise ValueError('kernel/follower failure: ' + repr(journal_errors))
            started, done, seconds = progress(d, plan, phase, started, previous)
            previous = d['monotonic']
            if done:
                verdict = dict(verdict='PASS', phase=phase, observation_seconds=seconds, endpoint=d, PPS=False, pump_ON=False)
                break
            if started is None and time.monotonic() > deadline:
                raise TimeoutError('charger action not detected within registered wait')
            time.sleep(1)
    except Exception as e:
        verdict['error'] = repr(e)
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
            inspect_journal(raw, plan['boot_id'], locals().get('known', ()))
            failed = command(['systemctl', '--failed', '--no-legend', '--plain', '--no-pager'])
            emit('systemd-failed', raw=failed)
            validate(sample(), plan, phase if verdict['verdict'] == 'PASS' else None)
            if failed.strip() or journal_errors:
                raise ValueError('final unit/kernel error')
        except Exception as e:
            verdict.update(verdict='STOP', final_error=repr(e))
        emit('verdict', **verdict)
    return 0 if verdict['verdict'] == 'PASS' else 1



plan={'test': 'Test335', 'purpose': '30-second fixed9 ordinary switching charging on unchanged accepted Test331, using enrolled bounded WiFi discovery', 'baseline_source': '1f1d856858757c6d9082a4ccacc8de9de9b5cbed', 'boot_id': 'f1e9a45a55054b88ab05b969775657e9', 'machine_id': '3c2a1b8f2d624db4b5ffdc836050fcf6', 'config_sha256': '51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a', 'notes_sha256': '03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95', 'runtime_cmdline': 'console=tty0 msm.separate_gpu_kms=1 consoleblank=0 gts9_display_recover=1 gts9_rootfs=/dev/mmcblk1p1 gts9_sec_log=0x880200000,0x200000 loglevel=4 nokaslr panic=0 clk_ignore_unused pd_ignore_unused regulator_ignore_unused firmware_class.path=/lib/firmware systemd.ssh_auto=no fbcon=font:TER16x32  msm_drm.dsi_display0=GTS9_ANA38407_AMSA10FA01: msm_drm.lcd_id=800004 sec_common_fn.lcd_id=800004 console=null nokaslr watchdog.stop_on_reboot=0 softdog.soft_panic=1 sec_vibrator_inputff_module.vib_le_est=0 common_muic.muic_param_pdic_info=1 common_muic.muic_param_pmic_info=3 pdic_notifier_module.pdic_param_lpcharge=0 nfc_sec.nfc_param_lpcharge=0 flicker_sensor.flicker_param_lpcharge=0 common_muic.muic_param_afc_mode=0x00 sec-battery.charging_mode=0x00 sec-battery.pd_disable=0x00 abc.qet_loaded=0 mesh_qc.kq_mesh_drv_loading=0x0 sb-mfc.wireless_ic=0x0 p9320_charger.wireless_ic=0x0 s2miw04_charger.wireless_ic=0x0 cps4038_charger.wireless_ic=0x0 nu1668_charger.wireless_ic=0x0 msm_rtb.enable=0 nowatchdog sec-battery.sales_code=CHN sec_sysup.edtbo_ver=-1 sapa=0 sec_pon_alarm.rtcalarm=0 sec_pon_alarm.lpcharge=0 hdm.status=NONE frpc-adsprpc.signoff=0x7277', 'previous_ip': '10.139.153.163', 'key': '/home/ms/.ssh/gts9_ed25519', 'known_hosts': '/tmp/gts9-test323-known-hosts', 'alias': 'gts9-test292', 'charger': 'Lenovo YG65G USB-C2 18W, C1 empty', 'wait_seconds': 240, 'charge_seconds': 30, 'discharge_seconds': 15, 'sample_gap_max_seconds': 3, 'soc_min': 20, 'soc_max_exclusive': 80, 'vbat_min_uv': 3500000, 'vbat_max_exclusive_uv': 4300000, 'temp_min_decic': 200, 'temp_max_exclusive_decic': 380, 'fixed9_input_max_ua': 1500000, 'PPS': False, 'pump_ON': False, 'flash': False, 'reboot': False, 'rollback': 'No software mutation; unplug charger on first non-clean, retain installed accepted331. No automatic flash/reboot/retry.', 'limitation': 'Not a native one-shot replay, PPS-to-fixed transition, independent VBUS measurement, pump/high-power acceptance or retroactive Test334 PASS'}
d=validate(sample(),plan); emit('endpoint',sample=d,config=hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest(),notes=hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()); emit('kernel-journal',raw=command(['journalctl','-k','-b','--no-pager','-o','json']))
