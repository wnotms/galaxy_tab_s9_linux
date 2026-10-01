"""Battery-only readiness, not passive ADC acceptance or fault clearing."""
def properties(text):
    return dict(x.split('=',1) for x in text.splitlines() if x.startswith('POWER_SUPPLY_'))

def validate_sample(battery, usb, snapshot, initial_temperature):
    if battery.get('POWER_SUPPLY_HEALTH') != 'Good' or battery.get('POWER_SUPPLY_PRESENT') != '1':
        raise ValueError('battery health/presence')
    if usb.get('POWER_SUPPLY_ONLINE') != '0' or battery.get('POWER_SUPPLY_STATUS') != 'Discharging':
        raise ValueError('USB not offline or battery not discharging')
    if not -2100000 <= int(battery['POWER_SUPPLY_CURRENT_NOW']) < 0:
        raise ValueError('unexpected discharge current')
    if not 5 <= int(battery['POWER_SUPPLY_CAPACITY']) <= 100:
        raise ValueError('SOC')
    if not 3400000 <= int(battery['POWER_SUPPLY_VOLTAGE_NOW']) <= 4440000:
        raise ValueError('battery voltage')
    temp=int(battery['POWER_SUPPLY_TEMP'])
    if not 0 <= temp < 420 or temp-initial_temperature >= 100:
        raise ValueError('battery temperature')
    if battery['POWER_SUPPLY_VOLTAGE_MAX_DESIGN'] != '4440000':
        raise ValueError('design voltage changed')
    # The stopped monitor is known failed and cannot supply fresh observations.
    # Preserve that fact; never convert its old cached voltage into live input.
    expected={'format':'sm5440-passive-v1','fault':'1','sample_faults':'0x80',
              'startup_pending':'0','pump_enable_supported':'0','last_sample_error':'0',
              'sample_mode_before':'0x01','sample_mode_after':'0x01'}
    if any(snapshot.get(k)!=v for k,v in expected.items()):
        raise ValueError('known cached monitor state unexpectedly changed')

def gauge_entry_hint(battery):
    # Readiness hint only: gauge and uncalibrated SM5440 ADC are not interchangeable.
    return 5 <= int(battery['POWER_SUPPLY_CAPACITY']) < 80 and int(battery['POWER_SUPPLY_VOLTAGE_NOW']) < 4300000
