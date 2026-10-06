#!/usr/bin/env python3
"""Test332 Fedora default-OFF install/short acceptance; stop and exact323 restore."""
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
    h.STAGE='D:/android/gts9-active/gts9-test332';h.TMP='/tmp/gts9-test332'
    base.verify_inputs=verify_inputs;base.identity=identity;base.admission=admission

def identity(raw,phase,expected=None):
    sec=h.g.baseline.sections(raw);boot,battery=gate.identity(sec,PLAN,phase,expected)
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
    # Default-OFF PC stage retains USB. Never use this fallback for PPS/charger.
    try:
        wifi=base.wifi_rescue(rec,sec,boot)
        result=dict(wifi=wifi,wifi_authenticated=True,rescue='WiFi')
    except p.CaptureError as error:
        h.ssh(rec,'ncm-rescue','169.254.42.1',boot)
        result=dict(wifi_authenticated=False,wifi_host_error=str(error),rescue='authenticated USB NCM',wireless_PPS_allowed=False)
    write(rec.folder/'transport.json',result)
    return result

def preflight():
    verify_inputs();rec=p.Recorder(R/'preflight')
    raw,_=rec.adb('current-state',PLAN['current_command'],timeout=15);sec,boot,b,unused=identity(raw,'baseline')
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
    write(rec.folder/'summary.json',result);return result

def admission(folder,phase,before,boots_before):
    rec=p.Recorder(folder);p.SERIAL='gts9wifi-0001';start=time.monotonic();index=0
    while time.monotonic()-start<PLAN['readiness_max_seconds']:
        raw,status=rec.adb('readiness-%02d'%index,'cat /proc/sys/kernel/random/boot_id; systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr',timeout=8,required=False);index+=1
        if status==0 and raw.splitlines().count('active')==3 and '169.254.42.1/' in raw and re.search(r'\bwlp1s0\s+inet\s+',raw):break
        time.sleep(2)
    else:raise TimeoutError('candidate rescue unavailable')
    command=PLAN['candidate_command'] if phase=='candidate' else PLAN['current_command']
    raw,_=rec.adb('current-state',command,timeout=15);sec,boot,b,unused=identity(raw,phase)
    if before and boot==before:raise ValueError('boot did not change')
    pump(rec,boot,phase);transport=rescue(rec,sec,boot)
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
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test332'))
    if require_push:
        git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration must be pushed')
        controlled=list(inputs)+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*controlled):raise ValueError('uncommitted registered input')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*controlled],check=True,stdout=subprocess.DEVNULL)

def install():
    verify_inputs(require_push=True)
    if (R/'mutation-state.json').exists():raise ValueError('one install only; inspect mutation state')
    pre=read(R/'preflight/summary.json')
    if pre['verdict']!='READY_FOR_REGISTERED_ONE_BOOT' or not pre['rescue_authenticated'] or not 0<=time.time()-pre['collected_at_epoch']<=PLAN['preflight_max_age_seconds']:raise ValueError('fresh authenticated preflight required')
    rec=p.Recorder(R/'installation');p.SERIAL='gts9wifi-0001'
    raw,_=rec.adb('live-boundary',PLAN['current_command'],timeout=15);base.identity(raw,'baseline',pre['boot_id'])
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
        state=dict(rollback_required=True,phase='candidate-installed-defaultOFF',allfive_verified=True,modules=181)
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
    root='/mnt/debian/usr/lib/modules';saved,_=rec.adb('module-layout',f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; if test -d {root}/.gts9-test332-original; then echo saved; else echo no-saved; fi',timeout=10)
    if saved.strip()=='saved':rec.adb('restore-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256',timeout=25)
    elif saved.strip()!='no-saved' or current!=PACKAGE['baseline_partitions']['boot']:raise ValueError('paired original modules missing')
    h.verify_modules(rec,'restored-modules','rollback-modules.sha256')
    if current!=PACKAGE['baseline_partitions']['boot']:h.write_boot(rec,'restore-boot','rollback-accepted331-boot.img',current,PACKAGE['baseline_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['baseline_partitions']);h.clear_unmount(rec)
    write(rec.folder/'summary.json',dict(verdict='ACCEPTED331_ALLFIVE_181_RESTORED'))
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    final=base.admission(R/('manual-final-acceptance' if from_recovery else 'final-acceptance'),'baseline',target,boots)[0]
    write(R/'mutation-state.json',dict(rollback_required=False,phase='accepted331-restored',final=final));return final


def run():
    try:
        install();rec=p.Recorder(R/'startup');rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
        pre=read(R/'preflight/summary.json');result,boots=admission(R/'candidate-admission','candidate',pre['boot_id'],(R/'preflight/boots-before.txt').read_text())
        if not result['transport']['wifi_authenticated']:raise ValueError('wireless rescue required for charger stage')
        result.update(verdict='OFF_ONLY_FIXED_CHECK_WAITING_FOR_9V')
        write(R/'mutation-state.json',dict(rollback_required=True,phase='OFF-only-candidate-started',candidate_boot_id=result['boot_id']))
        write(R/'startup-summary.json',result);return result
    except Exception as exc:
        write(R/'first-failure.json',dict(error=str(exc),stopped=True,PPS=False,pump_ON=False))
        if (R/'mutation-state.json').exists() and read(R/'mutation-state.json')['rollback_required']:
            try:restore(from_recovery=p.SERIAL=='R52X10045LT')
            except Exception as cleanup:write(R/'recovery-required.json',dict(error=str(cleanup),manual_TWRP_required=True));raise
        raise


def collect():
    verify_inputs(require_push=True)
    state=read(R/'startup-summary.json');boot=state['boot_id']
    address=state['transport']['wifi']
    rec=p.Recorder(R/('fixed-observation' if not (R/'fixed-observation').exists() else 'fixed-observation-trust-corrected'))
    source=(R/'observe.py').read_text()
    trust='/tmp/gts9-test323-known-hosts'  # base.wifi_rescue enrolls this exact file
    command='python3 -u -c '+shlex.quote(source)+' '+shlex.quote(boot)+' '+PLAN['candidate_config_sha256']+' '+PLAN['candidate_notes_sha256']
    argv=['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+trust,'-o','HostKeyAlias=gts9-test292','root@'+address,command]
    start=time.monotonic()
    with (rec.folder/'observer.jsonl').open('w') as out,(rec.folder/'stderr.txt').open('w') as err:
        try:process=subprocess.run(argv,stdout=out,stderr=err,timeout=290)
        except subprocess.TimeoutExpired:
            write(R/'first-failure.json',dict(error='bounded WiFi observer timeout',stopped=True,PPS=False,pump_ON=False));raise
    write(rec.folder/'command.json',dict(argv=argv,returncode=process.returncode,seconds=time.monotonic()-start,read_only_observer=True))
    raw=(rec.folder/'observer.jsonl').read_text()
    records=[json.loads(x) for x in raw.splitlines() if x.strip()]
    for entry in records:
        if entry['kind']=='complete-journal':(rec.folder/'kernel-json.txt').write_text(entry['data'])
    try:
        if process.returncode:raise ValueError('first observer/device refusal')
        result=gate.fixed_result(raw,boot)
        # Full journal gate with existing bounded known-startup classification.
        old=(R.parent/'test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt').read_text()
        known={json.loads(x)['MESSAGE'] for x in old.splitlines() if int(json.loads(x).get('PRIORITY',7))<=3}
        journal=(rec.folder/'kernel-json.txt').read_text()
        rows=[json.loads(x) for x in journal.splitlines()]
        uptime=float(result['endpoint']['uptime'])
        classified=h.g.evidence.inspect_journal(journal,boot,known,require_start=True,accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),accepted_qca_cycles=True,observed_uptime=uptime)
        bounded={n for group in h.g.startup_triplets(rows,True) for n in group['rows']}
        if classified['fault_counts'] or any(x['row'] not in bounded for x in classified['suspects']):raise ValueError('new full-journal fault/suspect')
        write(rec.folder/'journal-classification.json',classified)
        write(rec.folder/'summary.json',result);return result
    except Exception as e:
        write(R/'first-failure.json',dict(error=str(e),stopped=True,PPS=False,pump_ON=False));raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['preflight','run','collect','restore']);ap.add_argument('--from-recovery',action='store_true');args=ap.parse_args();configure()
    print(json.dumps(restore(args.from_recovery) if args.action=='restore' else globals()[args.action](),indent=2),flush=True)
