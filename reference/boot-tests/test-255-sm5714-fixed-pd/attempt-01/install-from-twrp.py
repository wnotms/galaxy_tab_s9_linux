#!/usr/bin/env python3
"""Install only the staged Test255 boot, vendor_boot and matched modules.

Run once after recovery-inspect has passed and its evidence has been pushed.
On any failed gate, leave the tablet in TWRP for inspection; never auto-reboot.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as p

A = Path(__file__).resolve().parent
STAGE = Path("/mnt/d/android/gts9-active/gts9-test255")
BASE = json.loads((ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/summary.json").read_text())
INSPECT = json.loads((A / "recovery-inspect/summary.json").read_text())
assert INSPECT["verdict"].startswith("TWRP identity")

head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
remote = subprocess.check_output(["git", "rev-parse", "origin/test"], cwd=ROOT).strip()
assert head == remote, "push inspection evidence before device writes"
assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()

expected_files = {
    "candidate-boot.img": "26ef6bd143a9575b997b8cf73f24686d647f1ac742f0e7d92d44aa600ef7c063",
    "candidate-vendor_boot.img": "d80d03cdf0ac810d9ac741074a9b97327c48880a98a4459db219ed7813461a46",
    "candidate-modules.tar.gz": "28e33cda7814686ee32b480c0b0cf4f02952cdc89d19ad7af37feb47e79edf1c",
    "rollback-test254-boot.img": BASE["partitions"]["boot"],
    "rollback-test254-vendor_boot.img": BASE["partitions"]["vendor_boot"],
    "test254-rollback-modules.sha256": None,
    "test255-candidate-modules.sha256": None,
    "module-swap.sh": None,
}
for filename, digest in expected_files.items():
    local = hashlib.sha256((STAGE / filename).read_bytes()).hexdigest()
    assert digest is None or local == digest, filename
    expected_files[filename] = local

p.SERIAL = "R52X10045LT"
r = p.Recorder(A / "install")
raw = r.host_adb("recovery-adb", "devices", "-l")[0]
assert p.SERIAL in raw and "recovery" in raw
raw = r.adb("immediate-partitions", "set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done", 70)[0]
assert p.parse_hashes(raw, "/dev/block/by-name/") == BASE["partitions"]
raw = r.adb("immediate-root", "set -e; cat /mnt/debian/etc/machine-id; grep ' /mnt/debian ' /proc/mounts; test ! -e /mnt/debian/usr/lib/modules/.gts9-test255-original; test ! -e /mnt/debian/usr/lib/modules/.gts9-test255-stage", 15)[0]
assert raw.splitlines()[0] == "3c2a1b8f2d624db4b5ffdc836050fcf6"
assert "/dev/block/mmcblk1p1 /mnt/debian ext4 ro," in raw
raw = r.adb("staged-hashes", "set -e; sha256sum " + " ".join("/tmp/test255-" + k for k in expected_files), 55)[0]
assert p.parse_hashes(raw, "/tmp/test255-") == expected_files
raw = r.adb("staged-sizes", "df -h /tmp; for n in boot vendor_boot; do blockdev --getsize64 /dev/block/by-name/$n; done", 15)[0]
assert raw.splitlines()[-2:] == ["100663296", "100663296"]

# The first permanent change follows. Each command is captured before the next
# step; a failure leaves TWRP active and requires explicit evidence review.
raw = r.adb("remount-root-rw", "set -e; umount /mnt/debian; mount -t ext4 -o rw /dev/block/mmcblk1p1 /mnt/debian; test \"$(cat /mnt/debian/etc/machine-id)\" = 3c2a1b8f2d624db4b5ffdc836050fcf6; grep ' /mnt/debian ' /proc/mounts", 25)[0]
assert "/dev/block/mmcblk1p1 /mnt/debian ext4 rw," in raw
r.adb("install-paired-modules", "sh /tmp/test255-module-swap.sh /mnt/debian install /tmp/test255-test255-candidate-modules.sha256 /tmp/test255-candidate-modules.tar.gz /tmp/test255-test254-rollback-modules.sha256", 120)
raw = r.adb("verify-rollback-modules", "cd /mnt/debian/usr/lib/modules/.gts9-test255-original && sha256sum -c /tmp/test255-test254-rollback-modules.sha256", 65)[0]
assert len([x for x in raw.splitlines() if x.endswith(": OK")]) == 181
r.adb("write-boot", "set -e; test \"$(blockdev --getsize64 /dev/block/by-name/boot)\" = 100663296; dd if=/tmp/test255-candidate-boot.img of=/dev/block/by-name/boot bs=4M; sync", 70)
r.adb("write-vendor-boot", "set -e; test \"$(blockdev --getsize64 /dev/block/by-name/vendor_boot)\" = 100663296; dd if=/tmp/test255-candidate-vendor_boot.img of=/dev/block/by-name/vendor_boot bs=4M; sync", 70)
raw = r.adb("partitions-after", "set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done", 75)[0]
expected = dict(BASE["partitions"])
expected["boot"] = expected_files["candidate-boot.img"]
expected["vendor_boot"] = expected_files["candidate-vendor_boot.img"]
assert p.parse_hashes(raw, "/dev/block/by-name/") == expected
r.adb("clear-bcb-unmount", "set -e; test \"$(blockdev --getsize64 /dev/block/by-name/misc)\" = 1048576; dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc; sync; umount /mnt/debian; dd if=/dev/block/by-name/misc bs=32 count=1 2>/dev/null | od -An -tx1", 40)
p.write_json(A / "install/summary.json", {"verdict": "candidate boot/vendor_boot and 181 matched modules installed with readback; TWRP remains before reboot", "partitions": expected, "rollback_modules": "/usr/lib/modules/.gts9-test255-original", "older_backups_untouched": True, "root_unmounted": True, "bcb_cleared": True})
print("Install/readback passed. TWRP remains active; commit/push evidence before system boot.", flush=True)
