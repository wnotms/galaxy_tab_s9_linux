import sys,json,hashlib,shutil,subprocess
from pathlib import Path
sys.path.insert(0,'scripts');import production_reboot_stability as p
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-03');reg=json.loads((A/'registration.json').read_text());r=p.Recorder(A/'image-load')
assert subprocess.check_output(['git','rev-parse','HEAD']).strip()==subprocess.check_output(['git','rev-parse','origin/test']).strip()
raw=r.adb('same-boot-before','cat /proc/sys/kernel/random/boot_id; systemctl show gts9-adbd.service -p MainPID --value')[0].splitlines();assert p.evidence.canonical_boot_id(raw[0])==reg['boot_id'] and int(raw[1])==reg['daemon_pid']
W=Path('/mnt/d/android/gts9-active/gts9-test254')
for meta in reg['images']:
    src=Path(meta['archive']);name=src.name;assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256'];shutil.copy2(src,W/name)
    r.host_adb('push-'+name,'-s',p.SERIAL,'push','D:/android/gts9-active/gts9-test254/'+name,'/tmp/test254-'+name,timeout=55)
    raw=r.adb('hash-'+name,'sha256sum /tmp/test254-'+name,30)[0];assert raw.split()[0]==meta['sha256']
    r.adb('load-'+name,'docker load -i /tmp/test254-'+name,55)
    raw=r.adb('inspect-'+name,'docker image inspect '+meta['image']+' --format "{{json .}}"',20)[0];info=json.loads(raw);assert info['Id']==meta['image_id'] and info['Architecture']=='arm64' and info['Os']=='linux'
    print('DEVICE IMAGE VERIFIED',meta['image'],info['Id'],flush=True)
    r.adb('remove-temp-'+name,'rm /tmp/test254-'+name)
p.write_json(A/'image-load/summary.json',dict(verdict='passed all four exact ARM64 config/archive identities',images=reg['images'],device_registry_pull_proven=False,daemon_config_changed=False))
