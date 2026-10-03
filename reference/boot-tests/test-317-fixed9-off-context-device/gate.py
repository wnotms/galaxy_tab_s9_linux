"""Pure fixed9 OFF-context evidence gates; no device or charging authorization."""
import importlib.util
import json
from pathlib import Path
import re

R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixed317_ordinary',R.parent/'test-313-adc-condition-comparison/ordinary-gate.py')
ordinary=importlib.util.module_from_spec(spec);spec.loader.exec_module(ordinary)
values=ordinary.values
battery_entry=ordinary.battery_entry

def require(condition, message):
    if not condition:raise ValueError(message)

def num(s,key):return int(s[key],0)
def octets(s,key,n):
    out=[int(x,16) for x in s[key].split()]
    require(len(out)==n and all(0<=x<=255 for x in out),'raw bytes: '+key)
    return out

def sample(s,prefix,allow_initial=False):
    n=lambda k:num(s,prefix+'_'+k)
    require(n('valid')==(0 if prefix=='condition' else 1) and not (n('mode_before')|n('mode_after'))&12,'sample OFF/valid')
    require(8500000<=n('vbus_uv')<=9500000 and n('ibus_ua')==0,'physical VBUS/IBUS')
    require(2500000<=n('vbat_uv')<=4600000 and 225<=n('die_decic')<420,'sample battery/die')
    require(n('int4_wait')&1 and not n('restore_error'),'ADC ready/cleanup')
    status=octets(s,prefix+'_status',4)
    require(status==[0,0,32,0],'sample live STATUS')
    faults=n('faults')
    require(faults==0 or (allow_initial and faults==128),'sample fault')
    if faults:
        event=octets(s,prefix+'_int',4)
        require(event[:2]==[0,0] and event[2]&2 and not event[2]&~(2|32|64)
                and event[3] in (0,1),'initial exact inactive latch')
    start,end=n('acquired_ms'),n('completed_ms')
    require(0<start<=n('adc_read_completed_ms')<=end and end-start<=500,'oldest ADC interval')
    return dict(seq=n('acquisition_seq'),start=start,end=end,voltage_uv=n('vbat_uv'),faults=faults)

def context(snapshot,kernel_json,boot,port):
    s=values(snapshot);p=values(port);n=lambda k:num(s,k)
    require(s['format']=='sm5440-passive-v1' and s['registers_are_cached']=='1'
            and s['independently_calibrated']=='0' and s['pump_enable_supported']=='0','diagnostic contract')
    for key,value in [('condition_test',1),('condition_attempted',1),('context_phase',10),
                      ('context_error',0),('context_cleanup_error',0),('enhiz_restore_pending',0),
                      ('last_sample_error',0),('sample_valid',1),('fault',0),('stopped',0),('startup_pending',0),
                      ('context_settings_pending',0),('context_lease_retained',1),
                      ('context_controls_state',2),('context_controls_attempted',7),
                      ('context_controls_off_verified',1),('context_controls_operation_error',0),
                      ('context_controls_restore_error',0),('context_controls_witness_valid',1)]:
        require(n(key)==value,'context state: '+key)
    require(n('context_instance')>0 and n('context_source_generation')>0 and n('context_lease')>0,'source/lease identity')
    require(1000<=n('context_budget_ma')<=1500,'fixed budget')
    require(5<=n('context_capacity')<80 and 3500000<=n('context_pack_uv')<4300000
            and 200<=n('context_pack_decic')<380,'real context pack')
    require(0<n('context_started_ms')<=n('context_pack_started_ms')<=n('context_pack_completed_ms')
            <=n('context_completed_ms') and n('context_pack_completed_ms')-n('context_pack_started_ms')<=500,'pack/context timing')
    require(1<=n('context_readiness_checks')<=40,'readiness count')
    octets(s,'context_controls_before',3);octets(s,'context_controls_witness',10)
    require(octets(s,'context_controls_status_before',4)==[0,0,32,0]
            and octets(s,'context_controls_status_after',4)==[0,0,32,0],'OFF controls live status')
    initial=sample(s,'context_initial',True);before=sample(s,'context_before');handoff=sample(s,'context_handoff');final=sample(s,'condition')
    if initial['faults']:
        require(n('context_inactive_revblk')==1,'inactive latch unconfirmed')
        confirmation=sample(s,'context_confirmation')
        require([initial['seq'],confirmation['seq'],before['seq'],handoff['seq'],final['seq']]==[1,2,3,4,5],'two NEW confirmations')
        for label in ('context_confirmation','context_before'):
            for key in ('cntl2','vbuscntl','vbatcntl','prtncntl'):
                require(n(label+'_'+key)==n('context_initial_'+key),'confirmation control drift')
    else:
        require(n('context_inactive_revblk')==0 and [initial['seq'],before['seq'],handoff['seq'],final['seq']]==[1,1,2,3],'comparison conversion order')
    require(before['end']<=handoff['start'] and handoff['end']<=final['start'],'handoff/conversion chronology')
    require(n('condition_pre_status_valid')==1 and octets(s,'condition_pre_status',4)==[0,0,32,0],'pre-change live status')
    for key in ('cntl6_before_valid','cntl6_during_valid','cntl6_restored_valid','gauge_attempted'):
        require(n('condition_'+key)==1,'condition read-validity '+key)
    original=n('condition_cntl6_before')
    require(original in (9,137) and n('condition_cntl6_during')==original&~128
            and n('condition_cntl6_restored')==original,'exact ENHIZ restore')
    require(n('condition_condition_error')==n('condition_restore_error')==n('condition_gauge_ret')==0,'condition/gauge error')
    gauge=n('condition_gauge_uv');adc=n('condition_vbat_uv')
    require(3500000<=gauge<4300000 and 3500000<=adc<4300000 and abs(gauge-adc)<=100000,'post comparison disagreement/range')
    require(n('condition_adc_read_completed_ms')<=n('condition_gauge_started_ms')<=n('condition_gauge_completed_ms')<=final['end'],'adjacent gauge timing')
    require(p['format']=='sm5714-current-port-v1' and num(p,'ret')==0 and num(p,'online')==1
            and num(p,'usb_type') in (6,8,9,10)
            and num(p,'charge_requested')==1 and num(p,'budget_mv')==9000
            and num(p,'budget_ma')==n('context_budget_ma')
            and num(p,'voltage_uv')==9000000 and num(p,'current_ua')==n('context_budget_ma')*1000,'current logical fixed9')
    require(n('context_completed_ms')<=num(p,'started_ms')<=num(p,'completed_ms')
            and num(p,'completed_ms')-num(p,'started_ms')<=500,'current source timing')
    for key in ('instance','source_generation','budget_generation'):
        require(num(p,key)==n('context_'+key),'current source epoch')
    rows=[json.loads(x) for x in kernel_json.splitlines() if x.strip()]
    require(rows and {r['_BOOT_ID'] for r in rows}=={boot.replace('-','')},'missing/mixed kernel journal')
    matches=[]
    pattern=re.compile(r'sm5440-passive 0-0063: startup voltage pair seq=(\d+) ADC-start=(\d+)ms ADC-read=(\d+)ms VBAT=(\d+)uV gauge-start=(\d+)ms gauge-end=(\d+)ms gauge-ret=(-?\d+) gauge=(-?\d+)uV')
    for row in rows:
        if 'startup voltage pair' in row.get('MESSAGE',''):
            match=pattern.fullmatch(row['MESSAGE']);require(match,'unparsed comparison pair');matches.append(tuple(map(int,match.groups())))
    expected=(final['seq'],final['start'],n('condition_adc_read_completed_ms'),adc,
              n('condition_gauge_started_ms'),n('condition_gauge_completed_ms'),0,gauge)
    require(matches==[expected],'unique source-timestamped journal/snapshot pair')
    return dict(verdict='FIXED9_OFF_CONTEXT_COMPARISON_CAPTURED',boot_id=boot.replace('-',''),
                ADC_vbat_uv=adc,gauge_uv=gauge,gauge_minus_ADC_uv=gauge-adc,
                conversion_seq=final['seq'],acquisition_interval_ms=final['end']-final['start'],
                inactive_initial_revblk_retained=bool(initial['faults']),lease_retained=True,
                source_calibrated=False,physical_freshness_grant=False,charging_authorized=False,PPS=False,pump_ON=False)

def handoff_controls(raw,boot):
    data=json.loads(raw);require(data['boot_id_before'].replace('-','')==data['boot_id_after'].replace('-','')==boot,'controls/boot')
    require(data['register_data_writes'] is False and data['only_atomic_pointer_reads'] is True
            and data['bound_driver']=='sm5714-battery','read-only real provider')
    v={k:int(x,0) for k,x in data['stable_registers'].items()}
    require(set(v)=={'0x0d','0x0e','0x13','0x14','0x15','0x18','0x1a'}
            and all(0<=x<=255 for x in v.values()),'control set/bytes')
    require(v['0x0d']&1 and not v['0x0d']&4 and not v['0x0e']&128,'charger POK/OVP/watchdog')
    require(not v['0x13']&8 and not v['0x15']&127,'switching Q4 OFF/min100mA')
    require(v['0x1a']&63==45 and v['0x18']<=134,'ordinary float/fast ceiling')
    return dict(verdict='INHIBITED_SWITCHING_Q4_OFF_INPUT100_VERIFIED',boot_id=boot,ordinary_reenabled=False,charging_authorized=False)
