"""Startup diagnosis only: never grants direct-charge admission."""
import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('accepted_snapshot_gate', ROOT / 'reference/boot-tests/test-263-sm5440-adc-snapshot/attempt-01/snapshot_gate.py')
snapshot_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot_gate)

def sections(raw):
    parts = re.split(r'^@@([^\n]+)(?:\n|$)', raw.replace('\r', ''), flags=re.M)
    names = parts[1::2]
    if len(names) != len(set(names)):
        raise ValueError('duplicate section')
    return dict(zip(names, parts[2::2]))

def props(raw):
    return dict(x.split('=', 1) for x in raw.splitlines() if x.startswith('POWER_SUPPLY_'))

def battery_entry(b):
    if b.get('POWER_SUPPLY_HEALTH') != 'Good' or b.get('POWER_SUPPLY_PRESENT') != '1':
        raise ValueError('battery health/presence')
    # Normal baseline boot diagnosis, NOT the unchanged direct-entry SOC<80 gate.
    if not 5 <= int(b['POWER_SUPPLY_CAPACITY']) <= 100:
        raise ValueError('battery SOC')
    if not 3500000 <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) < 4300000:
        raise ValueError('gauge VBAT outside original startup voltage range')
    if not 200 <= int(b['POWER_SUPPLY_TEMP']) < 380:
        raise ValueError('battery temperature entry')
    if b.get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN') != '4440000':
        raise ValueError('float design changed')

def diagnostic_sample(sec):
    b, u, monitor = (props(sec[k]) for k in ('battery', 'usb', 'passive'))
    battery_entry(b)
    if u.get('POWER_SUPPLY_ONLINE') != '1' or '[SDP]' not in u.get('POWER_SUPPLY_USB_TYPE', ''):
        raise ValueError('PC USB SDP absent')
    if u.get('POWER_SUPPLY_INPUT_CURRENT_LIMIT') != '500000':
        raise ValueError('PC USB input policy changed')
    if sec['roles'].strip().splitlines() != ['[sink]', '[device]']:
        raise ValueError('Sink/Device role')
    if monitor.get('POWER_SUPPLY_HEALTH') != 'Good' or monitor.get('POWER_SUPPLY_STATUS') != 'Not charging':
        raise ValueError('passive monitor failed/pending')
    if monitor.get('POWER_SUPPLY_ONLINE') != '1' or monitor.get('POWER_SUPPLY_CURRENT_NOW') != '0':
        raise ValueError('passive online/IBUS')
    if sec['failed'].strip():
        raise ValueError('failed systemd unit')
    snap = snapshot_gate.validate_snapshot(sec['snapshot'])
    if not 225 <= int(snap['sample_die_decic']) < 420:
        raise ValueError('passive die temperature startup diagnosis')
    return {'battery': b, 'usb': u, 'passive': monitor, 'snapshot': snap,
            'high_power_admission': False, 'direct_SOC_gate': int(b['POWER_SUPPLY_CAPACITY']) < 80}
