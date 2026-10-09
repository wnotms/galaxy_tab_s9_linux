#!/usr/bin/env python3
"""Apply already qualified helper; no new kernel/cable/reboot experiment."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

R=Path(__file__).resolve().parent
ROOT=R.parents[2]
T=ROOT/'reference/boot-tests/test-371-usb-lifecycle-gmu'
spec=importlib.util.spec_from_file_location('qualified_usb371',T/'host_flow.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def verify():
    H.verify(pushed=True)
    for name,sha in json.loads((R/'INPUTS.json').read_text()).items():
        path=ROOT/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('deployment input drift '+name)
    inputs=[*json.loads((R/'INPUTS.json').read_text()),str((R/'INPUTS.json').relative_to(ROOT))]
    if subprocess.check_output(['git','status','--porcelain','--',*inputs],text=True).strip():raise ValueError('uncommitted deployment inputs')
    subprocess.run(['git','ls-files','--error-unmatch',*inputs],check=True,stdout=subprocess.DEVNULL)


def program(tail):return (R/'device.py').read_text()+'\n'+tail+'\n'


def capture(folder,name):
    d=json.loads(H.remote(folder,name,program('print(json.dumps(capture()))')))
    if d['kernel']['status'] or d['lifecycle']['status']:raise ValueError('journal collection failed')
    write(folder/(name+'.json'),d)
    (folder/(name+'-kernel.jsonl')).write_text(d['kernel']['stdout'])
    (folder/(name+'-unit.jsonl')).write_text(d['lifecycle']['stdout'])
    plan,profile=H.load();H.admit(d,profile,plan['boot_id'])
    original=json.loads((T/'restored.json').read_text())['snapshot']
    if d['failed']['stdout']!=original['failed']['stdout']:raise ValueError('new failed unit')
    H.health(H.journal(d['kernel']['stdout'],plan['boot_id']),H.journal(original['kernel']['stdout'],plan['boot_id']),{})
    if not d['partner'] or d['usb_online']!='1' or d['udc']!='a600000.usb':raise ValueError('healthy attached PC required')
    return d


def rollback(folder):
    plan,profile=H.load()
    tail='print(json.dumps(deactivate('+repr(H.payload())+','+repr(profile)+','+repr(plan['boot_id'])+')))'
    result=json.loads(H.remote(folder,'rollback',program(tail),timeout=30));write(R/'rolled-back.json',result)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('apply','rollback'));args=ap.parse_args();verify()
    folder=R/(args.action+'-'+str(time.time_ns()));folder.mkdir()
    if args.action=='rollback':rollback(folder);return
    if (R/'mutation.json').exists() or (R/'first-failure.json').exists():raise ValueError('one deployment; no retry')
    try:
        before=capture(folder,'before')
        plan,profile=H.load();payload=H.payload()
        # Exact absent files/link checked before any rootfs mutation.
        tail='rows='+repr(payload)+'\nprofile='+repr(profile)+'\nboot='+repr(plan['boot_id'])+'\n'
        tail+="assert enabled_link('/') is None\nassert not safe('/',STATE).exists()\nfor name in PATHS:\n assert not safe('/',name).exists()\n assert not safe('/',name+'.usb-lifecycle-pending').exists()\n"
        tail+="g=guard(profile,boot,qualified(rows)['usr/local/libexec/gts9-usb-typec-lifecycle'].decode())\nassert g.state()=='attached'\nprint('originals absent, exact attached identity verified')\n"
        H.remote(folder,'originals',program(tail))
        write(R/'mutation.json',dict(boot_id=plan['boot_id'],intent='three absent qualified files plus one absent enabled symlink; ordinary service start',evidence=str(folder.relative_to(ROOT))))
        H.remote(folder,'install-start',program('rows='+repr(payload)+'\nprofile='+repr(profile)+'\nboot='+repr(plan['boot_id'])+"\nprint(json.dumps(install_permanent('/',rows,boot)))\nactivate(rows,profile,boot)"),timeout=35)
        time.sleep(15)
        after=capture(folder,'after')
        if 'ActiveState=active' not in after['lifecycle_state']['stdout'] or 'Result=success' not in after['lifecycle_state']['stdout']:raise ValueError('permanent service health')
        events=[json.loads(l)['MESSAGE'] for l in after['lifecycle']['stdout'].splitlines()]
        if any(msg.startswith('{') for msg in events):raise ValueError('unexpected UDC write on healthy attached PC')
        proof="verify_files('/',"+repr(payload)+")\nassert enabled_link('/') is not None\nprint(json.dumps({'enabled':command('systemctl','is-enabled',UNIT)}))"
        # capture defines command locally, so use an explicit bounded subprocess here.
        proof=proof.replace("command('systemctl','is-enabled',UNIT)","{'stdout':subprocess.check_output(['systemctl','is-enabled',UNIT],text=True,timeout=5).strip()}")
        enabled=json.loads(H.remote(folder,'installed-identity',program(proof)))
        if enabled['enabled']['stdout']!='enabled':raise ValueError('boot enablement absent')
        H.windows_usb(folder,'windows-after')
        raw=H.command(folder,'ADB',['/mnt/d/android/platform-tools/adb.exe','-s','gts9wifi-0001','shell','cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id'],timeout=12)
        if raw.split()!=[plan['machine_id'],plan['boot_id']]:raise ValueError('ADB identity')
        if '169.254.42.1/' not in after['network']['stdout']:raise ValueError('device NCM address')
        summary=dict(verdict='ENABLED_ACTIVE_CURRENT_BOOT_PASS',boot_id=plan['boot_id'],observation_seconds=round(float(after['uptime'].split()[0])-float(before['uptime'].split()[0]),2),UDC_writes=0,ADB='actual shell matched',NCM='device usb0 169.254.42.1',service='enabled/active',new_kernel_faults=0,failed_units=after['failed']['stdout'],reboot_tested=False,charger_to_PC_tested=False,evidence=str(folder.relative_to(ROOT)))
        write(R/'summary.json',summary);print(json.dumps(summary,indent=2))
    except Exception as exc:
        if not (R/'first-failure.json').exists():write(R/'first-failure.json',dict(error=str(exc),evidence=str(folder.relative_to(ROOT))))
        if (R/'mutation.json').exists():
            try:rollback(folder)
            except Exception as cleanup:write(folder/'recovery-failure.json',dict(error=str(cleanup)))
        raise

if __name__=='__main__':main()
