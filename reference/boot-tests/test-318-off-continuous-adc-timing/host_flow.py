#!/usr/bin/env python3
"""One pushed OFF timing candidate boot/capture, unconditional paired rollback.

Reuse accepted recovery/hash/module/read-only baseline helpers. Import is offline.
"""
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

ROOT=Path(__file__).resolve().parents[3]; R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

base=load('timing318_base',R.parent/'test-313-adc-condition-comparison/host_flow.py')
gate=load('timing318_gate',R/'gate.py'); h=base.h
read=base.read; write=base.write; transfer=base.transfer; restoration_layout=base.restoration_layout
TRUST=Path('/tmp/gts9-test318-known-hosts')


def configure():
    global PLAN, PACKAGE, STAGED
    base.R=R; base.configure(); PLAN=base.PLAN; PACKAGE=base.PACKAGE; STAGED=base.STAGED
    h.STAGE='D:/android/gts9-active/gts9-test318';h.TMP='/tmp/gts9-test318';h.TRUST=TRUST
    base.verify_inputs=verify_inputs; base.controls=controls; base.identity=identity


def verify_inputs(require_push=False):
    inputs=read(R/'INPUTS.json')
    for path, expected in inputs.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected: raise ValueError('input drift: '+path)
    base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test318'))
    if require_push:
        git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'): raise ValueError('push registration first')
        paths=list(inputs)+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*paths): raise ValueError('uncommitted registered input')
        subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch',*paths],check=True,stdout=subprocess.DEVNULL)


baseline_identity=base.identity

def identity(raw,phase,expected=None):
    if phase=='baseline':
        return baseline_identity(raw,phase,expected)
    sec=h.g.baseline.sections(raw);boot=sec['boot'].strip().replace('-','')
    if not re.fullmatch('[0-9a-f]{32}',boot) or (expected and boot!=expected) or sec['boot-end'].strip().replace('-','')!=boot: raise ValueError('candidate mixed/unexpected boot')
    if sec['cmdline'].strip()!=PLAN['runtime_cmdline'] or '7.2.0-rc3-gts9wifi-dirty' not in sec['uname']: raise ValueError('cmdline/release')
    if [line.split()[0] for line in sec['identity'].splitlines()]!=[PLAN['candidate_config_sha256'],PLAN['candidate_notes_sha256']]: raise ValueError('config/notes')
    battery=gate.battery_entry(sec['battery']);usb=gate.values(sec['usb']);snap=gate.values(sec['snapshot'])
    if gate.values(sec['battery']).get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN')!='4440000': raise ValueError('float design')
    if usb.get('POWER_SUPPLY_ONLINE')!='1' or '[SDP]' not in usb.get('POWER_SUPPLY_USB_TYPE','') or not 100000<=int(usb['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])<=500000: raise ValueError('ordinary PC policy')
    if sec['services'].splitlines()!=['active']*3 or sec['roles'].splitlines()!=['[sink]','[device]'] or sec['dcc'].strip()!='absent' or sec['failed'].strip(): raise ValueError('services/role/DCC/failed')
    if 'usb0    inet 169.254.42.1/' not in sec['network']: raise ValueError('device NCM')
    pack=sec['pack-thermal'].splitlines()
    if len(pack)!=3 or pack[:2]!=['sm5714-battery','enabled'] or not 20000<=int(pack[2])<38000 or abs(int(pack[2])-int(gate.values(sec['battery'])['POWER_SUPPLY_TEMP'])*100)>500: raise ValueError('real pack thermal')
    return sec,boot,battery,snap


def controls(rec,name,boot):
    source=(R.parent/'test-313-adc-condition-comparison/read-controls.py').read_text()
    raw,_=rec.adb(name,'python3 -c '+shlex.quote(source),timeout=10)
    result=base.ordinary.program_controls(raw,boot);write(rec.folder/(name+'.json'),result);return result


ncm_probe_original=base.old.ncm_probe

def ncm_probe(rec,boot):
    packet=rec.folder/'current-state.txt'
    if rec.folder.name=='preflight' and packet.exists():
        sec=h.g.baseline.sections(packet.read_text().replace('\r',''))
        key=sec['host-key'].strip().split()
        if len(key)<2 or key[0]!='ssh-ed25519' or not re.fullmatch('[A-Za-z0-9+/=]+',key[1]): raise ValueError('fresh ADB SSH host key')
        TRUST.write_text('gts9-test292 '+key[0]+' '+key[1]+'\n');TRUST.chmod(0o600)
    return ncm_probe_original(rec,boot)

base.old.ncm_probe=ncm_probe


def preflight():
    # An entry refusal is cheap. Do not hash partitions/modules or probe
    # Windows while the actual pack cannot support candidate+rollback boots.
    # This is only an entry filter; full identity/rescue still follows once.
    rec=p.Recorder(R/'reserve-checks'/str(time.time_ns()))
    raw,_=rec.adb('battery-reserve','set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent',timeout=8)
    sec=h.g.baseline.sections(raw)
    if not re.fullmatch('[0-9a-f]{32}',sec['boot'].strip().replace('-','')):raise ValueError('reserve packet boot identity')
    try:
        battery=gate.battery_entry(sec['battery'])
    except (ValueError, KeyError) as exc:
        write(rec.folder/'summary.json',dict(verdict='PACK_ENTRY_NOT_READY',error=str(exc),full_preflight_executed=False,device_mutation=False))
        raise
    if not PLAN['minimum_flash_soc']<=battery['soc']<PLAN['maximum_flash_soc_exclusive']:
        write(rec.folder/'summary.json',dict(verdict='FLASH_RESERVE_NOT_READY',battery=battery,full_preflight_executed=False,device_mutation=False))
        raise ValueError('flash/rescue battery reserve')
    result=base.preflight()
    if not PLAN['minimum_flash_soc']<=result['battery']['soc']<PLAN['maximum_flash_soc_exclusive']: raise ValueError('flash/rescue battery reserve')
    sec=h.g.baseline.sections((R/'preflight/current-state.txt').read_text().replace('\r',''))
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',sec['network'])
    key=sec['host-key'].strip().split()
    if len(addresses)!=1 or len(key)<2 or key[0]!='ssh-ed25519' or not re.fullmatch('[A-Za-z0-9+/=]+',key[1]): raise ValueError('ADB authenticated Wi-Fi/key')
    TRUST.write_text('gts9-test318 '+key[0]+' '+key[1]+'\ngts9-test292 '+key[0]+' '+key[1]+'\n');TRUST.chmod(0o600)
    argv=['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(TRUST),'-o','HostKeyAlias=gts9-test318','root@'+addresses[0],'cat /proc/sys/kernel/random/boot_id; cat /etc/machine-id']
    raw,_=p.Recorder(R/'preflight').command('wifi-identity',argv,timeout=8)
    if raw.splitlines()!=[str(__import__('uuid').UUID(result['boot_id'])),'3c2a1b8f2d624db4b5ffdc836050fcf6']: raise ValueError('Wi-Fi identity')
    result.update(wifi=addresses[0],authenticated_wifi=True);write(R/'preflight/summary.json',result);return result


def admission(folder,phase,before,boots_before):
    if phase=='baseline':return base.admission(folder,phase,before,boots_before)
    rec=p.Recorder(folder);p.SERIAL='gts9wifi-0001';start=time.monotonic();i=0
    while time.monotonic()-start<PLAN['readiness_max_seconds']:
        raw,status=rec.adb('readiness-%02d'%i,PLAN['candidate_command'],timeout=12,required=False);i+=1
        sec=h.g.baseline.sections(raw);s=gate.values(sec.get('snapshot',''))
        if status==0 and (int(s.get('timing_attempted','0')) or int(s.get('fault','0'))):break
        time.sleep(2)
    else:raise TimeoutError('candidate rescue/readiness missing; no repeated boot')
    # Preserve boundary evidence before classification, including first refusal.
    kernel,_=rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
    boots,_=rec.adb('boots-after','journalctl --list-boots --no-pager',timeout=20)
    sec,boot,battery,s=identity(raw,'candidate')
    if h.g.evidence.attribute(before,boot,boots_before,boots)!='attributed':raise ValueError('extra/missing boot')
    scan=base.old.scan_journal(kernel,boot,float(sec['uptime'].split()[0]),s)
    write(folder/'journal-classification.json',scan)
    result=gate.timing(sec['snapshot'],sec['source']);result.update(boot_id=boot,battery=battery)
    base.thermal(rec,'thermal',boot);controls(rec,'program-controls',boot)
    windows,_=rec.ps('windows-usb',p.PS_USB,timeout=20)
    if p.has_code43(windows):raise ValueError('Windows Code43')
    result['host_NCM_probe_status']=base.old.ncm_probe(rec,boot)[1]
    write(folder/'summary.json',result);return result,boots


def restore(from_recovery=False):
    if not (R / 'mutation-state.json').exists():
        raise ValueError('no registered mutation to restore')
    if not read(R/'mutation-state.json').get('rollback_required'): raise ValueError('already restored; no duplicate recovery')
    verify_inputs(require_push=True)
    folder = R / ('manual-rollback-install' if from_recovery else 'rollback-install')
    rec = p.Recorder(folder)
    if not from_recovery:
        p.SERIAL = 'gts9wifi-0001'
        target, _ = rec.adb('target-boot-id', 'cat /proc/sys/kernel/random/boot_id', timeout=8)
        boots, _ = rec.adb('target-boots', 'journalctl --list-boots --no-pager', timeout=20)
        target = target.strip().replace('-', '')
        observed=read(R/'mutation-state.json').get('candidate_boot_id')
        if observed and target!=observed: raise ValueError('unexpected boot before rollback')
        h.enter_recovery(rec)
    else:
        p.SERIAL = 'R52X10045LT'
        # Manual recovery must still identify this board/root. No device write
        # is inferred from an old installation summary or disconnected command.
        ident, _ = rec.adb('manual-twrp-identity', 'getprop ro.product.device; id', timeout=10)
        if 'gts9wifi' not in ident or 'uid=0' not in ident:
            raise ValueError('manual TWRP identity')
        target, boots = None, None
    transfer(rec)
    raw, _ = rec.adb('partitions-before', h.PARTS, timeout=20)
    current = restoration_layout(raw)
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    module_root = '/mnt/debian/usr/lib/modules'
    state, _ = rec.adb('module-layout', f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; '
                      f'if test -d {module_root}/.gts9-test318-original; then echo saved; else echo no-saved; fi', timeout=10)
    if state.strip() == 'saved':
        rec.adb('restore-modules', f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256', timeout=25)
    elif state.strip() != 'no-saved' or current != PACKAGE['baseline_partitions']['boot']:
        raise ValueError('paired rollback modules missing')
    h.verify_modules(rec, 'restored-modules', 'rollback-modules.sha256')
    if current != PACKAGE['baseline_partitions']['boot']:
        h.write_boot(rec, 'restore-boot', 'rollback-accepted311-boot.img', current, PACKAGE['baseline_partitions']['boot'])
    raw, _ = rec.adb('partitions-after', h.PARTS, timeout=20)
    h.require_partitions(raw, PACKAGE['baseline_partitions'])
    h.clear_unmount(rec)
    write(rec.folder / 'summary.json', dict(verdict='ACCEPTED311_ALLFIVE_181_RESTORED'))
    rec.host_adb('normal-reboot', '-s', p.SERIAL, 'reboot', timeout=10)
    # A failed candidate may never have completed journald. Still verify the
    # restored baseline's actual identity/thermal/rescue/journal, while retaining
    # the missing candidate attribution explicitly (never a clean Test318).
    final = admission(R / ('manual-final-acceptance' if from_recovery else 'final-acceptance'),
                      'baseline', target, boots)[0]
    write(R / 'mutation-state.json', dict(rollback_required=False, phase='accepted311-restored', final=final))
    return final

def install_once():
    pre = read(R / 'preflight/summary.json')
    if pre['verdict'] != 'READY_FOR_REGISTERED_ONE_BOOT' or not 0 <= time.time() - pre['collected_at_epoch'] <= PLAN['preflight_max_age_seconds']:
        raise ValueError('fresh successful preflight required')
    rec = p.Recorder(R / 'installation')
    raw, _ = rec.adb('live-boundary', PLAN['current_command'], timeout=15)
    boundary=identity(raw, 'baseline', pre['boot_id'])
    if not PLAN['minimum_flash_soc']<=boundary[2]['soc']<PLAN['maximum_flash_soc_exclusive'] or not pre.get('authenticated_wifi'): raise ValueError('flash reserve/authenticated rescue')
    # From the first possible BCB request onward, cleanup is required even if
    # no kernel/module write has happened. A failed transfer must not strand a
    # healthy baseline in recovery and leave an armed BCB unreported.
    write(R / 'mutation-state.json', dict(rollback_required=True, phase='recovery-requested-no-kernel-write'))
    h.enter_recovery(rec)
    transfer(rec)
    raw, _ = rec.adb('partitions-before', h.PARTS, timeout=20)
    h.require_partitions(raw, PACKAGE['baseline_partitions'])
    h.verify_modules(rec, 'original-modules', 'rollback-modules.sha256')
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    write(R / 'mutation-state.json', dict(rollback_required=True, phase='before-module-swap'))
    rec.adb('install-modules', f'sh {h.TMP}/module-swap.sh /mnt/debian install {h.TMP}/candidate-modules.sha256 {h.TMP}/candidate-modules.tar.gz {h.TMP}/rollback-modules.sha256', timeout=25)
    h.write_boot(rec, 'write-boot', 'candidate-boot.img', PACKAGE['baseline_partitions']['boot'], PACKAGE['candidate_partitions']['boot'])
    raw, _ = rec.adb('partitions-after', h.PARTS, timeout=20)
    h.require_partitions(raw, PACKAGE['candidate_partitions'])
    h.clear_unmount(rec)
    write(R / 'mutation-state.json', dict(rollback_required=True, phase='candidate-reboot-requested'))
    rec.host_adb('normal-reboot', '-s', p.SERIAL, 'reboot', timeout=10)
    result,_=admission(R/'candidate-admission','candidate',pre['boot_id'],(R/'preflight/boots-before.txt').read_text())
    write(R/'mutation-state.json',dict(rollback_required=True,phase='capture-completed',candidate_boot_id=result['boot_id']))
    time.sleep(PLAN['endpoint_seconds'])
    rec=p.Recorder(R/'endpoint');raw,_=rec.adb('current-state',PLAN['candidate_command'],timeout=12)
    sec,boot,_,_=identity(raw,'candidate',result['boot_id'])
    kernel,_=rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
    write(rec.folder/'journal-classification.json',base.old.scan_journal(kernel,boot,float(sec['uptime'].split()[0]),gate.values(sec['snapshot'])))
    write(rec.folder/'summary.json',gate.timing(sec['snapshot'],sec['source']))
    return result


def run():
    verify_inputs(require_push=True)
    if (R/'mutation-state.json').exists():raise ValueError('one install only; inspect persisted state')
    failure=None;result=None
    try:result=install_once()
    except Exception as exc:
        failure=str(exc);write(R/'first-failure.json',dict(error=failure,stopped=True,charging_authorized=False))
        if p.SERIAL=='gts9wifi-0001':p.Recorder(R/'first-failure').adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15,required=False)
    finally:
        if (R/'mutation-state.json').exists():
            try:restore(from_recovery=p.SERIAL=='R52X10045LT')
            except Exception as exc:
                write(R/'recovery-required.json',dict(error=str(exc),manual_TWRP_required=True,no_blind_retry=True))
                raise RuntimeError('restore incomplete, manual TWRP required: '+str(exc)) from exc
    if failure:raise RuntimeError('first non-clean stopped/restored: '+failure)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['preflight','run','restore']);ap.add_argument('--from-recovery',action='store_true');args=ap.parse_args();configure()
    if args.from_recovery and args.action!='restore':ap.error('from-recovery only for restore')
    print(json.dumps(restore(args.from_recovery) if args.action=='restore' else globals()[args.action](),indent=2))
