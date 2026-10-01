"""Registered full-battery passive PC window only; no hardware writes."""
def properties(text):
    return dict(x.split('=', 1) for x in text.splitlines() if x.startswith('POWER_SUPPLY_'))

def validate_device(battery, passive, power_role, data_role):
    if battery.get('POWER_SUPPLY_HEALTH') != 'Good' or battery.get('POWER_SUPPLY_PRESENT') != '1':
        raise ValueError('battery health/presence')
    if passive.get('POWER_SUPPLY_HEALTH') != 'Good' or passive.get('POWER_SUPPLY_STATUS') != 'Not charging' or passive.get('POWER_SUPPLY_ONLINE') != '1':
        raise ValueError('passive health/OFF/online')
    if power_role.strip() != '[sink]' or data_role.strip() != '[device]':
        raise ValueError('Sink/Device role')
    for props, key, lo, hi in [
        (battery,'POWER_SUPPLY_CAPACITY',5,100),
        (battery,'POWER_SUPPLY_TEMP',0,419),
        (battery,'POWER_SUPPLY_VOLTAGE_NOW',3500000,4440000),
        (passive,'POWER_SUPPLY_TEMP',225,599),
        (passive,'POWER_SUPPLY_VOLTAGE_NOW',4500000,5500000),
        (passive,'POWER_SUPPLY_CURRENT_NOW',0,0),
    ]:
        if not lo <= int(props[key]) <= hi:
            raise ValueError(key + ' outside registered passive bounds')
    if battery['POWER_SUPPLY_VOLTAGE_MAX_DESIGN'] != '4440000':
        raise ValueError('float-voltage design changed')
    if abs(int(battery['POWER_SUPPLY_CURRENT_NOW'])) > 2100000:
        raise ValueError('unexpected battery current')
