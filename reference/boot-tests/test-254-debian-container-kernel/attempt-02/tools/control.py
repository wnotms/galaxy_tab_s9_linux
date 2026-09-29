import sys,json,hashlib,base64,subprocess,shutil,tarfile,tempfile,os,time
from pathlib import Path
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05'
T=ROOT/'reference/boot-tests/test-254-debian-container-kernel'; A=T/'attempt-02'
OLD=ROOT/'reference/boot-tests/test-252-sm5714-stage1'
LAST=ROOT/'reference/boot-tests/test-253-adbd-usb-reconnect/attempt-04/final-acceptance'
W=Path('/mnt/d/android/gts9-active/gts9-test254');W.mkdir(exist_ok=True)
WIFI='10.191.121.167'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def save(path,obj): p.write_json(path,obj)
def hashes(raw,prefix):return p.parse_hashes(raw,prefix)
class WiFi(p.Recorder):
    def adb(self,name,script,timeout=15,required=True):
        if name == 'bluetooth-state':
            script=script.replace("ls /sys/class/bluetooth", "ls /sys/class/bluetooth | sed -n '/^hci[0-9][0-9]*$/p'")
        return self.command(name,['env','GTS9_DEVICE='+WIFI,p.SSH,script],timeout,required)

def collect(folder,candidate=False,transport=True):
    assert not folder.exists(),folder
    r=WiFi(folder);art=json.loads((T/'ARTIFACTS.json').read_text()) if candidate else json.loads((OLD/'ARTIFACTS.json').read_text())
    base=p.baseline();ex=dict(base);ex['config_sha256']=art['kernel_artifacts']['config'];ex['notes_sha256']=art['kernel_notes_sha256']
    state=p.production_state(r,ex,full=False)
    cfg=r.adb('embedded-config','zcat /proc/config.gz',25)[0]
    assert hashlib.sha256(cfg.encode()).hexdigest()==ex['config_sha256']
    notes=base64.b64decode(''.join(r.adb('notes-base64','base64 /sys/kernel/notes')[0].split()),validate=True)
    (folder/'kernel-notes.bin').write_bytes(notes);assert sha(folder/'kernel-notes.bin')==ex['notes_sha256']
    parts=hashes(r.adb('partitions','set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done',45)[0],'/dev/disk/by-partlabel/')
    exp=hashes((LAST/'partitions.txt').read_text(),'/dev/disk/by-partlabel/')
    if candidate: exp['boot']=json.loads((A/'packaging/artifacts.json').read_text())['boot_sha256']
    assert parts==exp,('partition identity',parts,exp)
    mods=hashes(r.adb('module-hashes',f'find {p.MODULE_ROOT} -type f -exec sha256sum {{}} +',45)[0],p.MODULE_ROOT+'/')
    mf=(T if candidate else OLD)/'validation/module-hashes.json';assert mods==json.loads(mf.read_text()) and len(mods)==181
    b='/usr/lib/modules/.gts9-test252-original/'
    backup=hashes(r.adb('backup-module-hashes','find '+b+' -type f -exec sha256sum {} +',45)[0],b)
    assert backup==base['modules'] and len(backup)==181
    dirs=r.adb('module-directories','find /usr/lib/modules -maxdepth 1 -type d -print; find '+p.MODULE_ROOT+' -type l -exec ls -l {} +')[0]
    if candidate:
        b='/usr/lib/modules/.gts9-test254-original/'
        orig=hashes(r.adb('test252-rollback-module-hashes','find '+b+' -type f -exec sha256sum {} +',45)[0],b)
        assert orig==json.loads((OLD/'validation/module-hashes.json').read_text())
    else: assert '.gts9-test254' not in dirs
    cmd='set -eu; sha256sum '+ ' '.join(line.split(maxsplit=1)[1] for line in (LAST/'protected-settings-hashes.txt').read_text().splitlines())
    protected=r.adb('protected-settings-hashes',cmd,25)[0]; assert protected==(LAST/'protected-settings-hashes.txt').read_text()
    users=r.adb('userspace-state',"set -e; pid=$(systemctl show -p MainPID --value gts9-adbd.service); echo PID=$pid; readlink /proc/$pid/exe; sha256sum /proc/$pid/exe; sha256sum /usr/libexec/gts9-adbd-run /usr/lib/systemd/system/gts9-adbd.service /usr/local/libexec/gts9-adbd-reconnect; systemctl cat gts9-adbd.service")[0]
    assert '/usr/local/libexec/gts9-adbd-reconnect' in users and '053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5' in users
    if candidate:
        before=(A/'preflight/userspace-state.txt').read_text();a=[x for x in users.splitlines() if x.endswith(('/usr/libexec/gts9-adbd-run','/usr/lib/systemd/system/gts9-adbd.service','/usr/local/libexec/gts9-adbd-reconnect')) and len(x.split()[0])==64];b=[x for x in before.splitlines() if x.endswith(('/usr/libexec/gts9-adbd-run','/usr/lib/systemd/system/gts9-adbd.service','/usr/local/libexec/gts9-adbd-reconnect')) and len(x.split()[0])==64];assert a==b
        assert (folder/'cmdline.txt').read_bytes()==(A/'preflight/cmdline.txt').read_bytes()
    raw=r.adb('kernel-journal-json','journalctl -k -b --no-pager -o json',35)[0]
    r.adb('kernel-journal','journalctl -k -b --no-pager -o short-monotonic',35)
    scan=p.inspect(raw,state['boot_id'],base,state['uptime_seconds']);save(folder/'kernel-scan.json',scan)
    assert not scan['fault_counts'] and not scan['suspects'],scan
    r.adb('boot-history','journalctl --list-boots --no-pager',25)
    supplies=r.adb('supplies','cat /sys/class/power_supply/sm5714-battery/uevent; cat /sys/class/power_supply/sm5714-usb/uevent')[0]
    props=dict(x.split('=',1) for x in supplies.splitlines() if x.startswith('POWER_SUPPLY_'))
    assert props['POWER_SUPPLY_HEALTH']=='Good' and 100<=int(props['POWER_SUPPLY_TEMP'])<420 and int(props['POWER_SUPPLY_VOLTAGE_NOW'])<=4440000
    r.adb('system-state','getent passwd 1000; ip -br addr; ip route; df -h /; systemctl show upower.service -p PrivateUsers -p ActiveState -p Result; command -v docker || true; dpkg-query -W docker.io docker-ce containerd iptables nftables uidmap upower 2>/dev/null; true',25)
    if transport:
        normal=p.Recorder(folder/'transport');link=p.transport(normal,state['boot_id'],source_bound=True)
        assert all(link[k] for k in ['adb_ok','ssh_ok','ncm_banner_ok']) and not link['code43'],link
        state['transport']=link
    assert p.evidence.canonical_boot_id(r.adb('end-boot-id','cat /proc/sys/kernel/random/boot_id')[0])==state['boot_id']
    state.update(verdict='passed',full_identity=True,partitions=parts,modules_verified=181,rollback_modules_verified=181,protected_settings_unchanged=True,kernel_scan=scan,temperature_deciC=int(props['POWER_SUPPLY_TEMP']),soc=int(props['POWER_SUPPLY_CAPACITY']),device_writes=False)
    save(folder/'summary.json',state);print(json.dumps(state,indent=2),flush=True)

def package():
    folder=A/'packaging';r=p.Recorder(folder)
    for name,meta in json.loads((T/'SHA256.json').read_text()).items():assert sha(T/name)==meta,name
    art=json.loads((T/'ARTIFACTS.json').read_text())
    for name,digest in art['kernel_artifacts'].items():assert sha(ROOT/'out/kernel-container-candidate'/name)==digest,name
    bundle=ROOT/'out/boot-bundle-container-candidate';ram=bundle/'input/ramdisk'
    assert sha(ram)=='7d524dbcaef4c91fb82a58b794f3a2afa099f1827c1bd0391b65cbcdf2e176fe'
    shutil.copy2(ROOT/'out/boot-bundle-sm5714-stage1/initramfs.manifest',str(ram)+'.manifest')
    env=['env','KERNEL_OUT_DIR='+str(ROOT/'out/kernel-container-candidate'),'MKBOOTIMG='+str(ROOT/'.work/tools/mkbootimg.py'),'AVBTOOL='+str(ROOT/'.work/tools/avbtool.py')]
    if not (folder/'bundle-build.txt').exists(): r.command('bundle-build',env+['scripts/build-boot-bundle.sh','--initramfs',str(ram),'--cmdline','boot/cmdline.example.txt','--bootconfig','boot/bootconfig.example.txt','--out',str(bundle)],timeout=55)
    if not (folder/'bundle-validation.txt').exists(): r.command('bundle-validation',['scripts/validate-boot-bundle.sh','--dir',str(bundle),'--kernel-out','out/kernel-container-candidate'],timeout=55)
    old=ROOT/'out/boot-bundle-sm5714-stage1'
    for n in ['vendor_boot','init_boot','dtbo','vbmeta']:assert sha(bundle/(n+'.img'))==sha(old/(n+'.img')),n
    for n in ['BUNDLE_INFO','SHA256SUMS','initramfs.manifest']:shutil.copy2(bundle/n,folder/n)
    assert sha(old/'boot.img')==hashes((LAST/'partitions.txt').read_text(),'/dev/disk/by-partlabel/')['boot']
    for src,dst in [(bundle/'boot.img','candidate-boot.img'),(old/'boot.img','rollback-boot.img'),(ROOT/'out/kernel-container-candidate/modules-container-candidate.tar.gz','candidate-modules.tar.gz'),(A/'tools/module-swap.sh','module-swap.sh'),(ROOT/'scripts/twrp-mount-debian.sh','twrp-mount-debian.sh')]:shutil.copy2(src,W/dst)
    candidate=json.loads((T/'validation/module-hashes.json').read_text());original=json.loads((OLD/'validation/module-hashes.json').read_text())
    for name,m in [('candidate',candidate),('original',original)]:
        (W/(name+'-module-checksums.txt')).write_text(''.join(v+'  '+k+'\n' for k,v in sorted(m.items())))
        shutil.copy2(W/(name+'-module-checksums.txt'),A/'tools')
    with tarfile.open(W/'candidate-modules.tar','w') as t:
        for name in sorted(candidate):
            t.add(ROOT/'out/kernel-container-candidate/modules-root/lib/modules'/p.RELEASE/name,arcname=p.RELEASE+'/'+name,recursive=False)
    with tarfile.open(W/'candidate-modules.tar') as t:
        files=[x for x in t.getmembers() if x.isfile()];assert len(files)==181
        assert not any(x.issym() or x.islnk() or x.name.startswith('/') or '..' in Path(x.name).parts for x in t.getmembers())
        assert {str(Path(x.name).relative_to(p.RELEASE)):hashlib.sha256(t.extractfile(x).read()).hexdigest() for x in files}==candidate
    with tempfile.TemporaryDirectory(prefix='test254-module-rehearsal-') as d:
        root=Path(d);base=root/'usr/lib/modules';base.mkdir(parents=True);(root/'etc').mkdir();(root/'etc/machine-id').write_text('3c2a1b8f2d624db4b5ffdc836050fcf6\n')
        shutil.copytree(ROOT/'out/kernel-gts9wifi/modules-root/lib/modules'/p.RELEASE,base/p.RELEASE,symlinks=True)
        logs=[]
        for mode,name in [('install','candidate'),('restore','original')]:
            cmd=['sh',str(A/'tools/module-swap.sh'),str(root),mode,str(W/(name+'-module-checksums.txt')),str(W/'candidate-modules.tar'),str(W/'original-module-checksums.txt')]
            envdict=dict(os.environ);envdict['PATH']=str(ROOT/'.work/container-audit/host-bin')+':'+envdict['PATH'];envdict['GTS9_HOST_SYNCFS_REPO']=str(ROOT);envdict['GTS9_HOST_SYNCFS_LOG']=str(ROOT/'.work/test254/rehearsal-sync.jsonl')
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=30,env=envdict);logs.append(dict(argv=cmd,exit=result.returncode,stdout=result.stdout,stderr=result.stderr));assert result.returncode==0,result.stderr
        assert {str(f.relative_to(base/p.RELEASE)):sha(f) for f in (base/p.RELEASE).rglob('*') if f.is_file()}==original
        save(folder/'module-install-restore-rehearsal.json',logs)
    staged={f.name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f in W.iterdir() if f.is_file()}
    save(folder/'artifacts.json',dict(boot_sha256=sha(bundle/'boot.img'),rollback_boot_sha256=sha(old/'boot.img'),partitions_to_write=['boot'],paired_module_files=181,dtb_unchanged=True,other_four_bundle_images_unchanged=True,generated_vbmeta_not_for_flashing=True,windows_staged=staged))
    print('PACKAGING PASSED',sha(bundle/'boot.img'))

if __name__=='__main__':
    if sys.argv[1]=='package':package()
    elif sys.argv[1]=='collect':collect(A/sys.argv[2],candidate='--candidate' in sys.argv,transport='--no-transport' not in sys.argv)
