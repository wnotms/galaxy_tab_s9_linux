"""Retained fixed9 acquisition proof, independent of post-return PC power state."""
import importlib.util
import json
import re
from pathlib import Path
spec=importlib.util.spec_from_file_location('oneshot325_pure',Path(__file__).parent.parent/'test-324-native-oneshot-off/gate.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
battery_entry=old.battery_entry
values=old.values


def retained_observation(raw,snapshot,kernel,boot,hold_seconds=30):
    result=old.oneshot(raw)
    if any(not 8500000<=s['vbus_uv']<=9500000 for s in result['samples']):
        raise ValueError('native samples outside fixed9V class')
    s=values(snapshot)
    for name in ('fault','stopped','startup_pending','last_sample_error','pump_enable_supported'):
        if s.get(name)!='0':raise ValueError('retained worker refusal: '+name)
    if s.get('startup_retained')!='1' or int(s['startup_faults'],0)!=128:
        raise ValueError('initial inactive startup event not retained')
    for prefix in ('startup_','sample_'):
        if any(int(s[prefix+k],0)&12 for k in ('mode_before','mode_after')) or int(s[prefix+'ibus_ua']):
            raise ValueError('startup confirmation was not OFF')
        if not 8500000<=int(s[prefix+'vbus_uv'])<=9500000 or not 3500000<=int(s[prefix+'vbat_uv'])<4300000 or not 225<=int(s[prefix+'die_decic'])<420:
            raise ValueError('retained startup physical class')
        if not int(s[prefix+'int4_wait'],0)&1:raise ValueError('startup READY absent')
    if int(s['sample_faults'],0):raise ValueError('last confirmation not clean')
    for k in ('cntl2','vbuscntl','vbatcntl','prtncntl'):
        if int(s['startup_'+k],0)!=int(s['sample_'+k],0):raise ValueError('startup control drift')
    lines=[x for x in kernel.splitlines() if x.strip()]
    if not lines:raise ValueError('kernel journal empty')
    events=[]
    for line in lines:
        d=json.loads(line)
        if d.get('_BOOT_ID')!=boot or d.get('_TRANSPORT')!='kernel':raise ValueError('foreign boot/source kernel row')
        # Receipt timestamps can lag source by seconds; never substitute them.
        t=d.get('_SOURCE_MONOTONIC_TIMESTAMP')
        if not isinstance(t,str) or not re.fullmatch(r'\d+',t):raise ValueError('kernel source timestamp missing')
        events.append((int(t)/1000,d.get('MESSAGE','')))
    events.sort()
    first=result['samples'][0]['requested_ms'];last=result['samples'][-1]['completed_ms']
    awaiting=[t for t,m in events if 'passive startup REVBLK awaiting two fresh confirmations' in m]
    confirmed=[t for t,m in events if 'passive startup REVBLK confirmed inactive; event retained' in m]
    if len(awaiting)!=1 or len(confirmed)!=1 or not awaiting[0]<confirmed[0]<first:
        raise ValueError('unique two-confirmation startup lifecycle absent')
    pairs=[]
    pattern=r'startup voltage pair seq=(\d+) ADC-start=(\d+)ms ADC-read=(\d+)ms VBAT=(\d+)uV'
    for t,m in events:
        match=re.search(pattern,m)
        if match and t<=confirmed[0]:pairs.append(tuple(map(int,match.groups())))
    if len(pairs)!=3 or [p[0] for p in pairs]!=[1,2,3] or any(not 0<p[1]<p[2]<first or not 3500000<=p[3]<4300000 for p in pairs) or any(pairs[i][1]<=pairs[i-1][2] for i in (1,2)):
        raise ValueError('two distinct new startup conversions not proven')
    budgets=[]
    for t,m in events:
        match=re.fullmatch(r'sm5714-usbpd \d+-0033: TCPM Sink budget: (\d+) mV (\d+) mA \(not measured VBUS\)',m)
        if match:budgets.append((t,*map(int,match.groups())))
        if 'PM: suspend entry' in m or 'PM: suspend exit' in m:raise ValueError('suspend invalidates boot/source timestamp equivalence')
        if first<=t<=last and re.search(r'(?i)(hard.?reset|soft.?reset|detach|I2C.*error|TCPC.*fault)',m):raise ValueError('protocol/source fault inside acquisition window')
    prior=[b for b in budgets if b[0]<=first]
    if not prior or prior[-1][1]!=9000 or not 1000<=prior[-1][2]<=1500:
        raise ValueError('no actual fixed9 logical source before native requests')
    bound=prior[-1]
    if any(first<b[0]<=last for b in budgets):raise ValueError('source budget transition inside native window')
    after=[b for b in budgets if b[0]>last]
    if not after or after[0][0]-bound[0]<hold_seconds*1000:
        raise ValueError('registered source hold/PC return not attributed')
    # A detach zero followed by PC5V is expected after retained acquisition.
    if after[0][1] not in (0,5000):raise ValueError('unexplained post-window source transition')
    if not any(b[1]==5000 and 100<=b[2]<=1800 for b in after):raise ValueError('PC5V return not attributed')
    result.update(verdict='RETAINED_FIXED9_OFF_ONESHOT_COMPLETE',logical_source_budget={'started_ms':bound[0],'millivolts':bound[1],'milliamps':bound[2]},source_hold_ms=after[0][0]-bound[0],startup_confirmations=2,source_timestamps=True,late_PC_state_separate=True)
    return result
