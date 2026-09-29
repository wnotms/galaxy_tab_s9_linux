#!/usr/bin/env python3
"""Read-only TWRP identity and staged-file inspection; no partition/rootfs write."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as p

A = Path(__file__).resolve().parent
STAGE = Path("/mnt/d/android/gts9-active/gts9-test255")
WIN = "D:/android/gts9-active/gts9-test255"
BASE = json.loads((ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/summary.json").read_text())
p.SERIAL = "R52X10045LT"
r = p.Recorder(A / "recovery-inspect")

raw = r.host_adb("recovery-adb", "devices", "-l")[0]
assert p.SERIAL in raw and "recovery" in raw
raw = r.adb("recovery-identity", "getprop ro.product.model; getprop ro.twrp.version; uname -a", 20)[0]
assert raw.splitlines()[0] == "SM-X710" and raw.splitlines()[1].startswith("3.7")
raw = r.adb("partitions-before", "set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do blockdev --getsize64 /dev/block/by-name/$n; sha256sum /dev/block/by-name/$n; done", 70)[0]
assert p.parse_hashes("\n".join(x for x in raw.splitlines() if "/dev/block/by-name/" in x), "/dev/block/by-name/") == BASE["partitions"]
assert all(x == "100663296" for x in raw.splitlines() if x.isdigit())
r.adb("recovery-supplies", 'for f in /sys/class/power_supply/*/uevent; do echo "$f"; cat "$f"; done', 20)
raw = r.adb("recovery-battery", "cat /sys/class/power_supply/battery/uevent", 15)[0]
props = dict(x.split("=", 1) for x in raw.splitlines() if x.startswith("POWER_SUPPLY_"))
assert props["POWER_SUPPLY_HEALTH"] == "Good"
assert 20 <= int(props["POWER_SUPPLY_CAPACITY"]) <= 100
assert 100 <= int(props["POWER_SUPPLY_TEMP"]) < 420
assert 3400000 <= int(props["POWER_SUPPLY_VOLTAGE_NOW"]) <= 4440000

files = {
    "candidate-boot.img": "candidate-boot.img",
    "candidate-vendor_boot.img": "candidate-vendor_boot.img",
    "candidate-modules.tar.gz": "candidate-modules.tar.gz",
    "rollback-test254-boot.img": "rollback-test254-boot.img",
    "rollback-test254-vendor_boot.img": "rollback-test254-vendor_boot.img",
    "test254-rollback-modules.sha256": "test254-rollback-modules.sha256",
    "test255-candidate-modules.sha256": "test255-candidate-modules.sha256",
    "module-swap.sh": "module-swap.sh",
    "twrp-mount-debian.sh": "twrp-mount-debian.sh",
}
expected = {
    "candidate-boot.img": "26ef6bd143a9575b997b8cf73f24686d647f1ac742f0e7d92d44aa600ef7c063",
    "candidate-vendor_boot.img": "d80d03cdf0ac810d9ac741074a9b97327c48880a98a4459db219ed7813461a46",
    "candidate-modules.tar.gz": "28e33cda7814686ee32b480c0b0cf4f02952cdc89d19ad7af37feb47e79edf1c",
    "rollback-test254-boot.img": BASE["partitions"]["boot"],
    "rollback-test254-vendor_boot.img": BASE["partitions"]["vendor_boot"],
}
for local, remote in files.items():
    data = (STAGE / local).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if local in expected:
        assert digest == expected[local], local
    r.host_adb("push-" + local.replace(".", "-"), "-s", p.SERIAL, "push", WIN + "/" + local, "/tmp/test255-" + remote, timeout=75)
    got = r.adb("hash-" + local.replace(".", "-"), "sha256sum /tmp/test255-" + remote, 30)[0].split()[0]
    assert got == digest, local

r.adb("mount-readonly", "sh /tmp/test255-twrp-mount-debian.sh", 25)
raw = r.adb("root-identity", "cat /mnt/debian/etc/machine-id; grep ' /mnt/debian ' /proc/mounts; dd if=/dev/block/mmcblk1p1 bs=1 skip=1128 count=16 2>/dev/null | od -An -tx1; find /mnt/debian/usr/lib/modules -maxdepth 1 -type d -print", 25)[0]
assert raw.splitlines()[0] == "3c2a1b8f2d624db4b5ffdc836050fcf6"
assert "/dev/block/mmcblk1p1 /mnt/debian ext4 ro," in raw
assert "85 18 19 a7 0d 96 42 17 b6 4a ae ee e5 d8 be 61" in raw
assert ".gts9-test255-original" not in raw and ".gts9-test255-stage" not in raw
raw = r.adb("verify-current-modules", "cd /mnt/debian/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty && sha256sum -c /tmp/test255-test254-rollback-modules.sha256", 65)[0]
assert len([x for x in raw.splitlines() if x.endswith(": OK")]) == 181
r.adb("recovery-pstore", "for f in /sys/fs/pstore/*; do test -f \"$f\" && { echo \"$f\"; cat \"$f\"; }; done", 20, required=False)
r.adb("recovery-dmesg", "dmesg", 25)
p.write_json(A / "recovery-inspect/summary.json", {"verdict": "TWRP identity, five partitions, root and 181 current modules verified; staged files hash-verified; no partition/rootfs write yet", "battery_capacity": int(props["POWER_SUPPLY_CAPACITY"]), "battery_temp_deciC": int(props["POWER_SUPPLY_TEMP"]), "partition_hashes": BASE["partitions"]})
print("Recovery inspection and staging passed; no permanent write", flush=True)
