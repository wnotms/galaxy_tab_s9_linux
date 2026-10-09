#!/usr/bin/env python3
"""Independent, same-boot USB acceptance. No historical runner mutation/import.

preflight is read-only. install requires pushed inputs and one fresh preflight.
Any non-clean result is durable and prevents another start. No automatic retry.
"""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

R = Path(__file__).resolve().parent
ROOT = R.parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from windows_ssh_transport import ssh_argv


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def journal(raw, boot):
    rows = [json.loads(line) for line in raw.splitlines()]
    if not rows:
        raise ValueError('empty kernel journal')
    cursors = set()
    for row in rows:
        if (row.get('_BOOT_ID') != boot.replace('-','') or row.get('_TRANSPORT') != 'kernel' or
                not isinstance(row.get('MESSAGE'), str) or not row.get('__CURSOR') or
                row['__CURSOR'] in cursors or not str(row.get('PRIORITY','')).isdigit() or
                not 0 <= int(row['PRIORITY']) <= 7 or int(row['__MONOTONIC_TIMESTAMP']) < 0):
            raise ValueError('kernel attribution/metadata missing')
        cursors.add(row['__CURSOR'])
    return rows


CPU = r'(?i)(soft lockup|softlockup:.*CPU|rcu.*(?:stall|non-responsive)|CSD.*(?:stall|non-responsive|timeout)|Kernel panic|\bOops:|\bBUG:|Internal error|\bSError\b|blocked for more than|workqueue lockup|hung task|CPU.*non-responsive)'


def health(rows, before, known):
    if any(re.search(CPU, row['MESSAGE']) for row in rows):
        raise ValueError('CPU/panic signature; stop')
    if before is None:
        errors = [row['MESSAGE'] for row in rows if int(row['PRIORITY']) <= 3]
        expected = []
        for text, count in known.items():
            expected.extend([text]*count)
        if sorted(errors) != sorted(expected):
            raise ValueError('unregistered existing kernel error')
        return []
    indexed = {r['__CURSOR']:r for r in rows}
    for old in before:
        if indexed.get(old['__CURSOR']) != old:
            raise ValueError('journal baseline missing or changed')
    original = {r['__CURSOR'] for r in before}
    added = [r for r in rows if r['__CURSOR'] not in original]
    if any(int(row['PRIORITY']) <= 3 for row in added):
        raise ValueError('new kernel error; preserve first boot evidence')
    return added


def admit(d, profile, boot):
    if d['boot_id'] != boot or any(d[k] != v for k,v in profile.items()):
        raise ValueError('same-boot Test331 identity changed')
    b = d['battery']
    # No flash, reboot, charging experiment or current increase: upper SOC is
    # not the old sensor-flash admission gate. Temperature/voltage stay bounded.
    if (d['direct'] not in ('N','0') or d['roles'] != dict(power_role='[sink]',data_role='[device]') or
            b['POWER_SUPPLY_HEALTH'] != 'Good' or b['POWER_SUPPLY_PRESENT'] != '1' or
            not 20 <= int(b['POWER_SUPPLY_CAPACITY']) <= 100 or
            not 100 <= int(b['POWER_SUPPLY_TEMP']) < 420 or
            not 3400000 <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) < 4440000 or
            d['services']['status'] != 0 or d['services']['stdout'].split() != ['active']*4 or
            d['failed']['status'] != 0):
        raise ValueError('ordinary safety/rescue/desktop gate')


def load():
    plan = json.loads((R/'registration.json').read_text())
    profile = json.loads((ROOT/'userspace/adbd/profile-test331.json').read_text())
    return plan, profile


def verify(pushed=False):
    inputs = json.loads((R/'INPUTS.json').read_text())
    for name, expected in inputs.items():
        path = ROOT/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('frozen input drift: '+name)
    if pushed:
        git = lambda *a: subprocess.check_output(['git','-C',str(ROOT),*a], text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):
            raise ValueError('registration must be pushed to origin/test')
        names = [*inputs,str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*names):
            raise ValueError('uncommitted inputs')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*names], check=True, stdout=subprocess.DEVNULL)


def command(folder, name, argv, *, stdin=None, timeout=20):
    start = time.time()
    try:
        r = subprocess.run(argv,input=stdin,capture_output=True,timeout=timeout)
        raw, stderr, status = r.stdout,r.stderr,r.returncode
    except subprocess.TimeoutExpired as exc:
        raw,stderr,status = exc.stdout or b'',exc.stderr or b'',124
    (folder/(name+'.stdout')).write_bytes(raw)
    (folder/(name+'.stderr')).write_bytes(stderr)
    if stdin is not None:
        (folder/(name+'.stdin.py')).write_bytes(stdin)
    write(folder/(name+'.command.json'),dict(argv=argv,status=status,started_epoch=start,seconds=time.time()-start))
    if status:
        raise ValueError(name+' command failure '+str(status))
    return raw.decode('utf-8')


def remote(folder, name, program, *, timeout=25):
    plan,_ = load()
    argv = ssh_argv(plan['key'],plan['known_hosts'],plan['alias'],plan['wifi_ip'],
                    'python3 -',transport='windows-tcp')
    return command(folder,name,argv,stdin=program.encode(),timeout=timeout)


def capture(folder,name):
    source = (R/'device.py').read_text()
    d = json.loads(remote(folder,name,source+'\nprint(json.dumps(capture()))\n'))
    if d['kernel']['status'] or d['lifecycle']['status']:
        raise ValueError('complete journal collection failed')
    (folder/(name+'-kernel.jsonl')).write_text(d['kernel']['stdout'])
    (folder/(name+'-lifecycle.jsonl')).write_text(d['lifecycle']['stdout'])
    write(folder/(name+'.json'),d)
    return d


def baseline():
    return json.loads((R/'active-preflight.json').read_text())


def check_snapshot(d):
    plan,profile=load()
    admit(d,profile,plan['boot_id'])
    initial=baseline()['snapshot']
    if d['failed']['stdout'] != initial['failed']['stdout']:
        raise ValueError('new failed unit')
    rows = journal(d['kernel']['stdout'],plan['boot_id'])
    before=journal(initial['kernel']['stdout'],plan['boot_id'])
    spec=importlib.util.spec_from_file_location('teardown',ROOT/'userspace/adbd/teardown-evidence.py')
    parser=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    classification=parser.classify(rows,before,d['lifecycle']['stdout'],plan['boot_id'],'gts9-test368-lifecycle.service')
    d['teardown_classification']=classification
    exempt={row['cursor'] for row in classification}
    health([row for row in rows if row['__CURSOR'] not in exempt],before,plan['existing_errors'])
    return rows


def payload():
    manifest=json.loads((R/'files.json').read_text())
    rows={}
    for name,meta in manifest.items():
        data=(ROOT/meta['source']).read_bytes()
        rows[name]=dict(mode=meta['mode'],bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),base64=base64.b64encode(data).decode())
    return rows


def first_failure(folder, exc):
    if not (R/'first-failure.json').exists():
        write(R/'first-failure.json',dict(verdict='STOP',error=str(exc),evidence=str(folder.relative_to(ROOT)),time=time.time()))


def windows_usb(folder,name):
    script="""$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$rows = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.Present -and ($_.PNPDeviceID -like 'USB*') } | Select-Object Name,PNPDeviceID,ConfigManagerErrorCode)
ConvertTo-Json -InputObject $rows -Depth 3 -Compress
"""
    raw=command(folder,name,['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                            '-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],timeout=25)
    rows=json.loads(raw)
    if any(row['ConfigManagerErrorCode']==43 for row in rows):
        raise ValueError('present Windows USB Code43; attribution retained, stop')
    return rows


def preflight(folder):
    if (R/'first-failure.json').exists() or (R/'mutation.json').exists() or (R/'active-preflight.json').exists():
        raise ValueError('one attempt only')
    plan,profile=load()
    d=capture(folder,'before')
    admit(d,profile,plan['boot_id'])
    if d['partner'] or d['usb_online']!='0' or d['udc']!='a600000.usb' or d['battery']['POWER_SUPPLY_STATUS']!='Discharging':
        raise ValueError('preflight requires physically unplugged stale original binding')
    health(journal(d['kernel']['stdout'],plan['boot_id']),None,plan['existing_errors'])
    if d['failed']['stdout'].strip():
        raise ValueError('baseline failed unit')
    windows_usb(folder,'windows-before')
    # Check all three destinations and permanent enabled link are absent.
    probe=(R/'device.py').read_text()+"\nrows="+repr(payload())+"\nfor name in PATHS:\n assert not safe('/',name).exists()\n assert not safe('/',name+'.test368-pending').exists()\nassert not Path('/var/lib/gts9-test368').exists()\np=Path('/etc/systemd/system/multi-user.target.wants/gts9-usb-typec-lifecycle.service')\nassert not p.exists() and not p.is_symlink()\nprint('all destinations absent')\n"
    remote(folder,'ownership',probe)
    result=dict(verdict='PREFLIGHT_READY_NOT_STARTED',time=time.time(),snapshot=d,evidence=str(folder.relative_to(ROOT)))
    write(R/'active-preflight.json',result)
    return dict(verdict=result['verdict'],battery=d['battery'])


def install(folder):
    verify(pushed=True)
    if (R/'first-failure.json').exists() or (R/'mutation.json').exists():
        raise ValueError('first failure or previous mutation; no retry')
    b=baseline()
    if time.time()-b['time']>300:
        raise ValueError('preflight older than five minutes')
    d=capture(folder,'install-boundary')
    check_snapshot(d)
    if d['partner'] or d['usb_online']!='0':
        raise ValueError('cable changed before install')
    plan,profile=load()
    # Live identity/layout gate executes again immediately before rootfs writes.
    src=(R/'device.py').read_text()
    helper=(ROOT/'userspace/adbd/typec-lifecycle.py').read_text()
    program=src+'\nrows='+repr(payload())+'\nprofile='+repr(profile)+'\nboot='+repr(plan['boot_id'])
    program+="\nns={'__name__':'passive_helper'}\nexec("+repr(helper)+",ns)\ng=ns['Gadget']('/',profile)\nassert g.boot==boot and g.state()=='detached'\nprint(json.dumps(install('/',rows,boot)))\nactivate(rows,profile,boot)\n"
    write(R/'mutation.json',dict(boot_id=plan['boot_id'],evidence=str(folder.relative_to(ROOT)),intent='three absent files, one transient service; no enable'))
    remote(folder,'install-start',program,timeout=35)
    time.sleep(3)
    d=capture(folder,'initial-detached')
    check_snapshot(d)
    check_edge(d,'detached',1,0)
    write(R/'initial-detached.json',dict(verdict='DETACHED_READY_FOR_PC',boot_id=d['boot_id'],snapshot=d))
    return dict(verdict='DETACHED_READY_FOR_PC',boot_id=d['boot_id'],udc=d['udc'])


def check_edge(d,edge,unbinds,binds):
    if ('ActiveState=active' not in d['lifecycle_state']['stdout'] or
            d['partner']!=(edge=='attached') or d['usb_online']!=('1' if edge=='attached' else '0') or
            d['udc']!=('a600000.usb' if edge=='attached' else '')):
        raise ValueError('cable/service/binding gate')
    events=[]
    for line in d['lifecycle']['stdout'].splitlines():
        row=json.loads(line)
        if row.get('_BOOT_ID')!=d['boot_id'].replace('-',''):
            raise ValueError('unit journal attribution')
        message=row.get('MESSAGE','')
        if message.startswith('{'):
            packet=json.loads(message)
            if packet.get('boot_id')!=d['boot_id']:
                raise ValueError('helper event attribution')
            events.append(packet['event'])
    if events != ['unbind','bind']*(min(unbinds,binds))+(['unbind'] if unbinds>binds else []):
        raise ValueError('unexpected/repeated lifecycle writes: '+repr(events))


def observe(folder,edge):
    if (R/'first-failure.json').exists() or not (R/'initial-detached.json').exists():
        raise ValueError('not armed or already stopped')
    sequence={'attached':(1,1),'detached-again':(2,1),'reattached':(2,2)}
    prior={'attached':'initial-detached.json','detached-again':'attached.json','reattached':'detached-again.json'}
    if not (R/prior[edge]).exists() or (R/(edge+'.json')).exists():
        raise ValueError('one physical edge in registered order')
    d=capture(folder,edge+'-before')
    check_snapshot(d)
    check_edge(d,'detached' if edge=='detached-again' else 'attached',*sequence[edge])
    time.sleep(15 if edge=='detached-again' else 30)
    d=capture(folder,edge+'-after')
    check_snapshot(d)
    check_edge(d,'detached' if edge=='detached-again' else 'attached',*sequence[edge])
    if edge=='detached-again' and (d['battery']['POWER_SUPPLY_STATUS']!='Discharging' or int(d['battery']['POWER_SUPPLY_CURRENT_NOW'])>=0):
        raise ValueError('normal discharge not observed')
    if edge!='detached-again':
        windows_usb(folder,edge+'-windows')
        plan,_=load()
        adb='/mnt/d/android/platform-tools/adb.exe'
        shell=command(folder,edge+'-adb',[adb,'-s','gts9wifi-0001','shell','cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id'],timeout=12)
        if shell.split()!=[plan['machine_id'],plan['boot_id']]:
            raise ValueError('ADB shell identity')
        if not re.search(r'\busb0\s+.*169\.254\.42\.1/',d['network']['stdout']):
            raise ValueError('device NCM address')
    result=dict(verdict='EDGE_PASSED',edge=edge,boot_id=d['boot_id'],evidence=str(folder.relative_to(ROOT)),snapshot=d)
    write(R/(edge+'.json'),result)
    return {k:v for k,v in result.items() if k!='snapshot'}


def restore(folder):
    plan,profile=load()
    program=(R/'device.py').read_text()+'\nprint(json.dumps(deactivate('+repr(payload())+','+repr(profile)+','+repr(plan['boot_id'])+')))\n'
    result=json.loads(remote(folder,'stop-restore',program,timeout=30))
    d=capture(folder,'restored')
    admit(d,profile,plan['boot_id'])
    write(R/'restored.json',dict(transaction=result,snapshot=d,evidence=str(folder.relative_to(ROOT))))
    return dict(verdict='THREE_FILES_RESTORED',boot_id=d['boot_id'],udc=d['udc'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['verify','preflight','install','attached','detached-again','reattached','restore'])
    args=ap.parse_args()
    verify()
    if args.action=='verify':
        print(json.dumps(dict(verdict='FROZEN_INPUTS_VERIFIED_HOST_ONLY')))
        return
    folder=R/(args.action+'-'+str(time.time_ns()))
    folder.mkdir()
    try:
        result=({'preflight':preflight,'install':install,'restore':restore}[args.action](folder)
                if args.action in ('preflight','install','restore') else observe(folder,args.action))
    except Exception as exc:
        first_failure(folder,exc)
        # First durable evidence precedes any cleanup. No automatic start retry.
        if args.action!='restore' and (R/'mutation.json').exists():
            try:
                restore(folder)
            except Exception as cleanup:
                write(folder/'recovery-failure.json',dict(error=str(cleanup)))
        raise
    write(folder/'result.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
