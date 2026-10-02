#!/usr/bin/env python3
"""One registered startup diagnostic, no observer/PPS/charge enable; exact rollback."""
import importlib.util
import json
from pathlib import Path
import re
import errno
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p
spec=importlib.util.spec_from_file_location('test298_reused_transport',R.parent/'test-292-passive-observation/host_flow.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

def read(path):return json.loads(Path(path).read_text())
def write(path,value):h.write(path,value)

def configure():
    h.R=R;h.PLAN=read(R/'registration.json');h.PACKAGE=read(R/'PACKAGE.json')
    h.STAGED=read(R/'staged-files.json');h.STAGE='D:/android/gts9-active/gts9-test298'
    h.TMP='/tmp/gts9-test298'
    # Reused ssh() remains strict and pins the already authenticated device key.
    h.TRUST=Path('/tmp/gts9-test292-known-hosts')
    p.SERIAL='gts9wifi-0001'


def transfer(rec):
    import hashlib,shlex
    local=Path('/mnt/d/android/gts9-active/gts9-test298')
    for name,m in h.STAGED.items():
        content=(local/name).read_bytes()
        if len(content)!=m['bytes'] or hashlib.sha256(content).hexdigest()!=m['sha256']:raise ValueError('stage drift '+name)
    rec.host_adb('push-package','-s',p.SERIAL,'push',h.STAGE,'/tmp/',timeout=60)
    expected=''.join(m['sha256']+'  '+h.TMP+'/'+name+'\n' for name,m in h.STAGED.items())
    rec.adb('verify-package','printf %s '+shlex.quote(expected)+' | sha256sum -c -',timeout=20)
    rec.adb('mount-root','sh '+h.TMP+'/mount-debian.sh',timeout=15)

h.transfer=transfer


def identity(raw,notes,expected=None):
    s=h.g.baseline.sections(raw);boot=s['boot'].strip().replace('-','')
    if not re.fullmatch('[0-9a-f]{32}',boot):raise ValueError('boot ID')
    if expected and boot!=expected:raise ValueError('boot changed')
    if '7.2.0-rc3-gts9wifi-dirty' not in s['uname']:raise ValueError('kernel release')
    if s['cmdline'].strip()!=h.PLAN['runtime_cmdline']:raise ValueError('cmdline changed')
    if [x.split()[0] for x in s['identity'].splitlines()]!=[h.PLAN['config_sha256'],notes]:raise ValueError('config/notes')
    b=dict(x.split('=',1) for x in s['battery'].splitlines() if '=' in x)
    if b['POWER_SUPPLY_HEALTH']!='Good' or not 100<=int(b['POWER_SUPPLY_TEMP'])<420:raise ValueError('battery/temperature')
    if not 3400000<=int(b['POWER_SUPPLY_VOLTAGE_NOW'])<=4440000:raise ValueError('gauge voltage')
    if s['dcc'].strip()!='absent' or s['failed'].strip():raise ValueError('DCC/systemd')
    if s['services'].splitlines().count('active')!=3 or s['roles'].splitlines()!=['[sink]','[device]']:raise ValueError('services/roles')
    if 'usb0    inet 169.254.42.1/' not in s['network']:raise ValueError('device NCM')
    snap=dict(x.split('=',1) for x in s['snapshot'].splitlines() if '=' in x)
    if snap.get('pump_enable_supported')!='0':raise ValueError('pump capability')
    if snap.get('sample_valid')!='1':raise ValueError('missing cached startup sample')
    for label in ['sample','startup']:
        if int(snap[label+'_mode_before'],0)&12 or int(snap[label+'_mode_after'],0)&12:raise ValueError('pump mode not OFF')
        if int(snap[label+'_faults'],0) not in [0,128]:raise ValueError('new SM5440 fault')
        if int(snap[label+'_ibus_ua'])!=0:raise ValueError('pump current')
    if snap.get('last_sample_error')!='0':raise ValueError('new ADC error')
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',s['network'])
    wifi=addresses[0] if len(addresses)==1 else None
    return s,boot,wifi,snap


def scan_journal(raw,boot,uptime,snapshot):
    old=(R.parent/'test-292-passive-observation/final-diagnostic/kernel-json.txt').read_text()
    known={x['MESSAGE'] for line in old.splitlines() if int((x:=json.loads(line)).get('PRIORITY',7))<=3 and not x['MESSAGE'].startswith(('sm5440-direct ', 'sm5440-passive '))}
    scan=h.g.evidence.inspect_journal(raw,boot,known,require_start=True,
        accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),
        accepted_qca_cycles=True,observed_uptime=uptime)
    rows=[json.loads(line) for line in raw.splitlines()]
    triplets=h.g.startup_triplets(rows,True)
    bounded={n for group in triplets for n in group['rows']}
    refused=[]
    for suspect in scan['suspects']:
        m=suspect['message']
        if suspect['row'] in bounded:continue
        if m=='sm5440-passive 0-0063: passive startup confirmation failed' and snapshot['fault']=='1':
            refused.append(suspect);continue
        if m.startswith('sm5440-passive 0-0063: passive fault bitmap=0x80 ') and snapshot['startup_faults']=='0x80':
            refused.append(suspect);continue
        raise ValueError('new/unclassified kernel suspect: '+m)
    if scan['fault_counts']:raise ValueError('CPU/kernel failure')
    scan.update(known_startup_refusal=refused,display_diagnostic=triplets,
                charging_authorized=False,stability_clean_claim=False)
    return scan


def ncm_probe(rec,boot):
    # Owner's device-centred OFF-only scope: one host probe, no waiting/retry.
    raw,status=rec.command('ncm-ssh',['ssh','-i','/home/ms/.ssh/gts9_ed25519',
        '-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes',
        '-o','UserKnownHostsFile='+str(h.TRUST),'-o','HostKeyAlias=gts9-test292',
        'root@169.254.42.1','cat /proc/sys/kernel/random/boot_id; uname -a'],
        timeout=8,required=False)
    if status==0 and raw.splitlines()[0].replace('-','')!=boot:
        raise ValueError('NCM boot attribution')
    return raw,status


def boundary(folder,notes,before,boots_before):
    rec=p.Recorder(folder);p.SERIAL='gts9wifi-0001';start=time.monotonic();i=0
    # Stop as soon as ADB/services/NCM are ready; no Wi-Fi DHCP/fixed window wait.
    while time.monotonic()-start<150:
        raw,status=rec.adb(f'readiness-{i:02}',h.PLAN['current_command'],timeout=8,required=False);i+=1
        if status==0 and re.search(r'last_sample_error=(-?\d+)',raw) and int(re.search(r'last_sample_error=(-?\d+)',raw)[1]):
            rec.adb('kernel-first-fault','journalctl -k -b -o json --no-pager',timeout=15,required=False)
            raise ValueError('new ADC/rearm error; no further test')
        if status==0 and raw.splitlines().count('active')==3 and 'sample_valid=1' in raw and 'usb0    inet 169.254.42.1/' in raw:break
        time.sleep(3)
    else:raise TimeoutError('rescue/endpoint unavailable')
    try:sections,boot,wifi,snap=identity(raw,notes)
    except Exception:
        rec.adb('kernel-first-fault','journalctl -k -b -o json --no-pager',timeout=15,required=False)
        raise
    jobs=h.parallel({'kernel':lambda:rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15),
       'boots':lambda:rec.adb('boots-after','journalctl --list-boots --no-pager',timeout=10),
       'ncm':lambda:ncm_probe(rec,boot),
       'windows':lambda:rec.ps('windows-usb',p.PS_USB,timeout=20)})
    if p.has_code43(jobs['windows'][0]):raise ValueError('WindowsCode43')
    if h.g.evidence.attribute(before,boot,boots_before,jobs['boots'][0])!='attributed':raise ValueError('unexpected/extra boot')
    scan=scan_journal(jobs['kernel'][0],boot,float(sections['uptime'].split()[0]),snap)
    write(folder/'journal-classification.json',scan)
    summary=dict(verdict='STARTUP_DIAGNOSTIC_CAPTURED_NO_CHARGING_GRANT',boot_id=boot,wifi=wifi,
                 snapshot=snap,ADB=True,authenticated_NCM_SSH=(jobs['ncm'][1]==0),NCM_host_probe_status=jobs['ncm'][1],WiFi_host_reachability='not_required_PC_USB_scope',device_NCM=True,Code43=False,charging_authorized=False)
    write(folder/'summary.json',summary)
    return summary


def parse_runtime(raw,boot):
    """One actual API call: stable fixed evidence or explicit PC no-data refusal."""
    sections=h.g.baseline.sections(raw)
    if sections['before'].strip().replace('-','')!=boot or sections['after'].strip().replace('-','')!=boot:
        raise ValueError('runtime boot attribution')
    fields={}
    for line in sections['runtime'].splitlines():
        key,value=line.split('=',1)
        if key in fields:raise ValueError('duplicate runtime field')
        fields[key]=value
    expected={'format':'sm5714-current-port-v1','charging_grant':'0','values_are_not_physical_measurements':'1'}
    if any(fields.get(k)!=v for k,v in expected.items()):raise ValueError('runtime format/grant')
    ret=int(fields['ret']);kind='FIXED_TCPM_OBSERVATION'
    supply=sections['supply']
    if ret==-errno.ENODATA:
        if set(fields)!=set(expected)|{'ret'} or '[PD]' in supply or '[PD_PPS]' in supply:
            raise ValueError('no-data refusal conflicts with supply evidence')
        kind='PC_NO_PD_CAPABILITY_REFUSED'
    elif ret:
        raise ValueError('runtime API first refusal '+str(ret))
    else:
        vals={k:int(fields[k]) for k in ('instance','source_generation','budget_generation','started_ms','completed_ms','online','usb_type','voltage_uv','current_ua','budget_mv','budget_ma','charge_requested','nr_source_pdos')}
        if any(vals[k]<=0 for k in ('instance','source_generation','budget_generation','started_ms')):
            raise ValueError('runtime generation/time')
        if not 0<=vals['completed_ms']-vals['started_ms']<=1000:
            raise ValueError('runtime acquisition window')
        # Pinned Linux7.2 power_supply_usb_type: fixed PD=6, PPS=8.
        if vals['online']!=1 or vals['usb_type']!=6 or vals['charge_requested']!=1 or '[PD]' not in supply:
            raise ValueError('runtime not fixed PD')
        mv,ma=vals['budget_mv'],vals['budget_ma']
        if mv not in (5000,9000) or not 100<=ma<=(1800 if mv==5000 else 1500):
            raise ValueError('runtime fixed ceiling')
        if vals['voltage_uv']!=mv*1000 or vals['current_ua']!=ma*1000 or ('POWER_SUPPLY_VOLTAGE_NOW='+str(vals['voltage_uv'])) not in supply.splitlines() or ('POWER_SUPPLY_CURRENT_NOW='+str(vals['current_ua'])) not in supply.splitlines():
            raise ValueError('runtime mirror inconsistency')
        count=vals['nr_source_pdos']
        if not 1<=count<=7:raise ValueError('runtime source count')
        pdos=[int(fields['source_pdo_'+str(i)],0) for i in range(1,count+1)]
        if any(not 0<p<=0xffffffff for p in pdos):raise ValueError('runtime source word')
        if not any(p>>30==0 and ((p>>10)&1023)*50==mv and (p&1023)*10>=ma for p in pdos):
            raise ValueError('runtime offered fixed budget missing')
        allowed=set(expected)|{'ret'}|set(vals)|{'source_pdo_'+str(i) for i in range(1,count+1)}
        if set(fields)!=allowed:raise ValueError('unexpected runtime field')
    return dict(verdict=kind,boot_id=boot,api_ret=ret,fields=fields,charging_authorized=False,physical_voltage_verified=False,PPS=False,pump_ON=False)


def observe_runtime(boot):
    rec=p.Recorder(R/'runtime-observation')
    command='set -e; echo @@before; cat /proc/sys/kernel/random/boot_id; echo @@runtime; set -- /sys/kernel/debug/sm5714-*/current-port; test "$#" -eq 1; test -f "$1"; test "$(stat -c %a "$1")" = 400; cat "$1"; echo @@supply; set -- /sys/class/power_supply/tcpm-source-psy-*; test "$#" -eq 1; cat "$1/uevent"; echo @@after; cat /proc/sys/kernel/random/boot_id'
    raw,_=rec.adb('one-runtime-call',command,timeout=10)
    result=parse_runtime(raw,boot)
    write(rec.folder/'summary.json',result)
    return result


def install():
    rec=p.Recorder(R/'installation')
    raw,_=rec.adb('live-boundary',h.PLAN['current_command'],timeout=15)
    identity(raw,h.PLAN['baseline_notes_sha256'],h.PLAN['before_boot_id'])
    h.enter_recovery(rec);h.transfer(rec)
    raw,_=rec.adb('partitions-before',h.PARTS,timeout=20);h.require_partitions(raw,h.PACKAGE['baseline_partitions'])
    h.verify_modules(rec,'original-modules','rollback-modules.sha256')
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    rec.adb('install-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian install {h.TMP}/candidate-modules.sha256 {h.TMP}/candidate-modules.tar.gz {h.TMP}/rollback-modules.sha256',timeout=25)
    h.write_boot(rec,'write-boot','candidate-boot.img',h.PACKAGE['baseline_partitions']['boot'],h.PACKAGE['candidate_partitions']['boot'])
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,h.PACKAGE['candidate_partitions'])
    h.clear_unmount(rec)
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    admitted=boundary(R/'candidate-admission',h.PLAN['candidate_notes_sha256'],h.PLAN['before_boot_id'],(R/'preflight/boots-before.txt').read_text())
    runtime=observe_runtime(admitted['boot_id'])
    admitted['runtime_verdict']=runtime['verdict']
    # One short device endpoint; no trace, module load or new conversion request.
    time.sleep(15)
    end=p.Recorder(R/'endpoint')
    raw,_=end.adb('current-state',h.PLAN['current_command'],timeout=15)
    sec,boot,wifi,snap=identity(raw,h.PLAN['candidate_notes_sha256'],admitted['boot_id'])
    kernel,_=end.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15)
    write(end.folder/'journal-classification.json',scan_journal(kernel,boot,float(sec['uptime'].split()[0]),snap))
    write(end.folder/'summary.json',dict(boot_id=boot,snapshot=snap,charging_authorized=False,observation_seconds=15))
    return admitted


def rollback():
    rec=p.Recorder(R/'rollback-install')
    # Recovery must also work when admission stopped before summary publication.
    target,_=rec.adb('target-boot-id','cat /proc/sys/kernel/random/boot_id',timeout=8)
    boots,_=rec.adb('target-boots','journalctl --list-boots --no-pager',timeout=10)
    target=target.strip().replace('-','')
    h.enter_recovery(rec);h.transfer(rec)
    raw,_=rec.adb('partitions-before',h.PARTS,timeout=20);h.require_partitions(raw,h.PACKAGE['candidate_partitions'])
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    rec.adb('restore-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256',timeout=25)
    h.write_boot(rec,'restore-boot','rollback-test263-boot.img',h.PACKAGE['candidate_partitions']['boot'],h.PACKAGE['baseline_partitions']['boot'])
    h.verify_modules(rec,'restored-modules','rollback-modules.sha256')
    raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,h.PACKAGE['baseline_partitions'])
    h.clear_unmount(rec);rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    return boundary(R/'final-acceptance',h.PLAN['baseline_notes_sha256'],target,boots)

if __name__=='__main__':
    configure()
    print(json.dumps({'install':install,'rollback':rollback}[sys.argv[1]](),indent=2),flush=True)
