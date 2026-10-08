#!/usr/bin/env python3
"""Registered Test346 collection/observation; no new PPS/pump request here."""
import json
import queue
import shlex
import subprocess
import threading
import time
from pathlib import Path


def record_failure(f, result):
    if not (f.R/'first-failure.json').exists():
        f.write(f.R/'first-failure.json',result)


def enrolled(f):
    f.verify_inputs(require_push=True)
    if not f.authorized():
        raise ValueError('explicit300s execution scope required')
    start=f.read(f.R/'startup-summary.json')
    state=f.read(f.R/'mutation-state.json')
    if not state.get('rollback_required') or state.get('candidate_boot_id')!=start['boot_id']:
        raise ValueError('registered candidate not active')
    return start,state


def classify(f,raw,boot,uptime):
    old=(f.R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
    known={json.loads(x)['MESSAGE'] for x in old.splitlines() if int(json.loads(x).get('PRIORITY',7))<=3}
    rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
    result=f.h.g.evidence.inspect_journal(raw,boot,known,require_start=True,
        accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),
        accepted_qca_cycles=True,observed_uptime=uptime)
    bounded={n for group in f.h.g.startup_triplets(rows,True) for n in group['rows']}
    if result['fault_counts'] or any(x['row'] not in bounded for x in result['suspects']):
        raise ValueError('new full-journal fault/suspect')
    return result


def status_command(state):
    folder=state['guardian_folder']
    if folder!='/tmp/gts9-test346-monitor':
        raise ValueError('unregistered guardian folder')
    pid=int(state['guardian_pid'])
    if pid<=1:
        raise ValueError('invalid guardian PID')
    return ('from pathlib import Path; import json; p=Path('+repr(folder)+'); '
            'finished=(p/"evidence/finished").is_file(); '
            'cmd=Path("/proc/'+str(pid)+'/cmdline"); '
            'alive=cmd.exists() and '+repr(folder+'/guard.py')+' in cmd.read_bytes().decode(errors="replace"); '
            'print(json.dumps(dict(finished=finished,alive=alive,summary=json.loads((p/"evidence/summary.json").read_text()) if finished else None,stderr=(p/"stderr.txt").read_text())))')


def monitor(f):
    start,state=enrolled(f)
    if state['phase']!='owner-confirmed-single-activation':
        raise ValueError('one activation required before monitoring')
    rec=f.p.Recorder(f.R/('physical-monitor-'+str(time.time_ns())))
    began=time.monotonic();index=0
    while True:
        try:
            raw,_=f.wifi_command(rec,'status-%03d'%index,start['transport']['wifi'],
                                'python3 -c '+shlex.quote(status_command(state)))
        except Exception as exc:
            result=dict(verdict='GUARDIAN_CURRENT_STATE_UNKNOWN_TRANSPORT_FAILURE',
                        error=repr(exc),guardian_pid=state['guardian_pid'],
                        restart_allowed=False,native_failure_claim=False)
            f.write(rec.folder/'summary.json',result)
            # Raw failed probe is retained by Recorder. A subsequent call may
            # inspect this exact PID; never restart a possibly running guardian.
            return result
        index+=1;status=json.loads(raw)
        if status['finished']:
            result=status['summary']
            f.write(rec.folder/'summary.json',result)
            if result.get('verdict')!='BOUNDED_NATIVE_RETURN_PASS':
                record_failure(f,result)
            return result
        if not status['alive']:
            result=dict(verdict='STOP_GUARDIAN_MISSING_NO_TERMINAL_EVIDENCE',status=status)
            f.write(rec.folder/'summary.json',result);record_failure(f,result)
            return result
        if time.monotonic()-began>=400:
            # Authoritatively live now: an observation deadline is not a
            # completion/restart grant. Resume monitoring this exact PID.
            result=dict(verdict='LIVE_GUARDIAN_OBSERVATION_PENDING',status=status,
                        guardian_pid=state['guardian_pid'],restart_allowed=False)
            f.write(rec.folder/'summary.json',result)
            return result
        time.sleep(2)


def collect(f):
    start,state=enrolled(f)
    rec=f.p.Recorder(f.R/'physical-collection')
    code='from pathlib import Path; import json; p=Path('+repr(state['guardian_folder'])+'); assert (p/"evidence/finished").exists(); print(json.dumps({str(x.relative_to(p)):x.read_text() for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts}))'
    raw,_=f.wifi_command(rec,'guardian-files',start['transport']['wifi'],'python3 -c '+shlex.quote(code))
    files=json.loads(raw)
    for name,data in files.items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe guardian evidence path')
        target=f.R/'device-guardian'/path
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x') as out:out.write(data)
    raw,_=f.wifi_command(rec,'kernel-json',start['transport']['wifi'],'journalctl -k -b -o json --no-pager')
    guardian=json.loads(files['evidence/summary.json'])
    rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
    events=[json.loads(x) for x in files['evidence/events.jsonl'].splitlines() if x.strip()]
    active=[x['data'] for x in events if x['kind']=='sample' and x['data']['adc']['mode']==4]
    result=dict(verdict='STOP',guardian=guardian,boot_id=start['boot_id'],
                active_samples=len(active),rollback_required=True)
    if active:
        result['statistics']=dict(max_raw_ibus_ua=max(x['adc']['ibus_ua'] for x in active),
            max_pack_temp_decic=max(int(x['battery']['POWER_SUPPLY_TEMP']) for x in active),
            max_die_temp_decic=max(x['adc']['die_decic'] for x in active),calibrated=False)
    try:
        if guardian.get('verdict')!='BOUNDED_NATIVE_RETURN_PASS':
            raise ValueError('guardian non-clean')
        g=f.load('collected346_guard',f.R/'guard.py')
        proof=g.native_proof(rows,start['boot_id'],required=True)
        if proof!=guardian['native']:
            raise ValueError('native proof drift')
        samples=[x['data'] for x in events if x['kind']=='sample']
        if not samples or not active:
            raise ValueError('live pump evidence missing')
        classified=classify(f,raw,start['boot_id'],samples[-1]['boottime_seconds'])
        cleanups=[x['data'] for x in events if x['kind']=='cleanup']
        if len(cleanups)!=1 or not cleanups[0].get('fixed9_restored') or not cleanups[0].get('driver_unbound') or cleanups[0]['pump_mode']&12:
            raise ValueError('cleanup OFF/unbound/fixed9 missing')
        f.write(rec.folder/'journal-classification.json',classified)
        result.update(verdict='PASS',native=proof,cleanup=cleanups[0])
    except Exception as exc:
        result['error']=repr(exc);record_failure(f,result)
    f.write(rec.folder/'summary.json',result)
    return result


def accepted(f,entries,rc,phase,plan):
    verdicts=[x for x in entries if x['kind']=='verdict']
    journals=[x for x in entries if x['kind']=='journal-after']
    units=[x for x in entries if x['kind']=='systemd-failed']
    if rc or len(verdicts)!=1 or verdicts[0].get('verdict')!='PASS' or verdicts[0].get('phase')!=phase or len(journals)!=1 or len(units)!=1 or units[0]['raw'].strip():
        raise ValueError('missing/non-clean observer/journal/unit evidence')
    if not any(x['kind']=='armed' for x in entries) or not any(x['kind']=='journal-before' for x in entries):
        raise ValueError('missing observer initial evidence')
    g=f.load('accepted346_guard',f.R/'guard.py')
    proof=g.native_proof([json.loads(x) for x in journals[0]['raw'].splitlines()],plan['boot_id'],required=True)
    if verdicts[0].get('native')!=proof:
        raise ValueError('native verdict drift')
    from ordinary_charge_window import validate_safety,charging_ready
    samples=[x for x in entries if x['kind']=='sample']
    if not samples or verdicts[0]['observation_seconds']<plan[phase+'_seconds']:
        raise ValueError('incomplete observation window')
    previous=None
    for d in samples:
        validate_safety(d,plan)
        if previous is not None and not 0<d['monotonic']-previous<=plan['sample_gap_max_seconds']:
            raise ValueError('response gap')
        previous=d['monotonic']
    endpoint=verdicts[0]['endpoint'];validate_safety(endpoint,plan)
    if phase=='charge' and not charging_ready(endpoint):
        raise ValueError('fixed9 ordinary charging missing')
    if phase=='discharge' and not (endpoint['tcpm'].get('POWER_SUPPLY_ONLINE')=='0' and endpoint['usb'].get('POWER_SUPPLY_ONLINE')=='0' and endpoint['battery']['POWER_SUPPLY_STATUS']=='Discharging' and int(endpoint['battery']['POWER_SUPPLY_CURRENT_NOW'])<0):
        raise ValueError('discharge missing')
    result=dict(verdicts[0],ssh_returncode=rc)
    classified=classify(f,journals[0]['raw'],plan['boot_id'],endpoint['uptime'])
    return result,journals[0]['raw'],classified


def observe(f,phase):
    start,state=enrolled(f)
    if (f.R/'first-failure.json').exists() or f.read(f.R/'physical-collection/summary.json')['verdict']!='PASS':
        raise ValueError('native clean collection required')
    if phase=='discharge' and f.read(f.R/'charge/summary.json')['verdict']!='PASS':
        raise ValueError('ordinary charge must pass first')
    folder=f.R/phase
    if folder.exists():
        raise ValueError('one observer per phase; no overwrite/replay')
    rec=f.p.Recorder(folder);plan=dict(f.PLAN,boot_id=start['boot_id']);proc=None
    result=dict(verdict='STOP',phase=phase)
    from windows_ssh_transport import ssh_argv
    bundle='import sys,types\n'
    for name,path in [('ordinary_charge_window',f.ROOT/'scripts/ordinary_charge_window.py'),('bounded346_guard',f.R/'guard.py')]:
        bundle+=f'm=types.ModuleType({name!r});sys.modules[{name!r}]=m;exec({path.read_text()!r},m.__dict__)\n'
    bundle+=(f.R/'observe-post-return.py').read_text()
    argv=ssh_argv(plan['key'],plan['known_hosts'],plan['alias'],start['transport']['wifi'],
        'python3 - '+shlex.quote(json.dumps(plan))+' '+phase,
        transport=plan['ssh_transport'],windows_python=plan['windows_python'])
    f.write(folder/'command.json',dict(argv=argv,read_only=True))
    try:
        with (folder/'observer.jsonl').open('x') as raw,(folder/'stderr.txt').open('x') as err:
            proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
            proc.stdin.write(bundle);proc.stdin.close();lines=queue.Queue()
            def feed():
                for line in proc.stdout:lines.put(line)
                lines.put(None)
            threading.Thread(target=feed,daemon=True).start();began=time.monotonic()
            while True:
                if time.monotonic()-began>plan['host_outer_seconds']:
                    raise TimeoutError('host observer outer deadline')
                line=lines.get(timeout=12)
                if line is None:break
                raw.write(line);raw.flush();entry=json.loads(line)
                if entry['kind'] in ('armed','verdict'):
                    print(json.dumps(dict(kind=entry['kind'],phase=phase,verdict=entry.get('verdict'))),flush=True)
            rc=proc.wait(timeout=3)
        entries=[json.loads(x) for x in (folder/'observer.jsonl').read_text().splitlines()]
        result,journal,classified=accepted(f,entries,rc,phase,plan)
        (folder/'kernel-json.txt').write_text(journal)
        f.write(folder/'journal-classification.json',classified)
    except Exception as exc:
        result.update(error=repr(exc));record_failure(f,result)
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill();proc.wait(timeout=3)
        f.write(folder/'summary.json',result)
    return result


def pc_return(f):
    start,state=enrolled(f)
    if (f.R/'first-failure.json').exists() or f.read(f.R/'discharge/summary.json')['verdict']!='PASS':
        raise ValueError('clean discharge required; otherwise restore directly')
    rec=f.p.Recorder(f.R/'PC-return');f.p.SERIAL='gts9wifi-0001'
    command='set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@identity; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; echo @@services; systemctl is-active ssh gts9-adbd gts9-usb-acm; echo @@network; ip -4 -o addr; echo @@roles; cat /sys/class/typec/port0/power_role /sys/class/typec/port0/data_role; echo @@failed; systemctl --failed --no-legend --plain --no-pager; echo @@boot-end; cat /proc/sys/kernel/random/boot_id'
    result=dict(verdict='STOP')
    try:
        raw,_=rec.adb('state',command,timeout=15);sec=f.h.g.baseline.sections(raw)
        if sec['boot'].strip().replace('-','')!=start['boot_id'] or sec['boot-end'].strip().replace('-','')!=start['boot_id']:
            raise ValueError('PCreturn boot attribution')
        if sec['identity'].splitlines()[0].split()[0]!=f.PLAN['candidate_config_sha256'] or sec['identity'].splitlines()[1].split()[0]!=f.PLAN['candidate_notes_sha256']:
            raise ValueError('PCreturn kernel identity')
        if sec['services'].splitlines()!=['active']*3 or 'usb0    inet 169.254.42.1/' not in sec['network'] or sec['roles'].splitlines()!=['[sink]','[device]'] or sec['failed'].strip():
            raise ValueError('PCreturn rescue/role/unit')
        code=(f.R/'observe-post-return.py').read_text().split("if __name__ == '__main__':")[0]+"\nprint(json.dumps(dict(value=pump(),boot=text('/proc/sys/kernel/random/boot_id').replace('-',''),driver_bound=Path('/sys/bus/i2c/devices/0-0063/driver').exists())))"
        raw,_=rec.adb('pump-off','python3 -c '+shlex.quote(code),timeout=8);pump=json.loads(raw)
        if pump['boot']!=start['boot_id'] or pump['driver_bound'] or pump['value']&12:
            raise ValueError('PCreturn OFF/unbound')
        windows,_=rec.ps('windows-usb',f.p.PS_USB,timeout=20)
        import re
        if f.p.has_code43(windows) or not re.search(r'ProblemCode\s*:\s*0\b',windows):
            raise ValueError('Windows enumeration')
        result=dict(verdict='PASS',boot_id=start['boot_id'],ADB=True,device_NCM=True,
                    Code43=False,pump_OFF=True,driver_unbound=True,rollback_required=True)
    except Exception as exc:
        result['error']=repr(exc);record_failure(f,result)
    f.write(rec.folder/'summary.json',result)
    return result


def run(f,action):
    if action=='monitor':return monitor(f)
    if action=='collect':return collect(f)
    if action in ('charge','discharge'):return observe(f,action)
    if action=='pc-return':return pc_return(f)
    raise ValueError('unknown read-only phase')
