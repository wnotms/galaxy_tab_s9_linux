#!/usr/bin/env python3
"""Offline, hash-bound timing facts. No command execution or device access."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

A = Path(__file__).resolve().parent
ROOT = A.parents[2]
_spec = importlib.util.spec_from_file_location('frozen275_timing_gate', A.parent/'test-275-passive-fresh-acquisition/gate.py')
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
require = _gate.require


def checked_inputs(root, manifest):
    result = {}
    for name, expected in manifest.items():
        data = (root/Path(name)).read_bytes()
        require(len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256'], 'input identity: '+name)
        result[name] = data
    return result


def timeout_ticks(ms, hz):
    require(ms > 0 and hz > 0 and hz <= 1000 and 1000 % hz == 0, 'unsupported jiffy conversion')
    return (ms + 1000//hz - 1)//(1000//hz)


def profile(source, header, config):
    fresh = source.split('int sm5440_passive_request_fresh(',1)[1].split('EXPORT_SYMBOL_GPL(sm5440_passive_request_fresh)',1)[0]
    budget = int(re.search(r'#define SM5440_FRESH_REQUEST_MS (\d+)U',header)[1])
    polls = int(re.search(r'for \(i = 0; i < (\d+); i\+\+\)',source)[1])
    sleep = int(re.search(r'msleep\((\d+)\);',source)[1])
    hz = int(re.search(r'^CONFIG_HZ=(\d+)$',config,re.M)[1])
    require('CONFIG_ARM64=y' in config and 'CONFIG_64BIT=y' in config,'unsigned long width unknown')
    require(budget == 100 and polls == 12 and sleep == 25 and 'SM5440_ADC_AVG32' in source,'frozen converter policy changed')
    require(fresh.count('ret = -ETIMEDOUT;') == 4,'timeout branch catalog changed')
    require('mod_delayed_work(system_percpu_wq, &sm->work, 0)' in fresh,'worker queue changed')
    ticks = timeout_ticks(sleep,hz)
    return dict(deadline_ms=budget,poll_requested_ms=sleep,poll_timeout_ticks=ticks,
                poll_timeout_nominal_ms=ticks*1000//hz,maximum_polls=polls,
                maximum_requested_sleep_sum_ms=polls*sleep,averaging=32,hz=hz,unsigned_long_bits=64,
                nominal_four_poll_timeout_sum_ms=4*ticks*1000//hz,
                actual_sleep_or_conversion_ms=None,
                timeout_branch_candidates=['initial_budget','wait_expired','post_wake_budget','final_release_budget'],
                diagnostic_cache_freshness_ms=2500,
                tracing={k:('CONFIG_'+k+'=y' in config.splitlines()) for k in ['KPROBES','KRETPROBES','TRACEPOINTS','FUNCTION_TRACER']},
                charging_authorized=False)


def packet(raw):
    sections={}; key=None
    for line in raw.replace('\r','').splitlines():
        if line.startswith('@@'):
            key=line[2:];require(key and key not in sections,'duplicate/empty packet marker')
            sections[key]=[]
        elif key is not None: sections[key].append(line)
        else: require(not line.strip(),'content before packet marker')
    return {k:'\n'.join(v).strip() for k,v in sections.items()}


def snapshot(raw, hz, bits=64):
    require(hz > 0 and bits in (32,64),'snapshot clock profile')
    data={}
    for row in raw.splitlines():
        key,sep,value=row.partition('=');require(sep and key not in data,'snapshot fields')
        data[key]=value
    needed={'format','sample_stamp_jiffies','capture_jiffies','sample_age_ms','sample_valid','fault','last_sample_error','sample_mode_before','sample_mode_after','sample_ibus_ua','sample_int4_wait','sample_fresh'}
    require(needed <= data.keys(),'missing snapshot fields')
    require(data['format']=='sm5440-passive-v1','snapshot format')
    numeric=lambda key:int(data[key],0)
    stamp,capture,age=[numeric(k) for k in ['sample_stamp_jiffies','capture_jiffies','sample_age_ms']]
    modulus=1<<bits
    require(0<=stamp<modulus and 0<=capture<modulus and age>=0,'jiffies width/range')
    ticks=(capture-stamp)%modulus
    require(ticks<modulus//2 and ticks*1000//hz==age,'snapshot age/clock disagreement')
    require(numeric('sample_valid')==1 and numeric('fault')==0 and numeric('last_sample_error')==0,'unavailable/faulted cache')
    require(numeric('sample_mode_before')==numeric('sample_mode_after')==1 and numeric('sample_ibus_ua')==0,'pump not OFF')
    require(numeric('sample_int4_wait') & 1,'converter readiness absent')
    return dict(publication_jiffies=stamp,capture_jiffies=capture,publication_age_ms=age,
                debug_cache_fresh=numeric('sample_fresh'),actual_conversion_ms=None,
                absolute_publication_boottime_ms=None,clock_anchor_available=False)


def case(name, frames, observer_raw, hz):
    require(bool(frames),'missing snapshots')
    observer=_gate.observer(observer_raw)
    require(observer['count']==1 and observer['first_refusal']==1,'audit requires original single-refusal attempt')
    row=observer['rows'][0]
    if row['provider_status']:
        require(all(row[k]==0 for k in ['acquisition_ms','raw_vbus_uv','raw_vbat_uv','raw_ibus_ua','raw_die_decic','raw_online']),'provider error output not cleared')
    boot=None;ids=None;parsed=[]
    for label,raw in frames:
        sec=packet(raw);current=_gate.evidence.canonical_boot_id(sec['boot'])
        require(boot is None or current==boot,'snapshot boot changed')
        require(ids is None or sec['identity']==ids,'snapshot identity changed')
        boot,ids=current,sec['identity']
        item=snapshot(sec['snapshot'],hz);item['label']=label;parsed.append(item)
    deltas=[]
    for old,new in zip(parsed,parsed[1:]):
        ticks=(new['publication_jiffies']-old['publication_jiffies'])%(1<<64)
        require(ticks<(1<<63),'publication clock reversed')
        deltas.append(dict(before=old['label'],after=new['label'],publication_delta_ticks=ticks,
                           publication_delta_ms=ticks*1000//hz,cache_advanced=ticks>0,
                           proves_request_conversion_duration=False))
    return dict(test=name,boot_id=boot,provider_status=row['provider_status'],consumer_status=row['status'],
                observer_request_ms=row['request_ms'],observer_return_ms=row['return_ms'],
                observer_elapsed_ms=row['return_ms']-row['request_ms'],usable=False,
                cleared_fields_are_measurements=False,snapshots=parsed,publication_deltas=deltas,
                timeout_branch='UNKNOWN',phase_durations_ms={k:None for k in ['queue','conversion_ready','publication','delivery','release']},
                hardware_ADC_fault_proven=False,charging_authorized=False)


def analyse(inputs):
    text=lambda key:inputs[key].decode(errors='replace')
    current=profile(text('kernel/drivers/sm5440-direct.c'),text('kernel/drivers/sm5440-hw.h'),text('out/kernel-x710-272-passive/config'))
    cases=[]
    for number,suffix in [(275,'passive-fresh-acquisition'),(277,'revised-passive-observer')]:
        base=f'reference/boot-tests/test-{number}-{suffix}/observation/'
        labels=['before-load-state','sample-00']+(['endpoint-state'] if number==277 else [])
        facts=case(f'Test{number}',[(label,text(base+label+'.txt')) for label in labels],text(base+'terminal-observer.txt'),current['hz'])
        historical=json.loads(text(base+'summary.json'))
        require(_gate.evidence.canonical_boot_id(historical['boot_id'])==facts['boot_id'],'attempt summary attribution')
        facts['original_verdict']=historical['verdict']
        facts['unload_confirmed']=historical.get('unloaded',False)
        cases.append(facts)
    return dict(verdict='OFFLINE_TIMING_AUDIT_COMPLETED_ATTRIBUTION_UNRESOLVED',profile=current,cases=cases,
                device_commands_executed=False,physical_attempts=0,kernel_or_hardware_changed=False,
                deadline_changed=False,PPS=False,pump_ON=False,active_Stage3='NOT READY')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'refuse to overwrite existing report')
    inputs=checked_inputs(ROOT,json.loads((A/'INPUTS.json').read_text()))
    report=analyse(inputs)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')


if __name__=='__main__': main()
