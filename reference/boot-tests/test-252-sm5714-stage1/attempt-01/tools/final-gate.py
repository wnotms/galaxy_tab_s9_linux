from pathlib import Path
import sys,json,hashlib,re
sys.path.insert(0,str(Path('scripts').resolve()))
import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline();root=Path('reference/boot-tests/test-252-sm5714-stage1');art=json.loads((root/'ARTIFACTS.json').read_text());folder=root/'attempt-01/final-acceptance';assert not folder.exists();rec=p.Recorder(folder)
expected=dict(base);expected['config_sha256']=art['kernel_artifacts']['config'];expected['notes_sha256']=art['kernel_notes_sha256']
state=p.production_state(rec,expected,full=False)
rawcfg=rec.adb('embedded-config','zcat /proc/config.gz',25)[0];assert hashlib.sha256(rawcfg.encode()).hexdigest()==expected['config_sha256']
parts=rec.adb('partitions','for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done',40)[0]
exparts={n:v['accepted_device_sha256'] for n,v in art['partitions'].items()};exparts['boot']=art['partitions']['boot']['candidate_sha256'];assert p.parse_hashes(parts,'/dev/disk/by-partlabel/')==exparts
mods=rec.adb('module-hashes',f'find {p.MODULE_ROOT} -type f -exec sha256sum {{}} +',45)[0];expectedmods=json.loads((root/'validation/module-hashes.json').read_text());assert p.parse_hashes(mods,p.MODULE_ROOT+'/')==expectedmods
backup=rec.adb('backup-module-hashes',f'find /usr/lib/modules/.gts9-test252-original -type f -exec sha256sum {{}} +',45)[0];assert p.parse_hashes(backup,'/usr/lib/modules/.gts9-test252-original/')==base['modules']
link=p.transport(rec,state['boot_id'],source_bound=True);assert all(link[k] for k in ['adb_ok','ssh_ok','ncm_banner_ok']) and not link['code43'] and not link['ncm_initial_failure']
raw=rec.adb('kernel-journal-json','journalctl -k -b --no-pager -o json',35)[0];rec.adb('kernel-journal','journalctl -k -b --no-pager -o short-monotonic',35);scan=p.inspect(raw,state['boot_id'],base,state['uptime_seconds']);assert not scan['fault_counts'] and not scan['suspects']
rec.adb('boot-history','journalctl --list-boots --no-pager',20)
sup=rec.adb('supplies','cat /sys/class/power_supply/sm5714-battery/uevent; cat /sys/class/power_supply/sm5714-usb/uevent',15)[0]; props={line.split('=',1)[0]:line.split('=',1)[1] for line in sup.splitlines() if line.startswith('POWER_SUPPLY_')}
assert props['POWER_SUPPLY_HEALTH']=='Good';assert 100<=int(props['POWER_SUPPLY_TEMP'])<420;assert int(props['POWER_SUPPLY_VOLTAGE_NOW'])<=4440000
ip=rec.adb('wifi-ip',"ip -4 -o addr show wlp1s0",15)[0];wifi=re.search(r'inet ([0-9.]+)/',ip).group(1)
text,status=rec.command('wifi-ssh',['env','GTS9_DEVICE='+wifi,'scripts/gts9-ssh.sh','cat /proc/sys/kernel/random/boot_id'],timeout=18);assert status==0 and p.evidence.canonical_boot_id(text)==state['boot_id']
initial=json.loads((root/'attempt-01/boot/acceptance/summary.json').read_text()); old=initial['before_boot_id']; assert state['boot_id']==initial['boot_id']; assert p.evidence.boot_list((folder/'boot-history.txt').read_text())[-2:]==[old,state['boot_id']]
report=dict(verdict='passed exact candidate final identity and transport acceptance',boot_id=state['boot_id'],before_boot_id=old,config_notes_verified=True,partitions_verified=5,modules_verified=181,rollback_modules_verified=181,dcc_absent=True,failed_units=[],transport=link,kernel_scan=scan,pack_temp_deciC=int(props['POWER_SUPPLY_TEMP']),wifi_ip=wifi,soc=int(props['POWER_SUPPLY_CAPACITY']),voltage_uv=int(props['POWER_SUPPLY_VOLTAGE_NOW']),current_ua=int(props['POWER_SUPPLY_CURRENT_NOW']),input_limit_ua=int(props['POWER_SUPPLY_INPUT_CURRENT_LIMIT']))
notes_raw=rec.adb('notes-base64','base64 /sys/kernel/notes',15)[0]
notes=__import__('base64').b64decode(''.join(notes_raw.split()),validate=True);assert hashlib.sha256(notes).hexdigest()==expected['notes_sha256'];(folder/'kernel-notes.bin').write_bytes(notes)
assert (folder/'cmdline.txt').read_bytes()==(root/'attempt-01/boot/acceptance/cmdline.txt').read_bytes()
rec.adb('module-directories', 'find /usr/lib/modules -maxdepth 1 -type d -print',15)
rec.adb('pstore', 'find /sys/fs/pstore -maxdepth 1 -type f -print',15)
end=rec.adb('end-boot-id','cat /proc/sys/kernel/random/boot_id',15)[0];assert p.evidence.canonical_boot_id(end)==state['boot_id']
report['final_uptime_seconds']=state['uptime_seconds'];report['same_candidate_boot']=True;report['cmdline_unchanged']=True;report['kernel_notes_raw_verified']=True
p.write_json(folder/'summary.json',report);print(json.dumps(report,indent=2))
