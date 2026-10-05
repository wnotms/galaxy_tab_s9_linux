#!/usr/bin/env python3
"""One unchanged accepted311 normal baseline reentry; no flash/config writes."""
import argparse
import hashlib
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
spec=importlib.util.spec_from_file_location('reentry319_base',R.parent/'test-313-adc-condition-comparison/host_flow.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
read=b.read;write=b.write;h=b.h
TRUST=Path('/tmp/gts9-test319-known-hosts')

def configure():
    global PLAN,PACKAGE
    PLAN=read(R/'registration.json');PACKAGE=read(R/'PACKAGE.json')
    b.PLAN=dict(PLAN);h.PLAN=PLAN;h.TRUST=TRUST;p.SERIAL='gts9wifi-0001'

def identity(raw,incoming=False,expected=None):
    b.PLAN['runtime_cmdline']=PLAN['incoming_cmdline' if incoming else 'runtime_cmdline']
    try:result=b.identity(raw,'baseline',expected)
    finally:b.PLAN['runtime_cmdline']=PLAN['runtime_cmdline']
    sec,boot,battery,snap=result
    if sec['boot-end'].strip().replace('-','')!=boot:raise ValueError('mixed boot packet')
    pack=sec['pack-thermal'].splitlines()
    if len(pack)!=3 or pack[:2]!=['sm5714-battery','enabled'] or not 20000<=int(pack[2])<38000:raise ValueError('real pack thermal')
    source=b.gate.values(sec['source'])
    if source.get('ret')!='0' or source.get('online')!='1' or source.get('budget_mv')!='5000':raise ValueError('native PC fixed5 source')
    return result

def verify_registration():
    inputs=read(R/'INPUTS.json')
    for name,expected in inputs.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('registered input drift: '+name)
    git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
    names=list(inputs)+[str((R/'INPUTS.json').relative_to(ROOT))]
    if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test') or git('status','--porcelain','--',*names):raise ValueError('registration must be committed/pushed')
    subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*names],check=True,stdout=subprocess.DEVNULL)

def capture(folder,incoming=False,expected=None):
    rec=p.Recorder(folder);raw,_=rec.adb('current-state',PLAN['current_command'],timeout=12)
    sec,boot,battery,snap=identity(raw,incoming,expected)
    kernel,_=rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
    write(folder/'journal-classification.json',b.old.scan_journal(kernel,boot,float(sec['uptime'].split()[0]),snap))
    boots,_=rec.adb('boots','journalctl --list-boots --no-pager',timeout=15)
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows) or not re.search(r'ProblemCode\s*:\s*0\b',windows):raise ValueError('USB Code43 or no confirmed Code0')
    result=dict(boot_id=boot,battery=battery,device_NCM=True,physical_software_writes=False)
    return rec,sec,result,boots

def preflight():
    verify_registration()
    # Pack reserve precedes partition/module/Windows work.
    rec=p.Recorder(R/'reserve');raw,_=rec.adb('battery','cat /sys/class/power_supply/sm5714-battery/uevent',timeout=8)
    pack=b.gate.battery_entry(raw)
    if not PLAN['minimum_flash_soc']<=pack['soc']<PLAN['maximum_flash_soc_exclusive']:raise ValueError('reentry battery reserve')
    rec,sec,result,boots=capture(R/'preflight',incoming=True)
    parts,_=rec.adb('partitions',b.DEBIAN_PARTS,timeout=20);b.require_debian_partitions(parts,PACKAGE['baseline_partitions'])
    manifest=(R/'rollback-modules.sha256').read_text()
    cmd='set -e; test "$(cat /etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; cd /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; test "$(find . -type f | wc -l)" = 181; printf %s '+shlex.quote(manifest)+' | sha256sum -c -'
    rec.adb('modules',cmd,timeout=20)
    key=sec['host-key'].split()
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',sec['network'])
    if len(key)<2 or key[0]!='ssh-ed25519' or not re.fullmatch('[A-Za-z0-9+/=]+',key[1]) or len(addresses)!=1:raise ValueError('fresh ADB SSH key/address')
    TRUST.write_text('gts9-test319 '+key[0]+' '+key[1]+'\ngts9-test292 '+key[0]+' '+key[1]+'\n');TRUST.chmod(0o600)
    argv=['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(TRUST),'-o','HostKeyAlias=gts9-test319','root@'+addresses[0],'cat /proc/sys/kernel/random/boot_id; cat /etc/machine-id']
    wifi,_=rec.command('wifi-identity',argv,timeout=8)
    if wifi.splitlines()!=[str(__import__('uuid').UUID(result['boot_id'])),'3c2a1b8f2d624db4b5ffdc836050fcf6']:raise ValueError('authenticated Wi-Fi identity')
    result.update(collected_at_epoch=time.time(),boots=boots,verdict='READY_ONE_UNCHANGED_NORMAL_REBOOT')
    write(R/'preflight/summary.json',result);return result

def run():
    verify_registration()
    if (R/'reboot-state.json').exists():raise ValueError('one reboot only; no replay')
    pre=read(R/'preflight/summary.json')
    if pre['verdict']!='READY_ONE_UNCHANGED_NORMAL_REBOOT' or not 0<=time.time()-pre['collected_at_epoch']<=PLAN['preflight_max_age_seconds']:raise ValueError('fresh preflight required')
    rec=p.Recorder(R/'reboot');raw,_=rec.adb('live-boundary',PLAN['current_command'],timeout=12)
    _,_,battery,_=identity(raw,True,pre['boot_id'])
    if battery['soc']<PLAN['minimum_flash_soc']:raise ValueError('reserve fell before reboot')
    write(R/'reboot-state.json',dict(reboot_requested=True,software_writes=False,rollback_required=False))
    try:
        rec.adb('ordinary-reboot','systemctl reboot',timeout=8,required=False)
        start=time.monotonic();i=0;ready=p.Recorder(R/'readiness')
        while time.monotonic()-start<PLAN['readiness_max_seconds']:
            raw,status=ready.adb('packet-%02d'%i,PLAN['current_command'],timeout=8,required=False);i+=1
            sec=h.g.baseline.sections(raw)
            if status==0 and sec.get('boot','').strip().replace('-','')!=pre['boot_id']:
                identity(raw);break
            time.sleep(2)
        else:raise TimeoutError('new normal boot not available; no second reboot')
        _,_,result,boots=capture(R/'after')
        if h.g.evidence.attribute(pre['boot_id'],result['boot_id'],pre['boots'],boots)!='attributed':raise ValueError('unexplained/missing boot attribution')
        time.sleep(PLAN['endpoint_seconds']);capture(R/'endpoint',expected=result['boot_id'])
        result.update(verdict='NORMAL_ACCEPTED311_REENTRY_COMPLETED',rollback_required=False,new_candidate_boot=False)
        write(R/'summary.json',result);return result
    except Exception as exc:
        write(R/'first-failure.json',dict(error=str(exc),stopped=True,no_second_reboot=True,software_writes=False))
        p.Recorder(R/'first-failure').adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15,required=False)
        raise

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['preflight','run']);args=ap.parse_args();configure();print(json.dumps(globals()[args.action](),indent=2))
