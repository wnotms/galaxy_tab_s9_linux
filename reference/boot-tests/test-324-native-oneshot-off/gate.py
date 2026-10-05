#!/usr/bin/env python3
"""Pure diagnostic evidence parser. OFF data never grants calibration or pump ON."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('oneshot324_baseline',Path(__file__).parent.parent/'test-323-pc-source-budget/gate.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
battery_entry=old.battery_entry
values=old.values

def _oneshot_values(raw):
    result={}
    for line in raw.splitlines():
        if '=' not in line:continue
        key,value=line.split('=',1)
        if key in result:raise ValueError('duplicate evidence field')
        result[key]=value
    return result

def oneshot(raw):
    s=_oneshot_values(raw)
    for key,want in {'oneshot_attempted':1,'oneshot_finished':1,'oneshot_count':4,'oneshot_error':0,'oneshot_cleanup_error':0,'oneshot_off_error':0,'deadline_ms':100,'calibrated':0,'OCP_verified':0,'pump_ON':0}.items():
        if int(s[key])!=want:raise ValueError('native one-shot refusal/incomplete: '+key+'='+s[key])
    if not 1<=int(s['oneshot_readiness_checks'])<=20:raise ValueError('admission bound')
    if int(s['oneshot_first_readiness_error']) not in (0,-11,-16):raise ValueError('unexpected admission failure')
    samples=[];previous=0
    for i in range(4):
        prefix='sample'+str(i)+'_'
        def numbers(name,n,base=10,sep='/'):
            result=[int(x,base) for x in s[prefix+name].split(sep)]
            if len(result)!=n:raise ValueError('invalid sample shape')
            return result
        requested,disabled,acquired,completed=numbers('times',4)
        if not 0<requested<=disabled<=acquired<completed or acquired-disabled<20 or completed-requested>100 or requested<=previous:raise ValueError('native timing/fresh request')
        previous=completed
        if numbers('result',8)!=[0,0,3,1,0,1,1,1]:raise ValueError('READY/cleanup/validity missing')
        if numbers('control',3,16)!=[12,13,223]:raise ValueError('one-shot control differs')
        event=numbers('events',4,16,' ');status=numbers('status',4,16,' ');adc=numbers('adc',11,16,' ')
        if any(not 0<=x<=255 for x in event+status+adc):raise ValueError('register byte range')
        for row in (event,status):
            if row[0]&0x19 or row[1]&2 or row[2]&0xdf or row[3]&6:raise ValueError('hardware fault')
        if not event[3]&1 or not status[2]&32:raise ValueError('new READY/VBUSPOK absent')
        physical=numbers('physical',4)
        raw13=lambda n:(adc[n]<<5)|(adc[n+1]>>3)
        expected=[4096000+raw13(0)*1000,2048000+raw13(9)*500,raw13(4)*625,225+adc[8]*5]
        if physical!=expected:raise ValueError('raw physical conversion differs')
        vbus,vbat,ibus,die=physical
        if not 4500000<=vbus<=9500000 or not 3500000<=vbat<4300000 or ibus or die>=420:raise ValueError('OFF physical limits')
        before=numbers('pack_before',5);after=numbers('pack_after',5)
        if not 0<before[0]<=before[1]<=requested or not completed<=after[0]<=after[1] or after[1]-before[0]>500:raise ValueError('pack bracket timing')
        if any(not 3500000<=pack[2]<4300000 or not 200<=pack[4]<380 for pack in (before,after)):raise ValueError('pack limits')
        samples.append(dict(requested_ms=requested,completed_ms=completed,observation_ms=completed-requested,vbus_uv=vbus,vbat_uv=vbat,ibus_ua=ibus,die_decic=die,pack_before=before,pack_after=after))
    return dict(verdict='OFF_NATIVE_ONESHOT_OBSERVATION_COMPLETE',samples=samples,calibrated=False,software_ocp_verified=False,pump_ON=False,PPS=False,full_port_verdict='NOT_READY')
