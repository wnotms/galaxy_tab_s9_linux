from pathlib import Path
import hashlib,json,gzip,subprocess
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=Path('/sys/class/power_supply/sm5714-battery');u=Path('/sys/class/power_supply/sm5714-usb')
config=gzip.decompress(Path('/proc/config.gz').read_bytes())
protected={}
for directory,pattern in [('/usr/libexec','gts9*'),('/usr/local/libexec','gts9*'),('/usr/lib/systemd/system','gts9*'),('/etc/systemd/system','gts9*')]:
 for path in sorted(Path(directory).glob(pattern)):
  if path.is_file():protected[str(path)]=sha(path)
mods=Path('/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty')
module_hashes={str(p.relative_to(mods)):sha(p) for p in sorted(mods.rglob('*')) if p.is_file()}
partitions={}
for name in ('boot','vendor_boot','init_boot','dtbo','vbmeta'):
 path=Path('/dev/disk/by-partlabel')/name
 h=hashlib.sha256()
 with path.open('rb') as stream:
  while data:=stream.read(1048576):h.update(data)
 partitions[name]=h.hexdigest()
flags={}
for name in ('direct_charge','direct_charge_once','fixed_return_check','pps_return_check'):
 path=Path('/sys/module/sm5440_fedora/parameters')/name
 flags[name]=path.read_text().strip() if path.exists() else 'absent'
def command(args):
 p=subprocess.run(args,capture_output=True,text=True)
 return dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),machine_id=Path('/etc/machine-id').read_text().strip(),uname=command(['uname','-a']),cmdline=Path('/proc/cmdline').read_text(),uptime=Path('/proc/uptime').read_text(),config_sha256=hashlib.sha256(config).hexdigest(),notes_sha256=sha(Path('/sys/kernel/notes')),dcc_enabled=b'CONFIG_HVC_DCC=y' in config,hvc_dev=Path('/dev/hvc0').exists(),hvc_sys=Path('/sys/class/tty/hvc0').exists(),battery={n:(b/n).read_text().strip() for n in ('status','health','present','capacity','voltage_now','current_now','temp')},usb_online=(u/'online').read_text().strip(),pump_optins=flags,partitions=partitions,module_hashes=module_hashes,protected_rootfs=protected,services=command(['systemctl','is-active','ssh','gts9-adbd','gts9-usb-acm']),failed=command(['systemctl','--failed','--no-legend','--no-pager']),GDM=command(['systemctl','is-active','gdm.service','gdm3.service','display-manager.service']),root_space=command(['df','-B1','/']),network=command(['ip','-br','address'])),indent=2))
