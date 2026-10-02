"""Portable frozen mainline health gates; no device access."""
import re
from types import SimpleNamespace
import snapshot_gate
from collector import boot_id
from observer_gate import require
def sections(raw):
    parts = re.split('^@@([^\\n]+)(?:\\n|$)', raw.replace('\r', ''), flags=re.M)
    names = parts[1::2]
    if len(names) != len(set(names)):
        raise ValueError('duplicate section')
    return dict(zip(names, parts[2::2]))

def props(raw):
    return dict((x.split('=', 1) for x in raw.splitlines() if x.startswith('POWER_SUPPLY_')))

def battery_entry(b):
    if b.get('POWER_SUPPLY_HEALTH') != 'Good' or b.get('POWER_SUPPLY_PRESENT') != '1':
        raise ValueError('battery health/presence')
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
    return {'battery': b, 'usb': u, 'passive': monitor, 'snapshot': snap, 'high_power_admission': False, 'direct_SOC_gate': int(b['POWER_SUPPLY_CAPACITY']) < 80}

baseline=SimpleNamespace(diagnostic_sample=diagnostic_sample)
evidence=SimpleNamespace(canonical_boot_id=lambda raw:boot_id(raw).replace('-', ''))
def identity(sec, plan, notes, boot=None):
    current = evidence.canonical_boot_id(sec['boot'])
    require(boot is None or current == boot, 'boot changed')
    ids = sec['identity'].splitlines()
    require(len(ids) == 2 and ids[0].split()[0] == plan['config_sha256'] and (ids[1].split()[0] == notes), 'config/notes identity')
    require(sec['cmdline'].strip() == plan['runtime_cmdline'], 'runtime cmdline')
    require(sec['services'].splitlines() == ['active'] * 3 and (not sec['failed'].strip()), 'service failure')
    require(sec['dcc'].strip() == 'absent', 'DCC missing/restored')
    require('usb0' in sec['network'] and '169.254.42.1/16' in sec['network'], 'device NCM absent')
    value = baseline.diagnostic_sample(sec)
    require(all((value['snapshot'][k] == v for k, v in plan['protection'].items())), 'protection changed')
    return (current, value)
