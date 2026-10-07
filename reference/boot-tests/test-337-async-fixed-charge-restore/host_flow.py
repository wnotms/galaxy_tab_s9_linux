#!/usr/bin/env python3
"""Test337 registered PPS-OFF roundtrip; unconditional exact331 restoration."""
import argparse,hashlib,importlib.util,json,re,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=load('fedora331_base',R.parent/'test-323-pc-source-budget/host_flow.py')
gate=load('fedora331_gate',R/'gate.py');h=base.h
read=base.read;write=base.write

def configure():
    global PLAN,PACKAGE,STAGED
    base.R=R;base.configure();PLAN=base.PLAN;PACKAGE=base.PACKAGE;STAGED=base.STAGED
    h.STAGE='D:/android/gts9-active/gts9-test337';h.TMP='/tmp/gts9-test337'
    base.verify_inputs=verify_inputs;base.identity=identity;base.admission=admission

def identity(raw,phase,expected=None,restoration=False):
    sec=h.g.baseline.sections(raw);boot,battery=gate.identity(sec,PLAN,phase,expected,restoration=restoration)
    return sec,boot,battery,{}

def pump(rec,boot,phase):
    raw,_=rec.adb('pump-off','python3 -c '+shlex.quote((R/'read-pump.py').read_text()),timeout=8)
    d=gate.pump(raw,boot,phase);write(rec.folder/'pump-off.json',d);return d

def scan(rec,boot,uptime):
    raw,_=rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
    old=(R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
    known={json.loads(x)['MESSAGE'] for x in old.splitlines() if int(json.loads(x).get('PRIORITY',7))<=3}
    d=h.g.evidence.inspect_journal(raw,boot,known,require_start=True,accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),accepted_qca_cycles=True,observed_uptime=uptime)
    bounded={n for group in h.g.startup_triplets([json.loads(x) for x in raw.splitlines()],True) for n in group['rows']}
    if d['fault_counts'] or any(x['row'] not in bounded for x in d['suspects']):raise ValueError('new kernel fault/suspect')
    write(rec.folder/'journal-classification.json',d)
    return d

def rescue(rec,sec,boot):
    # Compare to the accepted key; never replace trust with a newly read key.
    from charging_wifi_discovery import Settings, Identity, parse_identity
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',sec['network'])
    if len(addresses)!=1 or sec['host-key'].split()[:2]!=PLAN['host_ed25519_key'].split():
        raise ValueError('WiFi/key baseline changed')
    settings=Settings(addresses[0],Path(PLAN['key']),Path(PLAN['known_hosts']),PLAN['alias'])
    settings.validate()
    raw,_=wifi_command(rec,'wifi-rescue',addresses[0],
        'cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes')
    parse_identity(raw,Identity(PLAN['machine_id'],PLAN['baseline_config_sha256'],PLAN['baseline_notes_sha256'],boot))
    result=dict(wifi=addresses[0],wifi_authenticated=True,rescue='WiFi')
    write(rec.folder/'transport.json',result)
    return result

def preflight_folder():
    pointer=R/'active-preflight.json'
    if not pointer.exists():return R/'preflight'
    current=read(pointer);name=current['folder']
    if not re.fullmatch(r'preflight(?:-refresh-[0-9]+)?',name):raise ValueError('invalid preflight namespace')
    folder=R/name
    if folder.is_symlink() or hashlib.sha256((folder/'summary.json').read_bytes()).hexdigest()!=current['summary_sha256']:raise ValueError('preflight snapshot drift')
    return folder

def preflight():
    verify_inputs();folder=R/'preflight'
    if folder.exists():folder=R/('preflight-refresh-'+str(time.time_ns()))
    rec=p.Recorder(folder)
    raw,_=rec.adb('current-state',PLAN['current_command'],timeout=15);sec,boot,b,unused=identity(raw,'baseline')
    gate.preparation_margin(b,PLAN)
    transport=rescue(rec,sec,boot)
    if not transport['wifi_authenticated']:raise ValueError('fresh authenticated WiFi required before install')
    pump(rec,boot,'baseline')
    raw,_=rec.adb('partitions',base.DEBIAN_PARTS,timeout=20);base.require_debian_partitions(raw,PACKAGE['baseline_partitions'])
    command='set -e; cd /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; test "$(find . -type f | wc -l)" = 181; printf %s '+shlex.quote((R/'rollback-modules.sha256').read_text())+' | sha256sum -c -'
    rec.adb('modules',command,timeout=20);scan(rec,boot,float(sec['uptime'].split()[0]))
    boots,_=rec.adb('boots-before','journalctl --list-boots --no-pager',timeout=20)
    if h.g.evidence.boot_list(boots)[-1]!=boot:raise ValueError('journal history')
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows) or not re.search(r'ProblemCode\s*:\s*0\b',windows):raise ValueError('Windows enumeration')
    result=dict(verdict='READY_FOR_REGISTERED_ONE_BOOT',authenticated_wifi=transport['wifi_authenticated'],rescue_authenticated=True,transport=transport,boot_id=boot,battery=b,collected_at_epoch=time.time(),PPS=False,pump_ON=False)
    write(rec.folder/'summary.json',result)
    write(R/'active-preflight.json',dict(folder=folder.name,summary_sha256=hashlib.sha256((folder/'summary.json').read_bytes()).hexdigest()))
    return result

def admission(folder,phase,before,boots_before):
    rec=p.Recorder(folder);p.SERIAL='gts9wifi-0001';start=time.monotonic();index=0
    while time.monotonic()-start<PLAN['readiness_max_seconds']:
        raw,status=rec.adb('readiness-%02d'%index,'cat /proc/sys/kernel/random/boot_id; systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr',timeout=8,required=False);index+=1
        if status==0 and raw.splitlines().count('active')==3 and '169.254.42.1/' in raw and re.search(r'\bwlp1s0\s+inet\s+',raw):break
        time.sleep(2)
    else:raise TimeoutError('candidate rescue unavailable')
    command=PLAN['candidate_command'] if phase=='candidate' else PLAN['current_command']
    raw,_=rec.adb('current-state',command,timeout=15);sec,boot,b,unused=identity(raw,phase,restoration=True)
    if before and boot==before:raise ValueError('boot did not change')
    pump(rec,boot,phase);transport=rescue(rec,sec,boot)
    raw,_=rec.adb('final-partitions',base.DEBIAN_PARTS,timeout=20);base.require_debian_partitions(raw,PACKAGE['baseline_partitions'])
    rec.adb('final-modules','set -e; cd /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; test "$(find . -type f | wc -l)" = 181; printf %s '+shlex.quote((R/'rollback-modules.sha256').read_text())+' | sha256sum -c -',timeout=20)
    boots,_=rec.adb('boots-after','journalctl --list-boots --no-pager',timeout=20)
    if before and h.g.evidence.attribute(before,boot,boots_before,boots)!='attributed':raise ValueError('unexpected/missing boot attribution')
    scan(rec,boot,float(sec['uptime'].split()[0]))
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows):raise ValueError('Windows Code43')
    result=dict(boot_id=boot,battery=b,device_NCM=True,transport=transport,PPS=False,pump_ON=False,boot_attribution='attributed' if before else 'failed_candidate_history_unavailable')
    write(rec.folder/'summary.json',result);return result,boots


def verify_inputs(require_push=False):
    import hashlib
    inputs=read(R/'INPUTS.json')
    for name,expected in inputs.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('input drift: '+name)
    verify_artifacts()
    if require_push:
        git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration must be pushed')
        controlled=list(inputs)+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*controlled):raise ValueError('uncommitted registered input')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*controlled],check=True,stdout=subprocess.DEVNULL)

def install():
    verify_inputs(require_push=True)
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test337'))
    if not authorized():raise ValueError('explicit PPS-OFF execution scope required')
    if (R/'mutation-state.json').exists():raise ValueError('one install only; inspect mutation state')
    pre=read(preflight_folder()/'summary.json')
    if pre['verdict']!='READY_FOR_REGISTERED_ONE_BOOT' or not pre['rescue_authenticated'] or not 0<=time.time()-pre['collected_at_epoch']<=PLAN['preflight_max_age_seconds']:raise ValueError('fresh authenticated preflight required')
    rec=p.Recorder(R/'installation');p.SERIAL='gts9wifi-0001'
    raw,_=rec.adb('live-boundary',PLAN['current_command'],timeout=15);_,_,battery,_=base.identity(raw,'baseline',pre['boot_id']);gate.preparation_margin(battery,PLAN)
    write(R/'mutation-state.json',dict(rollback_required=True,phase='recovery-requested-no-kernel-write'))
    try:
        h.enter_recovery(rec);base.transfer(rec)
        raw,_=rec.adb('partitions-before',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['baseline_partitions'])
        h.verify_modules(rec,'original-modules','rollback-modules.sha256')
        rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
        write(R/'mutation-state.json',dict(rollback_required=True,phase='before-module-swap'))
        rec.adb('install-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian install {h.TMP}/candidate-modules.sha256 {h.TMP}/candidate-modules.tar.gz {h.TMP}/rollback-modules.sha256',timeout=25)
        h.write_boot(rec,'write-boot','candidate-boot.img',PACKAGE['baseline_partitions']['boot'],PACKAGE['candidate_partitions']['boot'])
        raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['candidate_partitions']);h.clear_unmount(rec)
        state=dict(rollback_required=True,phase='candidate-installed-awaiting-owner-C1-System-boot',allfive_verified=True,modules=181)
        write(R/'mutation-state.json',state);write(rec.folder/'summary.json',state)
        # Deliberately no reboot here: owner changes PC -> charger IN TWRP first.
        return state
    except Exception as exc:
        write(R/'first-failure.json',dict(error=str(exc),phase='installation',stopped=True))
        if p.SERIAL=='R52X10045LT':restore(from_recovery=True)
        else:write(R/'recovery-required.json',dict(error=str(exc),manual_TWRP_required=True,no_blind_retry=True))
        raise

def restore(from_recovery=False):
    if not (R/'mutation-state.json').exists():raise ValueError('no registered mutation')
    verify_inputs(require_push=True);state=read(R/'mutation-state.json')
    if not state['rollback_required']:raise ValueError('already restored; no duplicate boot')
    rec=p.Recorder(R/('manual-rollback-install' if from_recovery else 'rollback-install'))
    if from_recovery:
        p.SERIAL='R52X10045LT';ident,_=rec.adb('twrp-identity','getprop ro.product.device; uname -a; id',timeout=10)
        if 'gts9wifi' not in ident or 'uid=0' not in ident or '7.2.0-rc3' in ident:raise ValueError('manual TWRP identity')
        target,boots=None,None
    else:
        p.SERIAL='gts9wifi-0001';target,_=rec.adb('target-boot-id','cat /proc/sys/kernel/random/boot_id',timeout=8);target=target.strip().replace('-','')
        if state.get('candidate_boot_id') and target!=state['candidate_boot_id']:raise ValueError('unexpected boot before restore')
        boots,_=rec.adb('target-boots','journalctl --list-boots --no-pager',timeout=20);h.enter_recovery(rec)
    base.transfer(rec);raw,_=rec.adb('partitions-before',h.PARTS,timeout=20);current=base.restoration_layout(raw)
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    root='/mnt/debian/usr/lib/modules';saved,_=rec.adb('module-layout',f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; if test -d {root}/.gts9-test337-original; then echo saved; else echo no-saved; fi',timeout=10)
    if saved.strip()=='saved':rec.adb('restore-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256',timeout=25)
    elif saved.strip()!='no-saved' or current!=PACKAGE['baseline_partitions']['boot']:raise ValueError('paired original modules missing')
    h.verify_modules(rec,'restored-modules','rollback-modules.sha256')
    if current!=PACKAGE['baseline_partitions']['boot']:h.write_boot(rec,'restore-boot','rollback-accepted331-boot.img',current,PACKAGE['baseline_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['baseline_partitions']);h.clear_unmount(rec)
    write(rec.folder/'summary.json',dict(verdict='ACCEPTED331_ALLFIVE_181_RESTORED'))
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    final=base.admission(R/('manual-final-acceptance' if from_recovery else 'final-acceptance'),'baseline',target,boots)[0]
    write(R/'mutation-state.json',dict(rollback_required=False,phase='accepted331-restored',final=final));return final


def verify_artifacts():
    for name, meta in PACKAGE['artifacts'].items():
        target = ROOT / meta['path']
        if target.is_symlink() or not target.is_file() or target.stat().st_size != meta['bytes']:
            raise ValueError('artifact missing/size: ' + name)
        with target.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != meta['sha256']:
            raise ValueError('artifact drift: ' + name)


def authorized():
    # This record is written only after a specific owner instruction authorizes
    # Test337 PPS-OFF deployment. Registration alone is never that instruction.
    path = R/'execution-scope.json'
    if not path.exists():return False
    d = read(path)
    return (d.get('test') == 'Test337' and d.get('PPS_OFF') is True and
            d.get('pump_ON') is False and d.get('owner_instruction', '').strip() and
            d.get('registration_sha256') == hashlib.sha256((R/'INPUTS.json').read_bytes()).hexdigest())


def stage():
    """Offline, explicit staging only; does not call ADB or start the candidate."""
    import shutil
    verify_inputs(require_push=True)
    if not authorized():raise ValueError('execution scope not yet authorized')
    folder=Path('/mnt/d/android/gts9-active/gts9-test337')
    folder.mkdir(exist_ok=False)
    mapping={'candidate-boot.img':'boot.img','candidate-modules.tar.gz':'modules-x710.tar.gz',
             'rollback-accepted331-boot.img':'rollback-boot.img'}
    for name in STAGED:
        source=ROOT/PACKAGE['artifacts'][mapping[name]]['path'] if name in mapping else R/name
        shutil.copyfile(source,folder/name)
    base.verify_stage(folder)
    return dict(verdict='STAGED_ONLY',device_mutation=False)


def admit():
    import asyncio
    from charging_wifi_discovery import Settings, Identity, discover
    verify_inputs(require_push=True)
    if not authorized():raise ValueError('execution scope not authorized')
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-installed-awaiting-owner-C1-System-boot' or (R/'first-failure.json').exists():
        raise ValueError('not pending one owner System boot / first STOP')
    pre=read(preflight_folder()/'summary.json');rec=p.Recorder(R/'candidate-admission')
    settings=Settings(pre['transport']['wifi'],Path(PLAN['key']),Path(PLAN['known_hosts']),PLAN['alias'])
    expected=Identity(PLAN['machine_id'],PLAN['candidate_config_sha256'],PLAN['candidate_notes_sha256'])
    with (rec.folder/'discovery.jsonl').open('x') as f:
        def emit(kind,**data):f.write(json.dumps(dict(kind=kind,**data))+'\n');f.flush()
        endpoint=asyncio.run(discover(settings,expected,emit))
    if not endpoint:raise TimeoutError('bounded enrolled candidate WiFi unavailable')
    # discover() returns the authenticated identity as flat fields.
    boot=endpoint['boot_id'];address=endpoint['address']
    if boot==pre['boot_id']:raise ValueError('boot did not change')
    boots,_=wifi_command(rec,'boots-after',address,'journalctl --list-boots --no-pager')
    if h.g.evidence.attribute(pre['boot_id'],boot,(preflight_folder()/'boots-before.txt').read_text(),boots)!='attributed':
        raise ValueError('unexpected/missing boot attribution')
    result=dict(boot_id=boot,boot_attribution='attributed',transport=dict(wifi=address,wifi_authenticated=True))
    write(R/'startup-summary.json',result)
    state.update(candidate_boot_id=boot,phase='candidate-admitted');write(R/'mutation-state.json',state)
    return result


def wifi_command(rec,name,address,command):
    argv=['ssh','-i',PLAN['key'],'-o','BatchMode=yes','-o','ConnectTimeout=3',
          '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+PLAN['known_hosts'],
          '-o','HostKeyAlias='+PLAN['alias'],'root@'+address,command]
    return rec.command(name,argv,timeout=15)


def observe(phase):
    import queue,threading
    from pps_off_evidence import native_proof, validate_native_sample
    from ordinary_charge_window import charging_ready, validate_safety
    verify_inputs(require_push=True)
    if not authorized() or (R/'first-failure.json').exists():raise ValueError('not authorized / first STOP')
    if (R/phase).exists():raise ValueError('one collection only; never overwrite earlier evidence')
    start=read(R/'startup-summary.json');plan=dict(PLAN,boot_id=start['boot_id'])
    if phase=='discharge' and read(R/'charge/summary.json')['verdict']!='PASS':raise ValueError('charge must pass first')
    rec=p.Recorder(R/phase);result=dict(verdict='STOP',phase=phase,pump_ON=False,PPS=True);proc=None
    try:
        # Bundle pure helpers into in-memory modules. No rootfs installation,
        # kernel commands or writable sysfs knobs are needed by the observer.
        bundle='import sys, types\n'
        for name in ('ordinary_charge_window','pps_off_evidence'):
            code=(ROOT/'scripts'/f'{name}.py').read_text()
            bundle+=f'm=types.ModuleType({name!r});sys.modules[{name!r}]=m;exec({code!r},m.__dict__)\n'
        bundle+=(R/'observe.py').read_text()
        argv=['ssh','-i',plan['key'],'-o','BatchMode=yes','-o','ConnectTimeout=3',
              '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+plan['known_hosts'],
              '-o','HostKeyAlias='+plan['alias'],'root@'+start['transport']['wifi'],
              'python3 - '+shlex.quote(json.dumps(plan))+' '+phase]
        write(rec.folder/'command.json',dict(argv=argv,read_only=True))
        with (rec.folder/'observer.jsonl').open('x') as raw,(rec.folder/'stderr.txt').open('x') as err:
            proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
            proc.stdin.write(bundle);proc.stdin.close()
            lines=queue.Queue()
            def feed():
                for line in proc.stdout:lines.put(line)
                lines.put(None)
            threading.Thread(target=feed,daemon=True).start();began=time.monotonic()
            while True:
                if time.monotonic()-began>plan['host_outer_seconds']:raise TimeoutError('outer observation deadline')
                line=lines.get(timeout=12)
                if line is None:break
                raw.write(line);raw.flush()
                entry=json.loads(line)
                if entry['kind'] in ('armed','progress','verdict'):print(json.dumps(entry),flush=True)
            rc=proc.wait(timeout=3)
        result=accepted((rec.folder/'observer.jsonl').read_text(),rc,phase,plan)
        journal=result.pop('journal')
        (rec.folder/'kernel-json.txt').write_text(journal)
        old=(R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
        known={json.loads(x)['MESSAGE'] for x in old.splitlines() if int(json.loads(x).get('PRIORITY',7))<=3}
        rows=[json.loads(x) for x in journal.splitlines()]
        classified=h.g.evidence.inspect_journal(journal,plan['boot_id'],known,require_start=True,accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),accepted_qca_cycles=True,observed_uptime=result['endpoint']['uptime'])
        bounded={n for group in h.g.startup_triplets(rows,True) for n in group['rows']}
        if classified['fault_counts'] or any(x['row'] not in bounded for x in classified['suspects']):raise ValueError('new full-journal fault/suspect')
        write(rec.folder/'journal-classification.json',classified)
    except Exception as exc:
        result.update(verdict='STOP',host_error=repr(exc))
        # Never overwrite the first incident. Restoration is still permitted.
        if not (R/'first-failure.json').exists():write(R/'first-failure.json',result)
    finally:
        if proc is not None and proc.poll() is None:proc.kill();proc.wait(timeout=3)
        write(rec.folder/'summary.json',result)
    return result


def accepted(raw,rc,phase,plan):
    from pps_off_evidence import native_proof, validate_native_sample
    from ordinary_charge_window import validate_safety, charging_ready
    entries=[json.loads(x) for x in raw.splitlines() if x.strip()]
    verdicts=[x for x in entries if x['kind']=='verdict']
    journals=[x for x in entries if x['kind']=='journal-after']
    if rc or len(verdicts)!=1 or verdicts[0].get('verdict')!='PASS' or verdicts[0].get('phase')!=phase or len(journals)!=1:
        raise ValueError('failed/missing/duplicate observer verdict or journal')
    if not any(x['kind']=='journal-before' for x in entries) or not any(x['kind']=='armed' for x in entries):raise ValueError('missing initial evidence')
    units=[x for x in entries if x['kind']=='systemd-failed']
    if len(units)!=1 or units[0]['raw'].strip():raise ValueError('systemd evidence')
    journal=journals[0]['raw'];proof=native_proof([json.loads(x) for x in journal.splitlines() if x.strip()],plan['boot_id'],required=True)
    result=verdicts[0]
    if result.get('native')!=proof or result.get('pump_ON') is not False:raise ValueError('proof verdict mismatch')
    samples=[x for x in entries if x['kind']=='sample']
    previous=None
    for d in samples:
        if phase=='charge':validate_native_sample(d,plan)
        else:validate_safety(d,plan)
        if previous is not None and not 0<d['monotonic']-previous<=plan['sample_gap_max_seconds']:raise ValueError('recorded response gap')
        previous=d['monotonic']
    progress=[x for x in entries if x['kind']=='progress']
    observing=[x for x in progress if x['state']==('OBSERVE' if phase=='charge' else 'DISCHARGE')]
    minimum=plan[phase+'_seconds']
    if not samples or not observing or not observing[-1].get('complete') or result['observation_seconds']<minimum or observing[-1]['observation_seconds']<minimum:
        raise ValueError('short/incomplete observation')
    current=None;started=None;settling=None;last_seconds=None
    for entry in entries:
        if entry['kind']=='sample':current=entry
        elif entry['kind']=='progress':
            if current is None:raise ValueError('progress without sample')
            state=entry['state'];now=current['monotonic']
            if state=='SETTLING':
                if started is not None:raise ValueError('observation timer restarted')
                if settling is None:settling=now
                if now-settling>10:raise ValueError('unbounded charge settling')
            if state in ('OBSERVE','DISCHARGE'):
                if started is None:
                    if settling is not None and now-settling>10:raise ValueError('late charge admission')
                    started=now
                if phase=='charge':
                    if not charging_ready(current) or entry.get('native')!=proof:raise ValueError('observed charge/native lost')
                elif current['tcpm'].get('POWER_SUPPLY_ONLINE')!='0' or current['usb'].get('POWER_SUPPLY_ONLINE')!='0' or current['battery']['POWER_SUPPLY_STATUS']!='Discharging' or int(current['battery']['POWER_SUPPLY_CURRENT_NOW'])>=0:
                    raise ValueError('observed discharge lost')
                last_seconds=now-started
                if abs(entry['observation_seconds']-last_seconds)>0.01:raise ValueError('reported duration differs from samples')
            elif started is not None:raise ValueError('observation reset')
    if last_seconds is None or last_seconds<minimum or abs(result['observation_seconds']-last_seconds)>0.01:
        raise ValueError('actual sample window shorter than verdict')
    endpoint=result['endpoint'];validate_safety(endpoint,plan)
    if phase=='charge' and not charging_ready(endpoint):raise ValueError('endpoint not charging')
    if phase=='discharge' and (endpoint['tcpm'].get('POWER_SUPPLY_ONLINE')!='0' or endpoint['usb'].get('POWER_SUPPLY_ONLINE')!='0' or endpoint['battery']['POWER_SUPPLY_STATUS']!='Discharging' or int(endpoint['battery']['POWER_SUPPLY_CURRENT_NOW'])>=0):raise ValueError('endpoint not discharging')
    return dict(result,journal=journal,sample_count=len(samples))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['verify','stage','preflight','install','admit','charge','discharge','restore']);ap.add_argument('--from-recovery',action='store_true');args=ap.parse_args();configure()
    try:
        if args.action=='verify':verify_inputs();result=dict(verdict='OFFLINE_INPUTS_MATCH',device_mutation=False)
        elif args.action in ('charge','discharge'):result=observe(args.action)
        elif args.action=='restore':result=restore(args.from_recovery)
        else:result=globals()[args.action]()
        print(json.dumps(result,indent=2),flush=True)
    except Exception as exc:
        if args.action in ('install','admit','charge','discharge') and not (R/'first-failure.json').exists():write(R/'first-failure.json',dict(verdict='STOP',phase=args.action,error=repr(exc)))
        raise
