#!/usr/bin/env python3
"""Test328 boot-only opt-in install; guarded short run; default-OFF restoration."""
import argparse,hashlib,importlib.util,json,re,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
old=load('pps328_base',R.parent/'test-327-fedora-default-off/host_flow.py');base=old.base;h=old.h;gate=old.gate
read=base.read;write=base.write
TRUST=Path('/tmp/gts9-test328-known-hosts')

def configure():
    global PLAN,PACKAGE,STAGED
    PLAN=read(R/'registration.json');PACKAGE=read(R/'PACKAGE.json');STAGED=read(R/'staged-files.json')
    base.R=R;base.PLAN=PLAN;base.PACKAGE=PACKAGE;base.STAGED=STAGED
    h.R=R;h.PLAN=PLAN;h.PACKAGE=PACKAGE;h.STAGED=STAGED;h.STAGE='D:/android/gts9-active/gts9-test328';h.TMP='/tmp/gts9-test328'
    p.SERIAL='gts9wifi-0001'

def verify_inputs(push=False):
    for n,hash_ in read(R/'INPUTS.json').items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=hash_:raise ValueError('input drift '+n)
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test328'))
    if push:
        git=lambda *a:subprocess.check_output(['git',*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration not pushed')
        names=list(read(R/'INPUTS.json'))+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*names):raise ValueError('registered input uncommitted')

def identity(raw,on,expected=None,final=False):
    sec=h.g.baseline.sections(raw);s=dict(sec)
    flag=PACKAGE['cmdline_flag'];cmd=s['cmdline'].strip()
    if on:
        if cmd.split().count(flag)!=1 or s['direct-default'].strip() not in ('Y','1'):raise ValueError('boot opt-in identity')
        s['cmdline']=cmd[len(flag)+1:] if cmd.startswith(flag+' ') else cmd.replace(' '+flag,'',1)
        s['direct-default']='N'
    limits=dict(PLAN,flash_soc_max=95,vbat_max_uv=4400000) if final else PLAN
    boot,b=gate.identity(s,limits,'candidate',expected)
    return sec,boot,b

def wifi(rec,sec,boot):
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',sec['network']);key=sec['host-key'].split()
    if len(addresses)!=1 or key[0]!='ssh-ed25519':raise ValueError('WiFi enrollment')
    TRUST.write_text('gts9-test328 '+key[0]+' '+key[1]+'\n');TRUST.chmod(0o600)
    raw,_=ssh(rec,'wifi-auth',addresses[0],'cat /proc/sys/kernel/random/boot_id; cat /etc/machine-id')
    if raw.splitlines()!=[str(__import__('uuid').UUID(boot)),'3c2a1b8f2d624db4b5ffdc836050fcf6']:raise ValueError('WiFi boot identity')
    return addresses[0]

def ssh(rec,name,address,command,timeout=12,required=True):
    return rec.command(name,['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(TRUST),'-o','HostKeyAlias=gts9-test328','root@'+address,command],timeout=timeout,required=required)

def preflight():
    verify_inputs();rec=p.Recorder(R/('preflight' if not (R/'preflight').exists() else 'preflight-'+str(time.time_ns())))
    raw,_=rec.adb('current-state',PLAN['current_command'],timeout=15);sec,boot,b=identity(raw,False)
    address=wifi(rec,sec,boot)
    raw,_=rec.adb('pump-off','python3 -c '+shlex.quote((R.parent/'test-327-fedora-default-off/read-pump.py').read_text()),timeout=8);gate.pump(raw,boot,'candidate')
    raw,_=rec.adb('partitions',base.DEBIAN_PARTS,timeout=20);base.require_debian_partitions(raw,PACKAGE['baseline_partitions'])
    manifest=(R/'candidate-modules.sha256').read_text()
    rec.adb('modules','set -e; cd /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; test "$(find . -type f | wc -l)" = 181; printf %s '+shlex.quote(manifest)+' | sha256sum -c -',timeout=20)
    old.R=R;old.scan(rec,boot,float(sec['uptime'].split()[0]))
    boots,_=rec.adb('boots-before','journalctl --list-boots --no-pager',timeout=20)
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows):raise ValueError('Code43')
    result=dict(verdict='READY',boot_id=boot,battery=b,wifi=address,collected_at_epoch=time.time());result['evidence_folder']=str(rec.folder.relative_to(R));write(rec.folder/'summary.json',result);write(R/'live-preflight.json',result);return result

def startup(rec,on,final=False):
    start=time.monotonic();index=0
    while time.monotonic()-start<90:
        raw,status=rec.adb('readiness-%02d'%index,'systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr',timeout=8,required=False);index+=1
        if status==0 and raw.splitlines().count('active')==3 and '169.254.42.1/' in raw and re.search(r'\bwlp1s0\s+inet\s+',raw):break
        time.sleep(2)
    else:raise TimeoutError('one boot unavailable')
    raw,_=rec.adb('current-state',PLAN['current_command'],timeout=15);sec,boot,b=identity(raw,on,final=final)
    address=wifi(rec,sec,boot)
    raw,_=rec.adb('pump-off','python3 -c '+shlex.quote((R.parent/'test-327-fedora-default-off/read-pump.py').read_text()),timeout=8);gate.pump(raw,boot,'candidate')
    old.R=R;old.scan(rec,boot,float(sec['uptime'].split()[0]))
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows):raise ValueError('Code43')
    return dict(boot_id=boot,battery=b,wifi=address)

def install():
    verify_inputs(True)
    if (R/'mutation-state.json').exists():raise ValueError('one install only')
    pre=read(R/'live-preflight.json') if (R/'live-preflight.json').exists() else read(R/'preflight/summary.json')
    if pre['verdict']!='READY' or not 0<=time.time()-pre['collected_at_epoch']<=600:raise ValueError('fresh preflight')
    rec=p.Recorder(R/'installation');raw,_=rec.adb('live-boundary',PLAN['current_command'],timeout=15);identity(raw,False,pre['boot_id'])
    write(R/'mutation-state.json',dict(rollback_required=True,phase='recovery-requested'))
    try:
        h.enter_recovery(rec);base.transfer(rec)
        raw,_=rec.adb('partitions-before',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['baseline_partitions']);h.verify_modules(rec,'paired-modules','candidate-modules.sha256')
        h.write_boot(rec,'write-opt-in','candidate-boot.img',PACKAGE['baseline_partitions']['boot'],PACKAGE['candidate_partitions']['boot'])
        raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,PACKAGE['candidate_partitions']);h.clear_unmount(rec)
        rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10);p.SERIAL='gts9wifi-0001'
        result=startup(p.Recorder(R/'candidate-admission'),True)
        boot=result['boot_id'];boots,_=p.Recorder(R/'attribution').adb('boots-after','journalctl --list-boots --no-pager',timeout=20)
        if h.g.evidence.attribute(pre['boot_id'],boot,(R/pre.get('evidence_folder','preflight')/'boots-before.txt').read_text(),boots)!='attributed':raise ValueError('boot attribution')
        write(R/'mutation-state.json',dict(rollback_required=True,phase='opt-in-PC-ready-awaiting-armed-collector',candidate=result))
        return result
    except Exception as exc:
        write(R/'first-failure.json',dict(phase='install/startup',error=str(exc),PPS_started=False));restore();raise

def restore(emergency=False):
    verify_inputs(True);state=read(R/'mutation-state.json')
    if not state['rollback_required']:raise ValueError('already restored')
    rec=p.Recorder(R/'rollback')
    if p.SERIAL!='R52X10045LT':h.enter_recovery(rec)
    base.transfer(rec);raw,_=rec.adb('partitions-before',h.PARTS,timeout=20)
    observed=h.partitions(raw)
    if any(observed[n]!=PACKAGE['baseline_partitions'][n] for n in observed if n!='boot') or observed['boot'] not in (PACKAGE['baseline_partitions']['boot'],PACKAGE['candidate_partitions']['boot']):raise ValueError('unknown recovery layout')
    h.verify_modules(rec,'paired-modules','candidate-modules.sha256')
    desired=PACKAGE['emergency323_partitions'] if emergency else PACKAGE['baseline_partitions']
    if emergency:
        rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
        rec.adb('restore-original323-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback323-modules.sha256',timeout=25)
        h.verify_modules(rec,'restored323-modules','rollback323-modules.sha256')
    image='emergency323-boot.img' if emergency else 'rollback-defaultOFF-boot.img'
    if observed['boot']!=desired['boot']:h.write_boot(rec,'restore-defaultOFF',image,observed['boot'],desired['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,desired);h.clear_unmount(rec)
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10);p.SERIAL='gts9wifi-0001'
    if emergency:
        old.configure();result=old.admission(R/'final-emergency323','baseline',None,None)[0]
    else:result=startup(p.Recorder(R/'final-defaultOFF'),False,final=True)
    write(R/'mutation-state.json',dict(rollback_required=False,phase='emergency323-restored' if emergency else 'defaultOFF327-restored',final=result));return result

def arm():
    verify_inputs(True);state=read(R/'mutation-state.json');c=state['candidate'];rec=p.Recorder(R/'arming')
    if state['phase']!='opt-in-PC-ready-awaiting-armed-collector':raise ValueError('one guard only')
    raw,_=rec.adb('entry-boundary',PLAN['current_command'],timeout=15);identity(raw,True,c['boot_id'])
    guard=ROOT/str((R/'guard.py').relative_to(ROOT));data=guard.read_bytes();hash_=hashlib.sha256(data).hexdigest()
    rec.host_adb('push-guard','-s',p.SERIAL,'push',h.STAGE+'/guard.py',h.TMP+'/guard.py',timeout=10)
    command='set -e; test "$(cat /proc/sys/kernel/random/boot_id | tr -d -)" = '+c['boot_id']+'; test "$(sha256sum '+h.TMP+'/guard.py | cut -d " " -f1)" = '+hash_+'; test ! -e '+h.TMP+'/capture; nohup python3 '+h.TMP+'/guard.py --boot '+c['boot_id']+' --out '+h.TMP+'/capture >'+h.TMP+'/guard-console.txt 2>&1 </dev/null &'
    ssh(rec,'start-guard',c['wifi'],command)
    time.sleep(1)
    raw,_=ssh(rec,'armed',c['wifi'],'cat '+h.TMP+'/capture/armed')
    if raw.strip()!=c['boot_id']:raise ValueError('guardian not armed')
    write(R/'mutation-state.json',dict(state,phase='guardian-armed-awaiting-C1',armed_at_epoch=time.time()));return dict(armed=True,wait_limit_seconds=240,wifi=c['wifi'],boot_id=c['boot_id'])

def status():
    state=read(R/'mutation-state.json');c=state['candidate'];rec=p.Recorder(R/('status-'+str(time.time_ns())))
    raw,_=ssh(rec,'status',c['wifi'],'test "$(cat /proc/sys/kernel/random/boot_id | tr -d -)" = '+c['boot_id']+'; if test -e '+h.TMP+'/capture/finished; then cat '+h.TMP+'/capture/summary.json; else echo waiting; fi')
    return dict(state=raw.strip(),boot_id=c['boot_id'])

def collect():
    verify_inputs(True);state=read(R/'mutation-state.json');c=state['candidate'];rec=p.Recorder(R/'pps-observation')
    command='set -e; test "$(cat /proc/sys/kernel/random/boot_id | tr -d -)" = '+c['boot_id']+'; test -e '+h.TMP+'/capture/finished; cat '+h.TMP+'/capture/summary.json'
    raw,_=ssh(rec,'guardian-summary',c['wifi'],command);result=json.loads(raw)
    for name in ['events.jsonl','armed','finished']:
        ssh(rec,name,c['wifi'],'cat '+h.TMP+'/capture/'+name,timeout=20)
    ssh(rec,'guardian-console',c['wifi'],'cat '+h.TMP+'/guard-console.txt')
    raw,_=ssh(rec,'kernel-json',c['wifi'],'journalctl -k -b -o json --no-pager',timeout=20)
    rows=[json.loads(x) for x in raw.splitlines()]
    if not rows or any(x.get('_BOOT_ID')!=c['boot_id'] for x in rows):raise ValueError('missing/mixed kernel journal')
    ssh(rec,'kernel-journal',c['wifi'],'journalctl -k -b --no-pager',timeout=20)
    ssh(rec,'boots-after',c['wifi'],'journalctl --list-boots --no-pager')
    endpoint,_=ssh(rec,'endpoint',c['wifi'],'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/class/power_supply/sm5714-battery/uevent; cat /sys/class/power_supply/sm5714-usb/uevent; cat /sys/class/power_supply/tcpm-source-psy-*/uevent; systemctl --failed --no-legend --plain --no-pager; test ! -e /sys/bus/i2c/devices/0-0063/driver')
    faults=[x['MESSAGE'] for x in rows if __import__('re').search(r'Kernel panic|soft lockup|rcu.*stall|CSD.*(?:stall|non-responsive)|\bOops:|\bBUG:',x.get('MESSAGE',''),__import__('re').I)]
    events=[json.loads(x) for x in (rec.folder/'events.jsonl.txt').read_text().splitlines()]
    cleanup=[x['data'] for x in events if x['kind']=='cleanup']
    result['accepted']=result.get('verdict')=='PPS_30S_OBSERVED' and result.get('cleanup_verified') is True and result.get('active_seconds',0)>=30 and len(cleanup)==1 and not faults
    result['boot_id']=c['boot_id'];result['kernel_faults']=faults
    class CapturedJournal:
        folder=rec.folder
        def adb(self,*args,**kwargs):return raw,0
    try:
        old.R=R;old.scan(CapturedJournal(),c['boot_id'],float(endpoint.splitlines()[1].split()[0]))
    except Exception as exc:
        result['accepted']=False;result['journal_gate_error']=str(exc)
    write(rec.folder/'summary.json',result)
    write(R/'mutation-state.json',dict(state,phase='observed-awaiting-PC-restore',pps=result))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['preflight','install','arm','status','collect','restore']);ap.add_argument('--emergency',action='store_true');a=ap.parse_args();configure();print(json.dumps(restore(a.emergency) if a.action=='restore' else globals()[a.action](),indent=2),flush=True)
