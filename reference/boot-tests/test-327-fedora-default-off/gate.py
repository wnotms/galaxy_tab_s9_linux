#!/usr/bin/env python3
"""Pure default-OFF admission; no native ADC/deadline or active PPS assumptions."""
import json,re

def values(raw):return dict(x.split('=',1) for x in raw.splitlines() if '=' in x)
def identity(s,plan,phase,expected=None):
    boot=s['boot'].strip().replace('-','')
    if not re.fullmatch('[0-9a-f]{32}',boot) or s['boot-end'].strip().replace('-','')!=boot or (expected and expected!=boot):raise ValueError('mixed/unexpected boot')
    if '7.2.0-rc3-gts9wifi-dirty' not in s['uname'] or s['cmdline'].strip()!=plan['runtime_cmdline']:raise ValueError('release/cmdline')
    if [x.split()[0] for x in s['identity'].splitlines()]!=[plan[phase+'_config_sha256'],plan[phase+'_notes_sha256']]:raise ValueError('kernel identity')
    b=values(s['battery']);u=values(s['usb']);t=values(s['tcpm'])
    if b.get('POWER_SUPPLY_PRESENT')!='1' or b.get('POWER_SUPPLY_HEALTH')!='Good' or b.get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN')!='4440000':raise ValueError('pack health/design')
    soc=int(b['POWER_SUPPLY_CAPACITY']);v=int(b['POWER_SUPPLY_VOLTAGE_NOW']);temp=int(b['POWER_SUPPLY_TEMP'])
    if not plan['flash_soc_min']<=soc<plan['flash_soc_max'] or not 3500000<=v<plan['vbat_max_uv'] or not plan['pack_temp_min_decic']<=temp<plan['pack_temp_max_decic']:raise ValueError('ordinary entry limits')
    pack=s['pack-thermal'].splitlines()
    if len(pack)!=3 or pack[:2]!=['sm5714-battery','enabled'] or abs(int(pack[2])-100*temp)>500 or not 20000<=int(pack[2])<38000:raise ValueError('real pack sensor')
    if s['dcc'].strip()!='absent' or s['failed'].strip() or s['services'].splitlines()!=['active']*3 or s['roles'].splitlines()!=['[sink]','[device]']:raise ValueError('DCC/services/roles')
    if 'usb0    inet 169.254.42.1/' not in s['network']:raise ValueError('device NCM')
    if u.get('POWER_SUPPLY_ONLINE')!='1' or '[SDP]' not in u.get('POWER_SUPPLY_USB_TYPE','') or t.get('POWER_SUPPLY_ONLINE')!='1' or '[PD_PPS]' in t.get('POWER_SUPPLY_USB_TYPE',''):raise ValueError('ordinary PC source')
    if int(t['POWER_SUPPLY_VOLTAGE_NOW'])!=5000000 or int(t['POWER_SUPPLY_VOLTAGE_MAX'])!=5000000 or not 100000<=int(t['POWER_SUPPLY_CURRENT_MAX'])<=3000000:raise ValueError('fixed5 source')
    budget=min(1800000,int(t['POWER_SUPPLY_CURRENT_MAX']));limit=int(u['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])
    if not 100000<=limit<=budget or (limit-100000)%25000:raise ValueError('ordinary input budget')
    if phase=='candidate' and (s['direct-default'].strip() not in ('N','0') or s['driver'].strip().split('/')[-1]!='sm5440-fedora'):raise ValueError('new provider/defaultOFF')
    return boot,dict(soc=soc,voltage_uv=v,temp_decic=temp,current_ua=int(b['POWER_SUPPLY_CURRENT_NOW']),input_limit_ua=limit)

def pump(raw,boot,phase):
    d=json.loads(raw)
    if d['boot_before'].replace('-','')!=boot or d['boot_after'].replace('-','')!=boot:raise ValueError('pump boot')
    if d['driver']!=('sm5440-fedora' if phase=='candidate' else 'sm5440-passive') or d['register']!=0x10 or d['config_data_written'] is not False or not 0<=d['value']<=255 or d['value']&12:raise ValueError('unverified pump OFF')
    return d
