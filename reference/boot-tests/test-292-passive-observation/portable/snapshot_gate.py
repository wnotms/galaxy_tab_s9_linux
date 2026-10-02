"""Pure cached-snapshot gate; no hardware/transport operations or calibration."""


def validate_snapshot(raw, voltage=5):
    values = {}
    for line in raw.splitlines():
        key, sep, value = line.partition('=')
        if not sep or key in values:
            raise ValueError('malformed/duplicate snapshot field')
        values[key] = value
    expected = dict(format='sm5440-passive-v1', registers_are_cached='1',
                    independently_calibrated='0', pump_enable_supported='0',
                    sample_present='1', sample_valid='1', sample_fresh='1',
                    stopped='0', fault='0', startup_pending='0',
                    last_sample_error='0', sample_faults='0x0')
    if any(values.get(k) != v for k, v in expected.items()):
        raise ValueError('snapshot format/availability/fault gate')
    if voltage not in (5, 9):
        raise ValueError('unregistered voltage')
    if not 0 <= int(values['sample_age_ms']) <= 2500:
        raise ValueError('stale sample')
    if not 0 < int(values['sample_stamp_jiffies']) <= int(values['capture_jiffies']):
        raise ValueError('invalid sample chronology')
    for key in ('sample_mode_before', 'sample_mode_after'):
        if not 0 <= int(values[key], 16) <= 255 or int(values[key], 16) & 0x0c:
            raise ValueError('pump not OFF')
    for key in ('sample_cntl2', 'sample_vbuscntl', 'sample_vbatcntl', 'sample_prtncntl'):
        if not 0 <= int(values[key], 16) <= 255:
            raise ValueError('invalid protection byte')
    arrays = {}
    for prefix in ('sample', 'startup'):
        for name, count in (('int', 4), ('status', 4), ('adc', 11)):
            tokens = values[prefix + '_' + name].split()
            if len(tokens) != count or any(len(x) != 2 for x in tokens):
                raise ValueError('raw register array length')
            nums = [int(x, 16) for x in tokens]
            if any(not 0 <= n <= 255 for n in nums):
                raise ValueError('raw register byte')
            arrays[prefix + '_' + name] = nums
    # Exact existing Samsung-derived sm5440-hw.h conversions, not calibration.
    adc = arrays['sample_adc']
    def raw13(offset):
        return (adc[offset] << 5) | (adc[offset + 1] >> 3)
    decoded = dict(sample_vbus_uv=4096000 + raw13(0) * 1000,
                   sample_vbat_uv=2048000 + raw13(9) * 500,
                   sample_ibus_ua=raw13(4) * 625,
                   sample_die_decic=225 + adc[8] * 5)
    if any(int(values[k]) != n for k, n in decoded.items()):
        raise ValueError('raw/decoded conversion mismatch')
    lower, upper = (4500000, 5500000) if voltage == 5 else (8500000, 9500000)
    if not lower <= decoded['sample_vbus_uv'] <= upper:
        raise ValueError('VBUS telemetry outside registered bound')
    if not (2500000 <= decoded['sample_vbat_uv'] < 4300000 and
            decoded['sample_ibus_ua'] == 0 and 225 <= decoded['sample_die_decic'] < 600):
        raise ValueError('unsafe passive ADC telemetry')
    retained = int(values['startup_faults'], 16)
    if retained not in (0, 0x80) or values['startup_retained'] != str(int(bool(retained))):
        raise ValueError('unexpected retained startup fault')
    return values
