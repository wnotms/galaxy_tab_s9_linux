#!/usr/bin/env python3
"""Offline explanation of a retained passive startup refusal; no admission/I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import uuid


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sections(raw):
    parts = re.split(r'^@@([^\n]+)(?:\n|$)', raw.replace('\r', ''), flags=re.M)
    names = parts[1::2]
    require(len(names) == len(set(names)), 'duplicate section')
    return dict(zip(names, parts[2::2]))


def fields(raw):
    result = {}
    for line in raw.splitlines():
        key, sep, value = line.partition('=')
        require(sep and key not in result, 'snapshot malformed/duplicate')
        result[key] = value
    return result


def unsigned(raw, bits=32):
    require(re.fullmatch(r'(?:0x[0-9a-f]+|[0-9]+)', raw) is not None,
            'invalid unsigned encoding')
    value = int(raw, 16 if raw.startswith('0x') else 10)
    require(0 <= value < 2**bits, 'unsigned width')
    return value


def octets(raw, size):
    require(re.fullmatch(r'[0-9a-f]{2}(?: [0-9a-f]{2}){' + str(size-1) + '}', raw)
            is not None, 'raw register byte count/encoding')
    return bytes.fromhex(raw)


def decode_faults(st):
    # Off-mode sm5440_decode_faults(), bit-for-bit oracle tested against C.
    result = 0
    for yes, bit in ((st[0] & 16, 0), (st[0] & 8, 1), (st[0] & 3, 2),
                     (st[2] & 128, 3), (st[2] & 24 or st[1] & 3, 5),
                     (st[2] & 4, 6), (st[2] & 2, 7), (st[2] & 1, 8),
                     (st[3] & 4, 9), (st[3] & 2, 10)):
        if yes:
            result |= 1 << bit
    return result


def sample(snapshot, prefix):
    value = {k: unsigned(snapshot[prefix+'_'+k]) for k in
             ('vbus_uv', 'vbat_uv', 'ibus_ua', 'faults', 'int4_disable',
              'int4_wait', 'mode_before', 'mode_after', 'cntl2', 'vbuscntl',
              'vbatcntl', 'prtncntl')}
    value['die_decic'] = int(snapshot[prefix+'_die_decic'])
    require(-(2**31) <= value['die_decic'] < 2**31, 'temperature width')
    for k in ('int4_disable', 'int4_wait', 'mode_before', 'mode_after',
              'cntl2', 'vbuscntl', 'vbatcntl', 'prtncntl'):
        require(value[k] <= 255, 'register width')
    value['int'] = octets(snapshot[prefix+'_int'], 4)
    value['status'] = octets(snapshot[prefix+'_status'], 4)
    value['adc'] = adc = octets(snapshot[prefix+'_adc'], 11)
    raw13 = lambda a,b: (a << 5) | (b >> 3)
    decoded = dict(vbus_uv=4096000+raw13(adc[0],adc[1])*1000,
                   vbat_uv=2048000+raw13(adc[9],adc[10])*500,
                   ibus_ua=raw13(adc[4],adc[5])*625, die_decic=225+adc[8]*5)
    require(all(value[k] == v for k,v in decoded.items()), 'ADC bytes/value mismatch')
    combined = bytearray(a | b for a,b in zip(value['int'], value['status']))
    combined[3] |= value['int4_disable'] | value['int4_wait']
    require(decode_faults(combined) == value['faults'], 'raw fault bitmap mismatch')
    value['online'] = bool(value['status'][2] & 32)
    return value


def sample_reasons(current, initial):
    """Explain the exact existing sm5440_startup_matches predicate; no waiver."""
    predicates = (
        ('sample_faults', not current['faults']),
        ('mode_before_not_OFF', not (current['mode_before'] & 12)),
        ('mode_after_not_OFF', not (current['mode_after'] & 12)),
        ('ADC_ready_absent', bool(current['int4_wait'] & 1)),
        ('VBUSPOK_absent', current['online']),
        ('VBUS_outside_PC_window', 4500000 <= current['vbus_uv'] <= 5500000),
        ('VBAT_outside_startup_window', 3500000 <= current['vbat_uv'] < 4300000),
        ('IBUS_nonzero', not current['ibus_ua']),
        ('die_temperature_outside_window', 225 <= current['die_decic'] < 420),
    )
    result = [name for name, ok in predicates if not ok]
    result.extend(k+'_changed' for k in ('cntl2','vbuscntl','vbatcntl','prtncntl')
                  if current[k] != initial[k])
    return result


def analyze(current_raw, journal_raw, config_raw, *, boot_id, config_sha256,
            notes_sha256):
    boot = uuid.UUID(boot_id).hex
    sec = sections(current_raw)
    require(uuid.UUID(sec['boot'].strip()).hex == boot, 'snapshot boot identity')
    require(hashlib.sha256(config_raw).hexdigest() == config_sha256, 'resolved config identity')
    ids = sec['identity'].splitlines()
    require(len(ids) == 2 and ids[0].split()[0] == config_sha256 and
            ids[1].split()[0] == notes_sha256, 'captured config/notes identity')
    require(b'CONFIG_HZ=250\n' in config_raw and
            b'# CONFIG_HVC_DCC is not set\n' in config_raw, 'HZ/DCC identity')
    snapshot = fields(sec['snapshot'])
    require(snapshot['format'] == 'sm5440-passive-v1' and
            snapshot['registers_are_cached'] == '1' and
            snapshot['independently_calibrated'] == '0' and
            snapshot['pump_enable_supported'] == '0', 'snapshot contract')
    require(all(snapshot[k] == v for k,v in
                dict(fault='1', startup_pending='1', last_sample_error='0',
                     sample_present='1', sample_valid='1', sample_fresh='0',
                     stopped='0', startup_retained='1').items()),
            'not the retained successful-read startup refusal profile')
    initial, current = (sample(snapshot, p) for p in ('startup', 'sample'))
    require(initial['faults'] == 128 and decode_faults(initial['int']) == 128
            and not decode_faults(initial['status']), 'initial REVBLK profile')
    # A complete successful read can still be unsuitable for the startup policy.
    reasons = sample_reasons(current, initial)
    require(bool(reasons), 'no sample predicate refusal; cannot attribute timeout')
    rows = [json.loads(line) for line in journal_raw.splitlines()]
    require(bool(rows), 'empty kernel journal')
    require(all(row.get('_BOOT_ID') == boot for row in rows), 'journal different/missing boot')
    starts = [row for row in rows if row.get('MESSAGE') ==
              'sm5440-passive 0-0063: passive startup REVBLK awaiting two fresh confirmations']
    failures = [row for row in rows if row.get('MESSAGE') ==
                'sm5440-passive 0-0063: passive startup confirmation failed']
    require(len(starts) == len(failures) == 1, 'missing/duplicate startup transition')
    require(not any('passive startup REVBLK confirmed inactive' in row.get('MESSAGE','')
                    for row in rows), 'contradictory startup completion')
    start_us, fail_us = (unsigned(row['_SOURCE_BOOTTIME_TIMESTAMP'],64)
                        for row in (starts[0],failures[0]))
    require(0 < start_us < fail_us, 'startup source chronology')
    ticks = unsigned(snapshot['sample_stamp_jiffies'],64) - unsigned(snapshot['startup_capture_jiffies'],64)
    # Scope excludes clock rollover; it cannot silently manufacture positive delta.
    require(0 < ticks < 1250, 'deadline/rollover not excluded')
    require(0 < fail_us-start_us < 4900000, 'journal too near/after deadline')
    require(abs(ticks*4000-(fail_us-start_us)) <= 8000,
            'snapshot/journal confirmation time disagreement')
    battery = {}
    # power_supply uevent can repeat TYPE identically; a conflicting value is
    # not evidence. Snapshot field duplicates remain strictly rejected.
    for line in sec['battery'].splitlines():
        if not line.startswith('POWER_SUPPLY_'):
            continue
        key, sep, value = line.partition('=')
        require(sep and (key not in battery or battery[key] == value),
                'contradictory battery property')
        battery[key] = value
    gauge = unsigned(battery['POWER_SUPPLY_VOLTAGE_NOW'])
    return dict(verdict='ATTRIBUTED_PASSIVE_STARTUP_SAMPLE_REFUSAL', boot_id=boot,
                sample_refusal_reasons=reasons, deadline_expiry_excluded=True,
                startup_to_failure_source_us=fail_us-start_us,
                startup_to_last_sample_ticks=ticks, configured_HZ=250,
                raw_ADC_VBAT_hex=current['adc'][9:11].hex(),
                decoded_VBAT_uv=current['vbat_uv'], startup_lower_bound_uv=3500000,
                below_startup_lower_bound_uv=max(0,3500000-current['vbat_uv']),
                gauge_reported_VBAT_uv=gauge,
                retained_ADC_minus_later_gauge_uv=current['vbat_uv']-gauge,
                synchronous_gauge_comparison=False, physical_voltage_error_uv=None,
                voltage_discrepancy_cause='UNKNOWN', independently_calibrated=False,
                changing_bounds_justified=False, same_fault_retry_authorized=False,
                policy_admission=False, active_freshness_grant=False,
                PPS_authorized=False, pump_ON_authorized=False,
                kernel_config_identity=config_sha256, kernel_notes_identity=notes_sha256)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--identity',type=Path,required=True,
                        help='accepted manifest with boot_id/config_sha256/notes_sha256')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=analyze(args.current.read_text(),args.journal.read_text(),args.config.read_bytes(),
                   **json.loads(args.identity.read_text()))
    with args.output.open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
