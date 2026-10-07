#!/usr/bin/env python3
"""Test340 owner-confirmed one-shot activation; unconditional exact331 restoration."""
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
    base.R=R;base.configure();base.PLAN.update(read(R/'runtime-commands.json'));PLAN=base.PLAN;PACKAGE=base.PACKAGE;STAGED=base.STAGED
    h.STAGE='D:/android/gts9-active/gts9-test340';h.TMP='/tmp/gts9-test340'
    base.verify_inputs=verify_inputs;base.identity=identity;base.admission=admission

def identity(raw,phase,expected=None,restoration=False):
    sec=h.g.baseline.sections(raw)
    effective=dict(PLAN)
    if phase=='candidate':
        tokens=sec['cmdline'].split()
        if tokens.count(PLAN['cmdline_flag'])!=1 or sec.get('once','').strip()!='Y':raise ValueError('exclusive one-shot opt-in')
        tokens.remove(PLAN['cmdline_flag']);sec=dict(sec,cmdline=' '.join(tokens))
        effective.update(baseline_config_sha256=PLAN['candidate_config_sha256'],baseline_notes_sha256=PLAN['candidate_notes_sha256'])
    elif sec.get('once','absent').strip() not in ('absent','N','0'):raise ValueError('baseline one-shot restored')
    boot,battery=gate.identity(sec,effective,'baseline',expected,restoration=restoration)
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
    parse_identity(raw,Identity(PLAN['machine_id'],PLAN['baseline_config_sha256'],sec['identity'].splitlines()[1].split()[0],boot))
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
    raw,_=rec.adb('current-state',command,timeout=15);sec,boot,b,unused=identity(raw,phase,restoration=(phase!='candidate'))
    if before and boot==before:raise ValueError('boot did not change')
    pump(rec,boot,phase);transport=rescue(rec,sec,boot)
    raw,_=rec.adb('final-partitions',base.DEBIAN_PARTS,timeout=20);base.require_debian_partitions(raw,PACKAGE[phase+'_partitions'])
    rec.adb('final-modules','set -e; cd /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; test "$(find . -type f | wc -l)" = 181; printf %s '+shlex.quote((R/('candidate-modules.sha256' if phase=='candidate' else 'rollback-modules.sha256')).read_text())+' | sha256sum -c -',timeout=20)
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
    execution=read(R/'EXECUTION_INPUTS.json')
    for name,expected in execution.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('execution helper drift: '+name)
    if require_push:
        git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration must be pushed')
        controlled=list(inputs)+list(execution)+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*controlled):raise ValueError('uncommitted registered input')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*controlled],check=True,stdout=subprocess.DEVNULL)

def install():
    verify_inputs(require_push=True)
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test340'))
    if not authorized():raise ValueError('explicit bounded pump execution scope required')
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
        state=dict(rollback_required=True,phase='candidate-installed-awaiting-PC-boot',allfive_verified=True,modules=181)
        write(R/'mutation-state.json',state);write(rec.folder/'summary.json',state)
        # PC USB first; kernel cannot activate at fixed5V. Guardian precedes C1.
        rec.host_adb('normal-PC-reboot','-s',p.SERIAL,'reboot',timeout=10)
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
    root='/mnt/debian/usr/lib/modules';saved,_=rec.adb('module-layout',f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; if test -d {root}/.gts9-test340-original; then echo saved; else echo no-saved; fi',timeout=10)
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
    # Test340 bounded pump deployment. Registration alone is never that instruction.
    path = R/'execution-scope.json'
    if not path.exists():return False
    d = read(path)
    return (d.get('test') == 'Test340' and d.get('PPS') is True and
            d.get('pump_ON') is True and d.get('pump_window_max_ms') == 30000 and d.get('input_cap_ma') == 1800 and d.get('owner_instruction', '').strip() and
            d.get('registration_sha256') == hashlib.sha256((R/'INPUTS.json').read_bytes()).hexdigest())


def stage():
    """Offline, explicit staging only; does not call ADB or start the candidate."""
    import shutil
    verify_inputs(require_push=True)
    if not authorized():raise ValueError('execution scope not yet authorized')
    folder=Path('/mnt/d/android/gts9-active/gts9-test340')
    folder.mkdir(exist_ok=False)
    mapping={'candidate-boot.img':'boot.img','candidate-modules.tar.gz':'modules-x710.tar.gz',
             'rollback-accepted331-boot.img':'rollback-boot.img'}
    for name in STAGED:
        source=ROOT/PACKAGE['artifacts'][mapping[name]]['path'] if name in mapping else R/name
        shutil.copyfile(source,folder/name)
    base.verify_stage(folder)
    return dict(verdict='STAGED_ONLY',device_mutation=False)


def admit():
    verify_inputs(require_push=True)
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-installed-awaiting-PC-boot' or (R/'first-failure.json').exists():raise ValueError('one PC candidate admission only')
    pre=read(preflight_folder()/'summary.json')
    result,_=admission(R/'candidate-admission','candidate',pre['boot_id'],(preflight_folder()/'boots-before.txt').read_text())
    state.update(candidate_boot_id=result['boot_id'],phase='candidate-admitted')
    write(R/'startup-summary.json',result);write(R/'mutation-state.json',state)
    park()
    return result

def wifi_command(rec,name,address,command):
    argv=['ssh','-i',PLAN['key'],'-o','BatchMode=yes','-o','ConnectTimeout=3',
          '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+PLAN['known_hosts'],
          '-o','HostKeyAlias='+PLAN['alias'],'root@'+address,command]
    return rec.command(name,argv,timeout=15)


def park():
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-admitted' or (R/'first-failure.json').exists():raise ValueError('preparation only before first STOP')
    start=read(R/'startup-summary.json');rec=p.Recorder(R/'preparation-park')
    boot=start['boot_id'];address=start['transport']['wifi']
    # Stop/drain before owner handoff. Full journal before and after rejects
    # any entry or consumed attempt; never rebind a stopped candidate.
    raw,_=wifi_command(rec,'journal-before',address,'journalctl -k -b -o json --no-pager')
    guard=load('park340_guard',R/'guard.py')
    rows=[json.loads(x) for x in raw.splitlines()];guard.native_proof(rows,boot)
    if any('one-shot entry begins:' in x['MESSAGE'] for x in rows):raise ValueError('entry already began')
    command='from pathlib import Path; Path("/sys/bus/i2c/drivers/sm5440-fedora/unbind").write_text("0-0063")'
    wifi_command(rec,'cancel-preparation-worker',address,'python3 -c '+shlex.quote(command))
    code=(R/'guard.py').read_text()+"\nhw=Hardware("+repr(boot)+");s=hw.sample();rows=[json.loads(x) for x in subprocess.check_output(['journalctl','-k','-b','-o','json','--no-pager'],text=True).splitlines()];print(json.dumps(dict(proof=preparation_proof(rows,hw.boot,s,hw.is_bound()),sample=s)));os.close(hw.fd)"
    # Imported guardian must not execute its CLI in this ephemeral check.
    code=code[:code.index("if __name__ == '__main__':")]+code[code.index('\nhw=Hardware('):]
    raw,_=wifi_command(rec,'parked-proof',address,'python3 -c '+shlex.quote(code))
    write(rec.folder/'summary.json',json.loads(raw))
    state['phase']='prepared-OFF-unbound';write(R/'mutation-state.json',state)
    return state


def activate():
    verify_inputs(require_push=True)
    state=read(R/'mutation-state.json')
    if state['phase']!='guardian-armed-awaiting-owner-C1' or (R/'first-failure.json').exists():raise ValueError('activation only once before STOP')
    start=read(R/'startup-summary.json')
    confirmation=read(R/'owner-C1-confirmation.json')
    if confirmation.get('test')!='Test340' or confirmation.get('boot_id')!=start['boot_id'] or not confirmation.get('owner_reply','').strip():raise ValueError('fresh owner C1 confirmation required')
    rec=p.Recorder(R/'owner-confirmed-activation')
    plan=read(R/'guardian-arm/plan.json');folder=state['guardian_folder']+'/evidence'
    marker=dict(boot_id=start['boot_id'],token=plan['activation_token'],owner_confirmed_C1=True)
    code='from pathlib import Path; import json; p=Path('+repr(folder)+'); assert not (p/"finished").exists(); assert (p/"awaiting-owner").read_text()=='+repr(start['boot_id'])+'; assert not (p/"activation-started").exists(); f=(p/"activate.json").open("x"); f.write('+repr(json.dumps(marker))+'); f.close()'
    check='import importlib.util, os, time; spec=importlib.util.spec_from_file_location("activation_guard",'+repr(state['guardian_folder']+'/guard.py')+'); g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g); hw=g.Hardware('+repr(start['boot_id'])+'); marker='+repr(marker)+'\ntry:\n for i in range(5):\n  sample=hw.sample(); rows=[json.loads(x) for x in g.subprocess.check_output(["journalctl","-k","-b","-o","json","--no-pager"],text=True,timeout=8).splitlines()]; g.preparation_proof(rows,hw.boot,sample,hw.is_bound())\n  if sample["tcpm"].get("POWER_SUPPLY_VOLTAGE_NOW")=="9000000":break\n  time.sleep(1)\n g.preparation_proof(rows,hw.boot,sample,hw.is_bound(),marker,marker["token"]); print(json.dumps(sample))\nfinally: os.close(hw.fd)\n'
    code=code[:code.index('f=(p/"activate.json")')]+check+code[code.index('f=(p/"activate.json")'):]
    raw,_=wifi_command(rec,'single-activation-marker',start['transport']['wifi'],'python3 -c '+shlex.quote(code))
    write(rec.folder/'activation-precheck.json',json.loads(raw))
    state['phase']='owner-confirmed-single-activation';write(R/'mutation-state.json',state)
    return state


def arm():
    verify_inputs(require_push=True)
    if not authorized() or (R/'first-failure.json').exists():raise ValueError('not authorized / first STOP')
    state=read(R/'mutation-state.json')
    if state['phase']!='prepared-OFF-unbound':raise ValueError('one guardian only after PC admission')
    start=read(R/'startup-summary.json');rec=p.Recorder(R/'guardian-arm')
    import secrets
    plan=dict(PLAN,boot_id=start['boot_id'],activation_token=secrets.token_hex(16));code=(R/'guard.py').read_text()
    write(rec.folder/'plan.json',plan)
    folder='/tmp/gts9-test340-monitor'
    setup='from pathlib import Path; import json; p=Path('+repr(folder)+'); p.mkdir(exist_ok=False); (p/"guard.py").write_text('+repr(code)+'); (p/"plan.json").write_text('+repr(json.dumps(plan))+')'
    wifi_command(rec,'ephemeral-helper',start['transport']['wifi'],'python3 -c '+shlex.quote(setup))
    cmd='nohup python3 '+folder+'/guard.py --plan '+folder+'/plan.json --out '+folder+'/evidence >'+folder+'/stdout.txt 2>'+folder+'/stderr.txt </dev/null & echo $!'
    pid,_=wifi_command(rec,'start-local-guardian',start['transport']['wifi'],cmd)
    raw,_=wifi_command(rec,'confirm-armed',start['transport']['wifi'],'for i in 1 2 3 4 5; do if test -f '+folder+'/evidence/awaiting-owner; then cat '+folder+'/evidence/awaiting-owner; test ! -f '+folder+'/evidence/finished; exit; fi; sleep 1; done; cat '+folder+'/stderr.txt; exit 1')
    if raw.strip()!=start['boot_id']:raise ValueError('guardian failed to arm')
    state.update(phase='guardian-armed-awaiting-owner-C1',guardian_pid=int(pid.strip()),guardian_folder=folder)
    write(R/'mutation-state.json',state);return state

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['verify','stage','preflight','install','admit','arm','activate','restore']);ap.add_argument('--from-recovery',action='store_true');args=ap.parse_args();configure()
    if args.action=='verify':verify_inputs();result={'verdict':'INPUTS_MATCH'}
    elif args.action=='restore':result=restore(args.from_recovery)
    else:result=globals()[args.action]()
    print(json.dumps(result,indent=2),flush=True)
