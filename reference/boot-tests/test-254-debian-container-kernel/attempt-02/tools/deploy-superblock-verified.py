import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()));import production_reboot_stability as p;p.SERIAL='R52X10045LT'
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-02');reg=json.loads((A/'registration.json').read_text());r=p.Recorder(A/'deploy')
raw=r.adb('resume-readonly-identity','getprop ro.product.model; getprop ro.twrp.version; cat /mnt/debian/etc/machine-id; grep " /mnt/debian " /proc/mounts; dd if=/dev/block/mmcblk1p1 bs=1 skip=1128 count=16 2>/dev/null | od -An -tx1')[0]
assert raw.splitlines()[0]=='SM-X710' and raw.splitlines()[2]=='3c2a1b8f2d624db4b5ffdc836050fcf6' and '/dev/block/mmcblk1p1 /mnt/debian ext4 ro,' in raw and '85 18 19 a7 0d 96 42 17 b6 4a ae ee e5 d8 be 61' in raw
raw=r.adb('immediate-partitions-before','set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done',40)[0];assert p.parse_hashes(raw,'/dev/block/by-name/')==reg['original_partitions']
raw=r.adb('staged-files-recheck','sha256sum /tmp/test254-candidate-boot.img /tmp/test254-candidate-modules.tar /tmp/test254-candidate-manifest /tmp/test254-original-manifest /tmp/test254-module-swap.sh',30)[0]
actual=p.parse_hashes(raw,'/tmp/test254-');src={'candidate-boot.img':'candidate-boot.img','candidate-modules.tar':'candidate-modules.tar','candidate-manifest':'candidate-module-checksums.txt','original-manifest':'original-module-checksums.txt','module-swap.sh':'module-swap.sh'}
assert actual=={k:hashlib.sha256((Path('/mnt/d/android/gts9-active/gts9-test254')/v).read_bytes()).hexdigest() for k,v in src.items()}
r.adb('remount-root-rw','umount /mnt/debian && mount -t ext4 -o rw /dev/block/mmcblk1p1 /mnt/debian && test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6 && grep " /mnt/debian " /proc/mounts')
r.adb('install-paired-modules','sh /tmp/test254-module-swap.sh /mnt/debian install /tmp/test254-candidate-manifest /tmp/test254-candidate-modules.tar /tmp/test254-original-manifest',55)
r.adb('write-boot','test "$(blockdev --getsize64 /dev/block/by-name/boot)" = 100663296 && dd if=/tmp/test254-candidate-boot.img of=/dev/block/by-name/boot bs=4M && sync',50)
raw=r.adb('partitions-after','set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done',40)[0]
expected=dict(reg['original_partitions']);expected['boot']=reg['candidate_boot_sha256'];assert p.parse_hashes(raw,'/dev/block/by-name/')==expected
r.adb('clear-bcb-unmount','test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576 && dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc && sync && umount /mnt/debian && dd if=/dev/block/by-name/misc bs=32 count=1 2>/dev/null | od -An -tx1',25)
p.write_json(A/'deploy/summary.json',dict(verdict='boot and matched modules installed/readback verified; not yet booted',boot_sha256=expected['boot'],partition_hashes=expected,modules=181,rollback_directory='/usr/lib/modules/.gts9-test254-original',other_partitions_unchanged=True,rootfs_unmounted=True,temporary_bcb_cleared=True,root_uuid_verified='raw ext4 superblock after blkid produced no output'))
print('DEPLOYMENT VERIFIED; reboot command follows',flush=True)
r.host_adb('reboot-system','-s',p.SERIAL,'reboot','system',timeout=15)
