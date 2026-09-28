from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'scripts');import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline();r=p.Recorder(Path('reference/boot-tests/test-253-adbd-usb-reconnect/post-stop'))
def ssh(n,s,t=30):return r.command(n,['env','GTS9_DEVICE=10.191.121.195',p.SSH,s],timeout=t)[0]
boot=ssh('boot-id','cat /proc/sys/kernel/random/boot_id').strip();cfg=ssh('embedded-config','zcat /proc/config.gz');parts=ssh('partitions','for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done',50)
mods=ssh('module-hashes',f'find {p.MODULE_ROOT} -type f -exec sha256sum {{}} +',50);old=ssh('backup-module-hashes','find /usr/lib/modules/.gts9-test252-original -type f -exec sha256sum {} +',50)
raw=ssh('kernel-journal-json','journalctl -k -b --no-pager -o json');ssh('kernel-journal','journalctl -k -b --no-pager -o short-monotonic');up=float(ssh('uptime','cat /proc/uptime').split()[0]);scan=p.inspect(raw,p.evidence.canonical_boot_id(boot),base,up);p.write_json(r.folder/'kernel-scan.json',scan)
pnp,_=r.ps('windows-pnp',p.PS_USB,timeout=30);r.host_adb('adb-state','devices','-l');banner,_=r.ps('windows-ncm-banner',p.PS_NCM_BOUND_BANNER,timeout=30);r.ssh('ncm-ssh','cat /proc/sys/kernel/random/boot_id',timeout=18)
root=Path('reference/boot-tests/test-252-sm5714-stage1');art=json.loads((root/'ARTIFACTS.json').read_text());exp={n:v['accepted_device_sha256'] for n,v in art['partitions'].items()};exp['boot']=art['partitions']['boot']['candidate_sha256']
assert p.parse_hashes(parts,'/dev/disk/by-partlabel/')==exp;assert p.parse_hashes(mods,p.MODULE_ROOT+'/')==json.loads((root/'validation/module-hashes.json').read_text());assert p.parse_hashes(old,'/usr/lib/modules/.gts9-test252-original/')==base['modules'];assert hashlib.sha256(cfg.encode()).hexdigest()==art['kernel_artifacts']['config'];assert not scan['fault_counts'] and not scan['suspects'];assert not p.has_code43(pnp);assert p.bound_banner_ok(banner)
p.write_json(r.folder/'summary.json',dict(verdict='read-only post-stop identity preserved; not acceptance',boot_id=boot,kernel_scan=scan,partitions_verified=5,modules_verified=181,backup_modules_verified=181,no_code43=True,ncm_ssh_ok=True,device_changes=False))
