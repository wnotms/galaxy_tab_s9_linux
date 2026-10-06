#!/usr/bin/env python3
"""Pure default-OFF admission; no native ADC/deadline or active PPS assumptions."""
import json,re

def values(raw):return dict(x.split('=',1) for x in raw.splitlines() if '=' in x)
def identity(s,plan,phase,expected=None):
    boot=s['boot'].strip().replace('-','')
    if not re.fullmatch('[0-9a-f]{32}',boot) or s['boot-end'].strip().replace('-','')!=boot or (expected and expected!=boot):raise ValueError('mixed/unexpected boot')
    tokens=s['cmdline'].split();flag=plan['cmdline_flag']
    if phase=='candidate':
        if tokens.count(flag)!=1 or s.get('fixed-check','').strip() not in ('Y','1'):raise ValueError('fixed-check opt-in')
        tokens.remove(flag)
    elif s.get('fixed-check','absent').strip() not in ('absent','N','0'):raise ValueError('baseline fixed-check active')
    if '7.2.0-rc3-gts9wifi-dirty' not in s['uname'] or tokens!=plan['runtime_cmdline'].split():raise ValueError('release/cmdline')
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
    if d['driver']!='sm5440-fedora' or d['register']!=0x10 or d['config_data_written'] is not False or not 0<=d['value']<=255 or d['value']&12:raise ValueError('unverified pump OFF')
    return d

PROOF=re.compile(r'fixed return verified: source=(\d+) lease=(\d+) vbus=(\d+)uV samples=(\d+) range=(\d+)\.\.(\d+)mV settled=(\d+)ms raw_ibus=0 pump_off=1')
def fixed_result(raw,boot):
    entries=[json.loads(x) for x in raw.splitlines() if x.strip()]
    results=[x for x in entries if x['kind']=='verdict']
    journals=[x for x in entries if x['kind']=='complete-journal']
    if len(results)!=1 or results[0]['verdict']!='PASS' or results[0]['boot']!=boot or results[0]['observation_seconds']<30:raise ValueError('missing/failed/bounded verdict')
    if len(journals)!=1 or journals[0]['returncode']!=0 or not journals[0]['data'].strip():raise ValueError('missing full journal')
    rows=[json.loads(x) for x in journals[0]['data'].splitlines() if x.strip()]
    if any(x.get('_BOOT_ID','').replace('-','')!=boot for x in rows):raise ValueError('journal boot attribution')
    messages=[str(x.get('MESSAGE','')) for x in rows]
    if sum('fixed return check complete: lease=0 PPS=0 pump_ON=0' in m for m in messages)!=1 or any('fixed return check failed:' in m or 'fixed fallback failed:' in m for m in messages):raise ValueError('check completion/fault')
    proofs=[PROOF.search(m) for m in messages if 'fixed return verified:' in m]
    if len(proofs)!=1 or proofs[0] is None:raise ValueError('unique physical proof missing')
    source,lease,vbus,count,low,high,settled=map(int,proofs[0].groups())
    if not source or not lease or count<3 or settled<100 or not 8550000<=vbus<=9450000 or not 8550<=low<=high<=9450 or high-low>100 or not low*1000<=vbus<=high*1000:raise ValueError('physical proof outside registered bounds')
    samples=[x for x in entries if x['kind']=='sample']
    if not samples or any(x['boot']!=boot or x['pump']&12 or x['config_data_written'] is not False for x in samples):raise ValueError('sample OFF/identity')
    endpoint=results[0]['endpoint'];b=endpoint['battery'];u=endpoint['usb'];p=endpoint['tcpm']
    if endpoint['boot']!=boot or endpoint['pump']&12 or int(b['POWER_SUPPLY_CURRENT_NOW'])<=0 or b.get('POWER_SUPPLY_HEALTH')!='Good' or not 200<=int(b['POWER_SUPPLY_TEMP'])<380:raise ValueError('endpoint battery/OFF')
    if p.get('POWER_SUPPLY_ONLINE')!='1' or int(p['POWER_SUPPLY_VOLTAGE_NOW'])!=9000000 or not 1000000<=int(p['POWER_SUPPLY_CURRENT_MAX'])<=1500000 or u.get('POWER_SUPPLY_ONLINE')!='1' or '[PD]' not in u.get('POWER_SUPPLY_USB_TYPE','') or not 100000<=int(u['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])<=1500000:raise ValueError('endpoint fixed9 switching source')
    return dict(verdict='FIXED9_OFF_RETURN_DEVICE_SCOPE_PASS',boot_id=boot,proof=dict(source=source,lease=lease,vbus_uv=vbus,samples=count,min_mv=low,max_mv=high,settled_ms=settled),observation_seconds=results[0]['observation_seconds'],endpoint=results[0]['endpoint'],sample_count=len(samples),PPS=False,pump_ON=False)
