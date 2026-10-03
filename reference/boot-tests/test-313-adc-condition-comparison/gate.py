#!/usr/bin/env python3
"""Pure Test306 evidence checks. No transport, device writes or charging grant."""
import json
import re


def values(text):
    result = {}
    for line in text.splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key in result and result[key] != value:
            raise ValueError('conflicting field: ' + key)
        result[key] = value
    return result


def battery_entry(text):
    b = values(text)
    if b['POWER_SUPPLY_HEALTH'] != 'Good' or b['POWER_SUPPLY_PRESENT'] != '1':
        raise ValueError('pack health/presence')
    soc, uv, temp = (int(b[k]) for k in ('POWER_SUPPLY_CAPACITY',
                                       'POWER_SUPPLY_VOLTAGE_NOW', 'POWER_SUPPLY_TEMP'))
    if not 5 <= soc < 80 or not 3500000 <= uv < 4300000 or not 200 <= temp < 380:
        raise ValueError('pack outside registered physical entry range')
    return dict(soc=soc, voltage_uv=uv, temp_decic=temp)


def condition(snapshot_text, kernel_json, boot_id):
    s = values(snapshot_text)
    if s.get('condition_test') != '1' or s.get('condition_attempted') != '1':
        raise ValueError('condition experiment absent')
    if s.get('enhiz_restore_pending') != '0' or s.get('last_sample_error') != '0':
        raise ValueError('ADC/restore unresolved')
    if s.get('stopped') != '0' or s.get('fault') != '0':
        raise ValueError('driver stopped/faulted')
    if s.get('pump_enable_supported') != '0' or s.get('sample_valid') != '1':
        raise ValueError('pump capability or missing completed sample')
    for name in ('cntl6_before_valid', 'cntl6_during_valid', 'cntl6_restored_valid'):
        if s.get('condition_' + name) != '1':
            raise ValueError('unverified control read: ' + name)
    for name in ('condition_error', 'restore_error'):
        if s.get('condition_' + name) != '0':
            raise ValueError('condition/restore error')
    before, during, restored = (int(s['condition_' + key], 0)
                                for key in ('cntl6_before', 'cntl6_during', 'cntl6_restored'))
    if before not in (0x09, 0x89) or during != (before & ~0x80) or restored != before:
        raise ValueError('unexpected control condition or restoration mismatch')
    for key in ('mode_before', 'mode_after'):
        if int(s['condition_' + key], 0) & 12:
            raise ValueError('pump/reverse mode')
    if int(s['condition_ibus_ua']) != 0:
        raise ValueError('nonzero pump input current')
    if not 4500000 <= int(s['condition_vbus_uv']) <= 5500000:
        raise ValueError('PC source not bounded5V')
    if not 3500000 <= int(s['condition_vbat_uv']) < 4300000:
        raise ValueError('ADC outside unchanged passive PC qualification range')
    if not 225 <= int(s['condition_die_decic']) < 420:
        raise ValueError('die temperature outside passive PC range')
    if int(s['condition_faults'], 0) not in (0, 128):
        raise ValueError('new SM5440 fault')
    if int(s['condition_faults'], 0) == 128:
        # The unchanged driver must have classified the PRE-conversion latch.
        # Live/repeated REVBLK is never accepted merely because bitmap=0x80.
        if s.get('startup_faults') != '0x80' or s.get('startup_pending') != '2':
            raise ValueError('REVBLK not retained by original startup classifier')
        before_int = [int(x, 16) for x in s['condition_int'].split()]
        live = [int(x, 16) for x in s['condition_status'].split()]
        if (len(before_int) != 4 or before_int[:2] != [0, 0]
                or before_int[2] not in (0x22, 0x62) or before_int[3] not in (0, 1)
                or live != [0, 0, 0x20, 0]):
            raise ValueError('live/unclassified REVBLK context')
    elif s.get('startup_pending') != '0':
        raise ValueError('unexpected startup confirmation state')
    if s.get('condition_gauge_attempted') != '1' or s.get('condition_gauge_ret') != '0':
        raise ValueError('adjacent gauge unavailable')
    rows = [json.loads(line) for line in kernel_json.splitlines() if line.strip()]
    if not rows or {r['_BOOT_ID'] for r in rows} != {boot_id.replace('-', '')}:
        raise ValueError('missing/mixed journal boot')
    pattern = re.compile(r'sm5440-passive 0-0063: startup voltage pair seq=(\d+) '
                         r'ADC-start=(\d+)ms ADC-read=(\d+)ms VBAT=(\d+)uV '
                         r'gauge-start=(\d+)ms gauge-end=(\d+)ms gauge-ret=(-?\d+) '
                         r'gauge=(-?\d+)uV')
    pairs = []
    for row in rows:
        message = row.get('MESSAGE', '')
        if 'startup voltage pair' in message:
            match = pattern.fullmatch(message)
            if not match:
                raise ValueError('unparsed startup pair')
            pairs.append(tuple(int(x) for x in match.groups()))
    if len(pairs) != 1:
        raise ValueError('expected exactly one conversion/pair')
    seq, start, end, uv, gauge_start, gauge_end, ret, gauge_uv = pairs[0]
    if seq != 1 or ret or not 0 < start <= end <= gauge_start <= gauge_end:
        raise ValueError('invalid conversion/gauge provenance')
    if uv != int(s['condition_vbat_uv']) or gauge_uv != int(s['condition_gauge_uv']):
        raise ValueError('journal/snapshot pair mismatch')
    for key, stamp in [('adc_read_completed_ms', end), ('gauge_started_ms', gauge_start),
                       ('gauge_completed_ms', gauge_end)]:
        if int(s['condition_' + key]) != stamp:
            raise ValueError('journal/snapshot timestamp mismatch')
    if not 3500000 <= gauge_uv < 4300000:
        raise ValueError('gauge pack outside entry range')
    return dict(verdict='OFF_CONDITION_COMPARISON_CAPTURED' if before & 128
                else 'NO_ENHIZ_CONDITION_CHANGE', boot_id=boot_id.replace('-', ''),
                cntl6_before=before, cntl6_during=during, cntl6_restored=restored,
                conversion_seq=seq, acquisition_interval_ms=end-start,
                ADC_vbat_uv=uv, adjacent_gauge_uv=gauge_uv,
                gauge_minus_ADC_uv=gauge_uv-uv, source_calibrated=False,
                physical_freshness_grant=False, charging_authorized=False,
                PPS=False, pump_ON=False)
