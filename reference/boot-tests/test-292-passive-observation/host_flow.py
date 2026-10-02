#!/usr/bin/env python3
"""Registered Test292 boundary runner; no retry of observation or charging."""
import concurrent.futures
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shlex
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

g=load('test292gate',R.parent/'test-286-smmu-startup-offline/gate.py')
recovery=load('test292recovery',R.parent/'test-283-startup-adc-event-offline/host_flow.py')

def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
PLAN=read(R/'registration.json');PACKAGE=read(R/'PACKAGE.json');STAGED=read(R/'staged-files.json')
STAGE='D:/android/gts9-active/gts9-test292'
TMP='/tmp/gts9-test292'
PARTS='sha256sum '+ ' '.join('/dev/block/by-name/'+x for x in ('boot','vendor_boot','init_boot','dtbo','vbmeta'))
TRUST=Path('/tmp/gts9-test292-known-hosts')

def partitions(raw):
    result={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)==2 and fields[1].startswith('/dev/block/by-name/'):
            key=fields[1].split('/')[-1]
            if key in result:raise ValueError('duplicate partition')
            result[key]=fields[0]
    return result

def require_partitions(raw,expected):
    if partitions(raw)!=expected:raise ValueError('allfive partition identity')


def ssh(rec,name,wifi,boot):
    raw,_=rec.command(name,['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(TRUST),'-o','HostKeyAlias=gts9-test292','root@'+wifi,'cat /proc/sys/kernel/random/boot_id; uname -a'],timeout=12)
    if raw.splitlines()[0].replace('-','')!=boot:raise ValueError('Wi-Fi different boot')
    return raw

def parallel(jobs):
    # Inspect every future even when another gate fails; preserve all raw evidence.
    results,errors={},[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        fs={key:pool.submit(fn) for key,fn in jobs.items()}
        for key,f in fs.items():
            try:results[key]=f.result()
            except Exception as exc:errors.append(key+': '+str(exc))
    if errors:raise RuntimeError('; '.join(errors))
    return results


def debian_ready(raw,status):
    # Services can be active before DHCP. Wait within the same180s bound;
    # do not start a new boot or relax final identity/authentication gates.
    addresses=re.findall(r'\bwlp1s0\s+inet\s+[0-9]+(?:\.[0-9]+){3}/[0-9]+',raw)
    return status==0 and raw.splitlines().count('active')==3 and 'sample_valid=1' in raw and len(addresses)==1


def wait_debian(rec):
    start=time.monotonic();i=0
    while time.monotonic()-start<180:
        raw,status=rec.adb(f'readiness-{i:02}','set -e; cat /proc/sys/kernel/random/boot_id; systemctl is-active ssh gts9-adbd gts9-usb-acm; ip -4 -o addr show wlp1s0; cat /sys/kernel/debug/sm5440-0-0063/snapshot',timeout=5,required=False)
        i+=1
        if debian_ready(raw,status):return
        time.sleep(3)
    raise TimeoutError('Debian unavailable; no repeat reboot')


def boundary(folder,notes,before_boot,before_boots):
    p.SERIAL='gts9wifi-0001';rec=p.Recorder(folder);wait_debian(rec)
    raw,_=rec.adb('current-state',PLAN['current_command'],timeout=15)
    sec=g.baseline.sections(raw);boot,health=g.identity(sec,PLAN,notes)
    wifi=g.wifi_address(sec)
    jobs=parallel({'kernel':lambda:rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15),'boots':lambda:rec.adb('boots-after','journalctl --list-boots --no-pager',timeout=10),'wifi':lambda:ssh(rec,'wifi',wifi,boot),'windows':lambda:rec.ps('windows-usb',p.PS_USB,timeout=20)})
    if p.has_code43(jobs['windows'][0]):raise ValueError('WindowsCode43')
    if g.evidence.attribute(before_boot,boot,before_boots,jobs['boots'][0])!='attributed':raise ValueError('unattributed/extra boot')
    known={x['MESSAGE'] for line in (R.parent/'test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt').read_text().splitlines() if int((x:=json.loads(line)).get('PRIORITY',7))<=3}
    scan=g.journal(jobs['kernel'][0],boot,known,float(sec['uptime'].split()[0]),sec,PLAN,notes)
    write(folder/'journal-classification.json',scan)
    summary=dict(verdict='ACCEPTED_REGISTERED_PASSIVE_ENDPOINT',boot_id=boot,wifi=wifi,health=health,kernel_fault_counts=scan['fault_counts'],Code43=False,ADB=True,authenticated_WiFi=True,device_NCM=True,stability_clean_claim=False)
    write(folder/'summary.json',summary)
    return summary,jobs['boots'][0]


def enter_recovery(rec):
    p.SERIAL='gts9wifi-0001'
    rec.adb('helper-check','TMPDIR=/tmp gts9-debian-to-recovery --check',timeout=10)
    rec.adb('bcb-request','TMPDIR=/tmp gts9-debian-to-recovery --yes --no-reboot',timeout=10)
    rec.adb('ordinary-reboot','systemctl reboot',timeout=10,required=False)
    write(rec.folder/'recovery-wait.json',recovery.wait_recovery(rec))
    p.SERIAL='R52X10045LT'
    identity,_=rec.adb('twrp-identity','set -e; getprop ro.product.device; uname -a; id; test "$(blockdev --getsize64 /dev/block/by-name/boot)" = 100663296; test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576',timeout=10)
    if 'gts9wifi' not in identity or 'uid=0' not in identity or '7.2.0-rc3' in identity:raise ValueError('TWRP identity')
    rec.adb('ancillary','echo @@recovery-dmesg; dmesg; echo @@pstore; ls -la /sys/fs/pstore; for f in /sys/fs/pstore/* /proc/last_kmsg; do if test -f "$f"; then echo @@source=$f; cat "$f"; else echo unavailable=$f; fi; done',timeout=15)


def transfer(rec):
    # All source hashes are fixed at registration; single native directory push.
    local=Path('/mnt/d/android/gts9-active/gts9-test292')
    for name,m in STAGED.items():
        content=(local/name).read_bytes()
        if len(content)!=m['bytes'] or hashlib.sha256(content).hexdigest()!=m['sha256']:raise ValueError('stage drift '+name)
    rec.host_adb('push-package','-s',p.SERIAL,'push',STAGE,'/tmp/',timeout=60)
    expected=''.join(m['sha256']+'  '+TMP+'/'+name+'\n' for name,m in STAGED.items())
    rec.adb('verify-package','printf %s '+shlex.quote(expected)+' | sha256sum -c -',timeout=20)
    rec.adb('mount-root','sh '+TMP+'/mount-debian.sh',timeout=15)


def verify_modules(rec,name,manifest):
    command='set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; cd /mnt/debian/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty; test "$(find . -type f | wc -l)" = 181; sha256sum -c '+TMP+'/'+manifest
    rec.adb(name,command,timeout=20)


def clear_unmount(rec):
    raw,_=rec.adb('clear-bcb-unmount','set -e; test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576; dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc; sync; umount /mnt/debian; dd if=/dev/block/by-name/misc bs=32 count=1 2>/dev/null | od -An -v -tx1',timeout=15)
    if any(word!='00' for word in raw.split()):raise ValueError('BCB clear')


def write_boot(rec,name,source,current,desired):
    command=f'set -e; test "$(blockdev --getsize64 /dev/block/by-name/boot)" = 100663296; test "$(sha256sum /dev/block/by-name/boot | cut -d " " -f1)" = {current}; test "$(sha256sum {TMP}/{source} | cut -d " " -f1)" = {desired}; dd if={TMP}/{source} of=/dev/block/by-name/boot bs=4M; sync'
    rec.adb(name,command,timeout=20)


def install():
    rec=p.Recorder(R/'installation')
    # Fresh combined current safety/identity, not another full hash/journal run.
    raw,_=rec.adb('live-boundary',PLAN['current_command'],timeout=15)
    g.identity(g.baseline.sections(raw),PLAN,PLAN['baseline_notes_sha256'],PLAN['before_boot_id'])
    enter_recovery(rec);transfer(rec)
    raw,_=rec.adb('partitions-before',PARTS,timeout=20);require_partitions(raw,PACKAGE['baseline_partitions'])
    verify_modules(rec,'original-modules','rollback-modules.sha256')
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    rec.adb('install-modules',f'sh {TMP}/module-swap.sh /mnt/debian install {TMP}/candidate-modules.sha256 {TMP}/candidate-modules.tar.gz {TMP}/rollback-modules.sha256',timeout=25)
    write_boot(rec,'write-boot','candidate-boot.img',PACKAGE['baseline_partitions']['boot'],PACKAGE['candidate_partitions']['boot'])
    raw,_=rec.adb('partitions-after',PARTS,timeout=20);require_partitions(raw,PACKAGE['candidate_partitions'])
    clear_unmount(rec)
    write(rec.folder/'summary.json',dict(verdict='PAIRED_INSTALL_READBACK_VERIFIED',partitions=PACKAGE['candidate_partitions'],modules=181))
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    return boundary(R/'candidate-admission',PLAN['candidate_notes_sha256'],PLAN['before_boot_id'],(R/'preflight/boots-before.txt').read_text())


def observe():
    admitted=read(R/'candidate-admission/summary.json');rec=p.Recorder(R/'observation');p.SERIAL='gts9wifi-0001'
    packet=dict(PLAN,boot_id=admitted['boot_id'],verdict='READY_FOR_REGISTERED_PASSIVE_OBSERVATION',paired_install_verified=True,health_rescue_verified=True)
    path=R/'observation/verified-packet.json';write(path,packet)
    packet_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    windows=Path('/mnt/d/android/gts9-active/gts9-test292/verified-packet.json');windows.write_bytes(path.read_bytes())
    rec.host_adb('push-packet','-s',p.SERIAL,'push',STAGE+'/verified-packet.json',TMP+'/verified-packet.json',timeout=10)
    rec.adb('prepare-tools',f'set -e; test ! -e {TMP}/tools; mkdir {TMP}/tools; tar -xf {TMP}/portable.tar -C {TMP}/tools; test "$(sha256sum {TMP}/observer.ko | cut -d " " -f1)" = '+PLAN['observer_sha256'],timeout=10)
    rec.adb('one-coordinator',f'python3 {TMP}/tools/device_ops.py --packet {TMP}/verified-packet.json --packet-sha256 {packet_hash} --module {TMP}/observer.ko --output {TMP}/device-capture',timeout=25,required=False)
    rec.adb('package-capture',f'set -e; tar -cf {TMP}/device-capture.tar -C {TMP}/device-capture .; sha256sum {TMP}/device-capture.tar',timeout=10)
    native=STAGE+'/device-capture.tar';rec.host_adb('pull-capture','-s',p.SERIAL,'pull',TMP+'/device-capture.tar',native,timeout=15)
    archive=Path('/mnt/d/android/gts9-active/gts9-test292/device-capture.tar');shutil_copy(archive,R/'observation/device-capture.tar')
    import tarfile
    target=R/'observation/device-capture';target.mkdir()
    with tarfile.open(archive) as tf:tf.extractall(target,filter='data')
    result=read(target/'observation/summary.json')
    raw,_=rec.adb('current-state',PLAN['current_command']+'; echo @@observer; test ! -e /sys/module/sm5440_passive_observer; test ! -e /sys/kernel/debug/sm5440-passive-observer; echo absent',timeout=15)
    sec=g.baseline.sections(raw);boot,health=g.identity(sec,PLAN,PLAN['candidate_notes_sha256'],admitted['boot_id'])
    jobs=parallel({'kernel':lambda:rec.adb('kernel-json','journalctl -k -b -o json --no-pager',timeout=15),'wifi':lambda:ssh(rec,'wifi',admitted['wifi'],boot)})
    known={x['MESSAGE'] for line in (R.parent/'test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt').read_text().splitlines() if int((x:=json.loads(line)).get('PRIORITY',7))<=3}
    scan=g.journal(jobs['kernel'][0],boot,known,float(sec['uptime'].split()[0]),sec,PLAN,PLAN['candidate_notes_sha256']);write(rec.folder/'journal-classification.json',scan)
    write(rec.folder/'endpoint-summary.json',dict(verdict='DEVICE_PASSIVE_SCOPE_COMPLETED',boot_id=boot,health=health,observer_absent=True,kernel_fault_counts=scan['fault_counts'],ADB=True,authenticated_WiFi=True,device_NCM=True,charging_authorized=False))
    return result


def shutil_copy(src,dst):
    import shutil
    if dst.exists():raise ValueError('evidence overwrite')
    shutil.copyfile(src,dst)


def rollback():
    rec=p.Recorder(R/'rollback-install');enter_recovery(rec);transfer(rec)
    raw,_=rec.adb('partitions-before',PARTS,timeout=20);require_partitions(raw,PACKAGE['candidate_partitions'])
    rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
    rec.adb('restore-modules',f'sh {TMP}/module-swap.sh /mnt/debian restore {TMP}/rollback-modules.sha256',timeout=25)
    write_boot(rec,'restore-boot','rollback-test263-boot.img',PACKAGE['candidate_partitions']['boot'],PACKAGE['baseline_partitions']['boot'])
    raw,_=rec.adb('partitions-after',PARTS,timeout=20);require_partitions(raw,PACKAGE['baseline_partitions'])
    rec.adb('backup-list','find /mnt/debian/usr/lib/modules -maxdepth 1 -name ".gts9-test*"',timeout=10)
    clear_unmount(rec);write(rec.folder/'summary.json',dict(verdict='EXACT263_ROLLBACK_READBACK_VERIFIED',partitions=PACKAGE['baseline_partitions'],modules=181))
    rec.host_adb('normal-reboot','-s',p.SERIAL,'reboot',timeout=10)
    before=read(R/'candidate-admission/summary.json')['boot_id']
    return boundary(R/'final-acceptance',PLAN['baseline_notes_sha256'],before,(R/'candidate-admission/boots-after.txt').read_text())

if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='install':result=install()
    elif stage=='observe':result=observe()
    elif stage=='rollback':result=rollback()
    else:raise SystemExit('install /observe /rollback only')
    print(json.dumps(result,indent=2),flush=True)
