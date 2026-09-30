#!/usr/bin/env python3
"""Pure Test258 admission checks; no transport or hardware operations."""
LPCHARGE_NAMES = {
    'pdic_notifier_module.pdic_param_lpcharge', 'nfc_sec.nfc_param_lpcharge',
    'flicker_sensor.flicker_param_lpcharge', 'cpufreq_limit.lpcharge',
    'sec-battery.lpcharge', 'max77705_charger.lpcharge',
    'max77705-fuelgauge.lpcharge', 'p9320_charger.lpcharge',
    's2miw04_charger.lpcharge', 'cps4038_charger.lpcharge',
    'nu1668_charger.lpcharge', 'msm_drm.secdp_param_lpcharge',
    'sec_pon_alarm.lpcharge',
}


def charge_boot_only(actual, accepted):
    """Permit one normal-baseline reboot, never candidate acceptance."""
    def split(text):
        fixed, flags = [], {}
        for token in text.split():
            name, _, value = token.partition('=')
            if name in LPCHARGE_NAMES:
                if value not in {'0', '1'} or name in flags:
                    raise ValueError('invalid/duplicate vendor charging flag')
                flags[name] = value
            else:
                fixed.append(token)
        return fixed, flags
    try:
        new, nf = split(actual)
        old, of = split(accepted)
    except ValueError:
        return False
    return new == old and nf != of and bool(nf) and set(nf.values()) == {'1'} and set(of.values()) <= {'0'}


def passive_errors(battery, passive, power_role, data_role):
    """Reported-value gates only; no ADC calibration or physical OCP claim."""
    errors = []
    if battery.get('POWER_SUPPLY_HEALTH') != 'Good' or battery.get('POWER_SUPPLY_PRESENT') != '1':
        errors.append('battery health/presence')
    if passive.get('POWER_SUPPLY_HEALTH') != 'Good' or passive.get('POWER_SUPPLY_STATUS') != 'Not charging':
        errors.append('passive health/OFF-backed sample unavailable')
    if passive.get('POWER_SUPPLY_ONLINE') != '1':
        errors.append('PC VBUS not reported online')
    if power_role.strip() != '[sink]' or data_role.strip() != '[device]':
        errors.append('Sink/Device role changed')
    for name, properties, key, lower, upper in (
        ('battery SOC', battery, 'POWER_SUPPLY_CAPACITY', 5, 80),
        ('battery temperature', battery, 'POWER_SUPPLY_TEMP', 0, 420),
        ('battery VBAT', battery, 'POWER_SUPPLY_VOLTAGE_NOW', 3500000, 4300000),
        ('passive die temperature', passive, 'POWER_SUPPLY_TEMP', 225, 600),
        ('passive VBUS', passive, 'POWER_SUPPLY_VOLTAGE_NOW', 4500000, 5500001),
        ('passive IBUS', passive, 'POWER_SUPPLY_CURRENT_NOW', 0, 100001),
    ):
        try:
            value = int(properties[key])
        except (KeyError, ValueError, TypeError):
            errors.append(name + ' missing/invalid')
            continue
        if not lower <= value < upper:
            errors.append(name + ' outside registered bounds')
    return errors
