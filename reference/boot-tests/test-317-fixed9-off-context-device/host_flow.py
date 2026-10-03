#!/usr/bin/env python3
"""Register/install/pause, one Wi-Fi fixed9 capture, unconditional accepted311 restore."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=load('fixed317_baseline',R.parent/'test-313-adc-condition-comparison/host_flow.py')
gate=load('fixed317_gate',R/'gate.py');h=base.h
CONTROL_READER=R.parent/'test-313-adc-condition-comparison/read-controls.py'
TRUST=Path('/tmp/gts9-test317-known-hosts')
read=base.read;write=base.write

def configure():
    global PLAN,PACKAGE,STAGED
    base.R=R;base.configure();PLAN=base.PLAN;PACKAGE=base.PACKAGE;STAGED=base.STAGED
    h.STAGE='D:/android/gts9-active/gts9-test317';h.TMP='/tmp/gts9-test317';h.TRUST=TRUST
    base.verify_inputs=verify_inputs
    base.controls=baseline_controls

def baseline_controls(rec,name,boot):
    source=CONTROL_READER.read_text()
    raw,_=rec.adb(name,'python3 -c '+shlex.quote(source),timeout=10)
    result=base.ordinary.program_controls(raw,boot)
    write(rec.folder/(name+'.json'),result)
    return result

def verify_inputs(require_push=False):
    import hashlib
    inputs=read(R/'INPUTS.json')
    for name,expected in inputs.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('input drift: '+name)
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test317'))
    if require_push:
        git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration must be pushed')
        controlled=list(inputs)+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*controlled):raise ValueError('uncommitted registered input')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*controlled],check=True,stdout=subprocess.DEVNULL)

def ssh_command(rec,name,command,timeout=15,required=True):
    pre=read(R/'preflight/summary.json');wifi=pre['wifi']
    if not re.fullmatch(r'(?:\d{1,3}\.){3}\d{1,3}',wifi):raise ValueError('invalid registered Wi-Fi address')
    return rec.command(name,['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes',
        '-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(TRUST),
        '-o','HostKeyAlias=gts9-test317','root@'+wifi,command],timeout=timeout,required=required)

def preflight():
    result=base.preflight()
    rec=p.Recorder(R/'preflight');raw=(rec.folder/'current-state.txt').read_text().replace('\r','')
    sec=h.g.baseline.sections(raw)
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',sec['network'])
    if len(addresses)!=1:raise ValueError('unique Wi-Fi address')
    key=sec['host-key'].strip().split()
    if len(key)<2 or key[0]!='ssh-ed25519' or not re.fullmatch('[A-Za-z0-9+/=]+',key[1]):raise ValueError('ADB authenticated SSH public key')
    TRUST.write_text('gts9-test317 '+key[0]+' '+key[1]+'\ngts9-test292 '+key[0]+' '+key[1]+'\n')
    TRUST.chmod(0o600);result.update(wifi=addresses[0],wifi_host_key_sha256=__import__('hashlib').sha256((key[0]+' '+key[1]).encode()).hexdigest(),verdict='PENDING_WIFI_AUTHENTICATION')
    write(rec.folder/'summary.json',result)
    raw,_=ssh_command(rec,'wifi-identity','cat /proc/sys/kernel/random/boot_id; cat /etc/machine-id; uname -a',timeout=8)
    if raw.splitlines()[:2]!=[str(__import__('uuid').UUID(result['boot_id'])),'3c2a1b8f2d624db4b5ffdc836050fcf6']:raise ValueError('Wi-Fi boot/machine identity')
    result.update(verdict='READY_FOR_REGISTERED_ONE_BOOT',authenticated_wifi=True)
    write(rec.folder/'summary.json',result);return result

def install():
    verify_inputs(require_push=True)
    if (R/'mutation-state.json').exists():raise ValueError('one install only; inspect mutation state')
    pre=read(R/'preflight/summary.json')
    if pre['verdict']!='READY_FOR_REGISTERED_ONE_BOOT' or not pre['authenticated_wifi'] or not 0<=time.time()-pre['collected_at_epoch']<=PLAN['preflight_max_age_seconds']:raise ValueError('fresh authenticated preflight required')
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
        state=dict(rollback_required=True,phase='candidate-installed-awaiting-owner-fixed9-boot',allfive_verified=True,modules=181)
        write(R/'mutation-state.json',state);write(rec.folder/'summary.json',state)
        # Deliberately no reboot here: owner changes PC -> charger IN TWRP first.
        return state
    except Exception as exc:
        write(R/'first-failure.json',dict(error=str(exc),phase='installation',stopped=True))
        if p.SERIAL=='R52X10045LT':restore(from_recovery=True)
        else:write(R/'recovery-required.json',dict(error=str(exc),manual_TWRP_required=True,no_blind_retry=True))
        raise

def candidate_identity(raw,expected=None):
    sec=h.g.baseline.sections(raw);boot=sec['boot'].strip().replace('-','')
    if not re.fullmatch('[0-9a-f]{32}',boot) or (expected and boot!=expected):raise ValueError('candidate boot identity')
    if sec['boot-end'].strip().replace('-','')!=boot:raise ValueError('packet mixed boot')
    if sec['cmdline'].strip()!=PLAN['runtime_cmdline'] or '7.2.0-rc3-gts9wifi-dirty' not in sec['uname']:raise ValueError('normal cmdline/release')
    if [x.split()[0] for x in sec['identity'].splitlines()]!=[PLAN['candidate_config_sha256'],PLAN['candidate_notes_sha256']]:raise ValueError('candidate config/notes')
    gate.battery_entry(sec['battery']);battery=gate.values(sec['battery'])
    if battery['POWER_SUPPLY_VOLTAGE_MAX_DESIGN']!='4440000':raise ValueError('ordinary float design')
    if sec['services'].splitlines()!=['active']*3 or sec['roles'].splitlines()!=['[sink]','[device]'] or sec['dcc'].strip()!='absent' or sec['failed'].strip():raise ValueError('device services/roles/DCC/failed')
    if 'usb0    inet 169.254.42.1/' not in sec['network']:raise ValueError('device NCM configured')
    pack=sec['pack-thermal'].splitlines()
    if len(pack)!=3 or pack[:2]!=['sm5714-battery','enabled'] or not 20000<=int(pack[2])<38000 or abs(int(pack[2])-int(battery['POWER_SUPPLY_TEMP'])*100)>500:raise ValueError('real pack thermal')
    port=gate.values(sec['source']);tcpm=gate.values(sec['tcpm'])
    if tcpm.get('POWER_SUPPLY_ONLINE')!='1' or tcpm.get('POWER_SUPPLY_VOLTAGE_NOW')!='9000000' or not 1000000<=int(tcpm['POWER_SUPPLY_CURRENT_NOW'])<=1500000:raise ValueError('actual mode/logical fixed contract')
    return sec,boot

def capture():
    verify_inputs(require_push=True)
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-installed-awaiting-owner-fixed9-boot' or (R/'candidate-admission').exists():raise ValueError('one capture only after installed owner boot')
    rec=p.Recorder(R/'candidate-admission');started=time.monotonic();index=0;observed=None
    try:
        while time.monotonic()-started<PLAN['readiness_max_seconds']:
            raw,status=ssh_command(rec,f'readiness-{index:02}',PLAN['candidate_command'],timeout=12,required=False);index+=1
            if status==0:
                sec=h.g.baseline.sections(raw)
                if 'battery' in sec:gate.battery_entry(sec['battery'])
                if sec.get('identity') and [x.split()[0] for x in sec['identity'].splitlines()]!=[PLAN['candidate_config_sha256'],PLAN['candidate_notes_sha256']]:raise ValueError('wrong running candidate')
                snap=gate.values(sec.get('snapshot',''))
                if int(snap.get('context_completed_ms','0'))>0:break
            time.sleep(2)
        else:raise TimeoutError('candidate Wi-Fi/readiness unavailable; no repeat boot')
        sec,boot=candidate_identity(raw);observed=boot
        kernel,_=ssh_command(rec,'kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
        boots,_=ssh_command(rec,'boots-after','journalctl --list-boots --no-pager',timeout=20)
        pre=read(R/'preflight/summary.json')
        if h.g.evidence.attribute(pre['boot_id'],boot,(R/'preflight/boots-before.txt').read_text(),boots)!='attributed':raise ValueError('extra/unexplained/missing boot')
        write(rec.folder/'journal-classification.json',base.old.scan_journal(kernel,boot,float(sec['uptime'].split()[0]),gate.values(sec['snapshot'])))
        verdict=gate.context(sec['snapshot'],kernel,boot,sec['source'])
        controls,_=ssh_command(rec,'handoff-controls','python3 -c '+shlex.quote(CONTROL_READER.read_text()),timeout=10)
        write(rec.folder/'handoff-controls.json',gate.handoff_controls(controls,boot));write(rec.folder/'summary.json',verdict)
        time.sleep(PLAN['endpoint_seconds']);end=p.Recorder(R/'endpoint')
        raw,_=ssh_command(end,'current-state',PLAN['candidate_command'],timeout=12);sec,_=candidate_identity(raw,boot)
        kernel,_=ssh_command(end,'kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
        write(end.folder/'journal-classification.json',base.old.scan_journal(kernel,boot,float(sec['uptime'].split()[0]),gate.values(sec['snapshot'])))
        verdict=gate.context(sec['snapshot'],kernel,boot,sec['source']);write(end.folder/'summary.json',verdict)
        state.update(phase='capture-complete-awaiting-PC-unconditional-restore',candidate_boot_id=boot);write(R/'mutation-state.json',state);return verdict
    except Exception as exc:
        fail=dict(error=str(exc),stopped=True,phase='candidate',observed_boot_id=observed,charging_authorized=False)
        write(R/'first-failure.json',fail)
        ssh_command(rec,'first-failure-kernel','journalctl -k -b -o json --no-pager',timeout=15,required=False)
        state.update(phase='first-failure-awaiting-PC-unconditional-restore',observed_boot_id=observed);write(R/'mutation-state.json',state);raise

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
    root='/mnt/debian/usr/lib/modules';saved,_=rec.adb('module-layout',f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; if test -d {root}/.gts9-test317-original; then echo saved; else echo no-saved; fi',timeout=10)
    if saved.strip()=='saved':rec.adb('restore-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256',timeout=25)
    elif saved.strip()!='no-saved' or current!=PACKAGE['baseline_partitions']['boot']:raise ValueError('paired original modules missing')
    h.verify_modules(rec,'restored-modules','rollback-modules.sha256')
    if current!=PACKAGE['baseline_partitions']['boot']:h.write_boot(rec,'restore-boot','rollback-accepted311-boot.img',current,PACKAGE['baseline_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['baseline_partitions']);h.clear_unmount(rec)
    write(rec.folder/'summary.json',dict(verdict='ACCEPTED311_ALLFIVE_181_RESTORED'))
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    final=base.admission(R/('manual-final-acceptance' if from_recovery else 'final-acceptance'),'baseline',target,boots)[0]
    write(R/'mutation-state.json',dict(rollback_required=False,phase='accepted311-restored',final=final));return final

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['preflight','install','capture','restore']);ap.add_argument('--from-recovery',action='store_true');args=ap.parse_args();configure()
    if args.from_recovery and args.action!='restore':ap.error('--from-recovery only for restore')
    result=restore(args.from_recovery) if args.action=='restore' else globals()[args.action]();print(json.dumps(result,indent=2),flush=True)
