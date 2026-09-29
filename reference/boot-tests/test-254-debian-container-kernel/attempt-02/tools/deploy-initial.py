import sys,json,hashlib,subprocess
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()));import production_reboot_stability as p
p.SERIAL='R52X10045LT'
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-02');reg=json.loads((A/'registration.json').read_text());art=json.loads((A/'packaging/artifacts.json').read_text());r=p.Recorder(A/'deploy')
raw=r.host_adb('recovery-adb-state','devices','-l')[0];assert p.SERIAL in raw and 'recovery' in raw
identity=r.adb('recovery-identity','getprop ro.product.model; getprop ro.twrp.version; uname -a')[0];assert 'SM-X710' in identity and '3.7' in identity
parts=r.adb('partitions-before','set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do blockdev --getsize64 /dev/block/by-name/$n; sha256sum /dev/block/by-name/$n; done',40)[0]
hashrows='\n'.join(x for x in parts.splitlines() if '/dev/block/by-name/' in x);assert p.parse_hashes(hashrows,'/dev/block/by-name/')==reg['original_partitions']
assert parts.splitlines()[0]=='100663296'
r.adb('recovery-supplies','for f in /sys/class/power_supply/*/uevent; do echo "$f"; cat "$f"; done',20)
supply=r.adb('recovery-battery','cat /sys/class/power_supply/battery/uevent')[0]
props=dict(x.split('=',1) for x in supply.splitlines() if x.startswith('POWER_SUPPLY_'));assert props['POWER_SUPPLY_HEALTH']=='Good' and 20<=int(props['POWER_SUPPLY_CAPACITY'])<=100 and 100<=int(props['POWER_SUPPLY_TEMP'])<420 and 3400000<=int(props['POWER_SUPPLY_VOLTAGE_NOW'])<=4440000
for src,dst in [('twrp-mount-debian.sh','mount.sh'),('module-swap.sh','module-swap.sh'),('candidate-module-checksums.txt','candidate-manifest'),('original-module-checksums.txt','original-manifest'),('candidate-modules.tar','candidate-modules.tar'),('candidate-boot.img','candidate-boot.img')]:
    local=Path('/mnt/d/android/gts9-active/gts9-test254')/src
    if src in art['windows_staged']:assert hashlib.sha256(local.read_bytes()).hexdigest()==art['windows_staged'][src]['sha256']
    r.host_adb('push-'+dst,'-s',p.SERIAL,'push','D:/android/gts9-active/gts9-test254/'+src,'/tmp/test254-'+dst,timeout=55)
    got=r.adb('hash-'+dst,'sha256sum /tmp/test254-'+dst,25)[0].split()[0];assert got==hashlib.sha256(local.read_bytes()).hexdigest(),src
r.adb('mount-readonly','sh /tmp/test254-mount.sh',20)
raw=r.adb('root-identity','cat /mnt/debian/etc/machine-id; grep " /mnt/debian " /proc/mounts; busybox blkid /dev/block/mmcblk1p1; find /mnt/debian/usr/lib/modules -maxdepth 1 -type d -print')[0]
assert raw.splitlines()[0]=='3c2a1b8f2d624db4b5ffdc836050fcf6' and '.gts9-test254-' not in raw
assert 'UUID="851819a7-0d96-4217-b64a-aeeee5d8be61"' in raw and '/dev/block/mmcblk1p1 /mnt/debian ext4 ro,' in raw
r.adb('remount-root-rw','umount /mnt/debian && mount -t ext4 -o rw /dev/block/mmcblk1p1 /mnt/debian && test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6 && grep " /mnt/debian " /proc/mounts')
r.adb('install-paired-modules','sh /tmp/test254-module-swap.sh /mnt/debian install /tmp/test254-candidate-manifest /tmp/test254-candidate-modules.tar /tmp/test254-original-manifest',55)
r.adb('write-boot','test "$(blockdev --getsize64 /dev/block/by-name/boot)" = 100663296 && dd if=/tmp/test254-candidate-boot.img of=/dev/block/by-name/boot bs=4M && sync',50)
raw=r.adb('partitions-after','set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done',40)[0]
expected=dict(reg['original_partitions']);expected['boot']=reg['candidate_boot_sha256'];assert p.parse_hashes(raw,'/dev/block/by-name/')==expected
r.adb('clear-bcb-unmount','test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576 && dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc && sync && umount /mnt/debian && dd if=/dev/block/by-name/misc bs=32 count=1 2>/dev/null | od -An -tx1',25)
p.write_json(A/'deploy/summary.json',dict(verdict='boot and matched modules installed/readback verified; not yet booted',boot_sha256=expected['boot'],partition_hashes=expected,modules=181,rollback_directory='/usr/lib/modules/.gts9-test254-original',other_partitions_unchanged=True,rootfs_unmounted=True,temporary_bcb_cleared=True))
print('DEPLOYMENT VERIFIED; reboot command follows',flush=True)
r.host_adb('reboot-system','-s',p.SERIAL,'reboot','system',timeout=15)
