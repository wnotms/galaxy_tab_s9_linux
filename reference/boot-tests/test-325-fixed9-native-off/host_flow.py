#!/usr/bin/env python3
"""Register/install/pause, one Wi-Fi fixed9 capture, unconditional accepted323 restore."""
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
base=load('fixed325_baseline',R.parent/'test-323-pc-source-budget/host_flow.py')
gate=load('fixed325_gate',R/'gate.py');h=base.h
CONTROL_READER=R.parent/'test-323-pc-source-budget/read-controls.py'
TRUST=Path('/tmp/gts9-test325-known-hosts')
read=base.read;write=base.write

def configure():
    global PLAN,PACKAGE,STAGED
    base.R=R;base.configure();PLAN=base.PLAN;PACKAGE=base.PACKAGE;STAGED=base.STAGED
    h.STAGE='D:/android/gts9-active/gts9-test325';h.TMP='/tmp/gts9-test325';h.TRUST=TRUST
    base.verify_inputs=verify_inputs
    base.controls=baseline_controls
    base.PLAN=dict(PLAN,candidate_config_sha256=PLAN['baseline_config_sha256'],candidate_notes_sha256=PLAN['baseline_notes_sha256'])
    base.identity=baseline_identity

_baseline_identity=base.identity

def baseline_identity(raw,phase,expected=None):
    return _baseline_identity(raw,'candidate',expected)

def baseline_controls(rec,name,boot):
    source=CONTROL_READER.read_text()
    raw,_=rec.adb(name,'python3 -c '+shlex.quote(source),timeout=10)
    state,_=rec.adb(name+'-source','cat /sys/class/power_supply/tcpm-source-psy-*/uevent',timeout=8)
    result=base.gate.program_controls(raw,boot,base.gate.source_budget(state))
    write(rec.folder/(name+'.json'),result);return result


def verify_inputs(require_push=False):
    import hashlib
    inputs=read(R/'INPUTS.json')
    for name,expected in inputs.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('input drift: '+name)
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test325'))
    if require_push:
        git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration must be pushed')
        controlled=list(inputs)+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*controlled):raise ValueError('uncommitted registered input')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*controlled],check=True,stdout=subprocess.DEVNULL)

def ssh_command(rec,name,command,timeout=15,required=True,address=None):
    pre=read(R/'preflight/summary.json');wifi=address or pre['wifi']
    if not re.fullmatch(r'(?:\d{1,3}\.){3}\d{1,3}',wifi):raise ValueError('invalid registered Wi-Fi address')
    return rec.command(name,['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes',
        '-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(TRUST),
        '-o','HostKeyAlias=gts9-test325','root@'+wifi,command],timeout=timeout,required=required)

def preflight():
    result=base.preflight()
    rec=p.Recorder(R/'preflight');raw=(rec.folder/'current-state.txt').read_text().replace('\r','')
    sec=h.g.baseline.sections(raw)
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',sec['network'])
    if len(addresses)!=1:raise ValueError('unique Wi-Fi address')
    key=sec['host-key'].strip().split()
    if len(key)<2 or key[0]!='ssh-ed25519' or not re.fullmatch('[A-Za-z0-9+/=]+',key[1]):raise ValueError('ADB authenticated SSH public key')
    TRUST.write_text('gts9-test325 '+key[0]+' '+key[1]+'\ngts9-test292 '+key[0]+' '+key[1]+'\n')
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
    # Reconnected-PC health is distinct from retained source-powered ADC scope.
    original=base.PLAN
    try:
        base.PLAN=dict(original,candidate_config_sha256=PLAN['candidate_config_sha256'],candidate_notes_sha256=PLAN['candidate_notes_sha256'])
        sec,boot,battery,snapshot=_baseline_identity(raw,'candidate',expected)
    finally:
        base.PLAN=original
    pack=sec['pack-thermal'].splitlines()
    if len(pack)!=3 or pack[:2]!=['sm5714-battery','enabled'] or not 20000<=int(pack[2])<38000 or abs(int(pack[2])-int(gate.values(sec['battery'])['POWER_SUPPLY_TEMP'])*100)>500:raise ValueError('real pack thermal')
    return sec,boot

def capture():
    verify_inputs(require_push=True)
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-installed-awaiting-owner-fixed9-boot' or (R/'candidate-admission').exists():raise ValueError('one retained capture only; no retry/reboot')
    rec=p.Recorder(R/'candidate-admission');p.SERIAL='gts9wifi-0001';observed=None
    try:
        # Capture raw evidence before parsing/refusal. No ADC trigger/replay.
        raw,_=rec.adb('current-state',PLAN['candidate_command'],timeout=15)
        kernel,_=rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
        boots,_=rec.adb('boots-after','journalctl --list-boots --no-pager',timeout=20)
        sections=h.g.baseline.sections(raw);observed=sections.get('boot','').strip().replace('-','')
        state['candidate_boot_id']=observed;write(R/'mutation-state.json',state)
        sec,boot=candidate_identity(raw);pre=read(R/'preflight/summary.json')
        if h.g.evidence.attribute(pre['boot_id'],boot,(R/'preflight/boots-before.txt').read_text(),boots)!='attributed':raise ValueError('extra/unexplained/missing boot')
        verdict=gate.retained_observation(sec['oneshot'],sec['snapshot'],kernel,boot,PLAN['owner_source_hold_seconds'])
        write(rec.folder/'journal-classification.json',base.old.scan_journal(kernel,boot,float(sec['uptime'].split()[0]),gate.values(sec['snapshot'])))
        windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
        if p.has_code43(windows):raise ValueError('Windows Code43 after source->PC return')
        base.wifi_rescue(rec,sec,boot)
        ncm=base.old.ncm_probe(rec,boot)
        verdict.update(boot_id=boot,device_NCM=True,host_NCM_probe_status=ncm[1],late_PC_capture=True)
        write(rec.folder/'summary.json',verdict)
        state.update(phase='capture-complete-PC-unconditional-restore',candidate_boot_id=boot);write(R/'mutation-state.json',state)
        return verdict
    except Exception as exc:
        write(R/'first-failure.json',dict(error=str(exc),stopped=True,phase='retained-candidate-capture',observed_boot_id=observed,charging_authorized=False))
        state.update(phase='first-failure-PC-unconditional-restore',observed_boot_id=observed);write(R/'mutation-state.json',state)
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
    root='/mnt/debian/usr/lib/modules';saved,_=rec.adb('module-layout',f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; if test -d {root}/.gts9-test325-original; then echo saved; else echo no-saved; fi',timeout=10)
    if saved.strip()=='saved':rec.adb('restore-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256',timeout=25)
    elif saved.strip()!='no-saved' or current!=PACKAGE['baseline_partitions']['boot']:raise ValueError('paired original modules missing')
    h.verify_modules(rec,'restored-modules','rollback-modules.sha256')
    if current!=PACKAGE['baseline_partitions']['boot']:h.write_boot(rec,'restore-boot','rollback-accepted323-boot.img',current,PACKAGE['baseline_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['baseline_partitions']);h.clear_unmount(rec)
    write(rec.folder/'summary.json',dict(verdict='ACCEPTED323_ALLFIVE_181_RESTORED'))
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    final=base.admission(R/('manual-final-acceptance' if from_recovery else 'final-acceptance'),'baseline',target,boots)[0]
    write(R/'mutation-state.json',dict(rollback_required=False,phase='accepted323-restored',final=final));return final

def capture_and_restore():
    # PC is already connected. Cleanup cannot wait for a report/commit/push.
    try:
        result=capture()
    finally:
        state=read(R/'mutation-state.json')
        if state.get('rollback_required'):
            restore()
    return dict(capture=result,restoration=read(R/'mutation-state.json'))


def wifi_address(address):
    import ipaddress
    ipaddress.IPv4Address(address)
    state=read(R/'mutation-state.json')
    if state['phase']!='candidate-installed-awaiting-owner-fixed9-boot':raise ValueError('address update outside pending single boot')
    path=R/'preflight/summary.json';pre=read(path)
    rec=p.Recorder(R/'wifi-address');raw,_=ssh_command(rec,'identity','cat /etc/machine-id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes',timeout=8,address=address)
    rows=raw.splitlines()
    if len(rows)!=3 or rows[0]!='3c2a1b8f2d624db4b5ffdc836050fcf6' or [s.split()[0] for s in rows[1:]]!=[PLAN['candidate_config_sha256'],PLAN['candidate_notes_sha256']]:raise ValueError('address candidate authentication failed')
    # Keep readers on the enrolled address until authentication and publication
    # both succeed. A failed probe must never redirect an in-flight collector.
    import os,tempfile
    pre['wifi']=address
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(json.dumps(pre,indent=2,sort_keys=True)+'\n')
        os.replace(temporary,path)
    finally:
        if temporary and temporary.exists():temporary.unlink()
    return dict(authenticated_address=address)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['preflight','install','capture','restore','wifi-address']);ap.add_argument('--from-recovery',action='store_true');ap.add_argument('--address');args=ap.parse_args();configure()
    if args.action=='wifi-address' and not args.address:ap.error('--address required')
    if args.from_recovery and args.action!='restore':ap.error('--from-recovery only for restore')
    result=wifi_address(args.address) if args.action=='wifi-address' else restore(args.from_recovery) if args.action=='restore' else capture_and_restore() if args.action=='capture' else globals()[args.action]();print(json.dumps(result,indent=2),flush=True)
