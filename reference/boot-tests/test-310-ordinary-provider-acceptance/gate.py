#!/usr/bin/env python3
"""Pure Test309 evidence checks. No transport, device writes or charging grant."""
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



def program_controls(raw, boot):
    data = json.loads(raw)
    if data['boot_id_before'].replace('-', '') != boot or data['boot_id_after'].replace('-', '') != boot:
        raise ValueError('register/boot attribution')
    if data['register_data_writes'] is not False or data['only_atomic_pointer_reads'] is not True:
        raise ValueError('register access is not read-only')
    if data['bound_driver'] != 'sm5714-battery':
        raise ValueError('wrong register provider')
    regs = data['stable_registers']
    if set(regs) != {'0x0d', '0x0e', '0x13', '0x14', '0x15', '0x18', '0x1a'}:
        raise ValueError('stable control evidence incomplete')
    v = {k: int(x, 0) for k, x in regs.items()}
    if any(not 0 <= x <= 255 for x in v.values()):
        raise ValueError('invalid register byte')
    if not v['0x0d'] & 1 or v['0x0d'] & 4 or v['0x0e'] & 128:
        raise ValueError('charger POK/OVP/watchdog fault')
    if not v['0x13'] & 8 or v['0x14'] & 15 != 5:
        raise ValueError('ordinary Q4/mode not enabled')
    if v['0x15'] & 127 > 16 or v['0x18'] != 32 or v['0x1a'] & 63 != 45:
        raise ValueError('PC input/fast/4.44V programming mismatch')
    return dict(verdict='ORDINARY_PC_CONTROLS_VERIFIED', boot_id=boot,
                input_limit_ma=100 + (v['0x15'] & 127) * 25,
                fast_code=v['0x18'], float_code=v['0x1a'] & 63,
                AICL_lower_limit_allowed=True, direct_charging_authorized=False)


def program_history(kernel_json, boot):
    rows = [json.loads(line) for line in kernel_json.splitlines() if line.strip()]
    if not rows or {r['_BOOT_ID'] for r in rows} != {boot}:
        raise ValueError('empty/mixed programming journal')
    mismatch, recovery = [], []
    for row in rows:
        message = row.get('MESSAGE', '')
        if message.startswith('sm5714 ') or message.startswith('sm5714-battery '):
            if any(x in message for x in ('cannot open Q4 charging path:',
                                          'ordinary charge configuration failed:',
                                          'charge safety read failed;',
                                          'pack thermistor unavailable;',
                                          'charging suspended at pack temperature')):
                raise ValueError('ordinary charge safety/configuration failure')
            if 'ordinary program mismatch:' in message:
                mismatch.append(int(row['_SOURCE_BOOTTIME_TIMESTAMP']))
            elif 'ordinary program recovery: verified' in message:
                recovery.append(int(row['_SOURCE_BOOTTIME_TIMESTAMP']))
            elif any(x in message for x in ('ordinary program recovery:', 'program recovery inhibited:',
                                            'program recovery Q4 OFF unproven:',
                                            'program recovery minimum input unproven:')):
                raise ValueError('ordinary recovery not verified/failed')
    if not mismatch and not recovery:
        return dict(classification='NO_PROGRAM_DRIFT_DETECTED', recovery_observed=False)
    if len(mismatch) != 1 or len(recovery) != 1 or not 0 <= recovery[0] - mismatch[0] <= 5_000_000:
        raise ValueError('second/missing/unbounded program recovery')
    return dict(classification='ONE_NATURAL_PROGRAM_RECOVERY_VERIFIED',
                recovery_observed=True, mismatch_us=mismatch[0], recovered_us=recovery[0])
