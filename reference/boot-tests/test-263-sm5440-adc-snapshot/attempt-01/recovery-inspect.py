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
STAGE = Path("/mnt/d/android/gts9-active/gts9-test263")
WIN = "D:/android/gts9-active/gts9-test263"
BASE = json.loads((A / "preflight/summary.json").read_text())
SEALED = json.loads((A / "STAGED_FILES.json").read_text())
p.SERIAL = "R52X10045LT"
r = p.Recorder(A / "recovery-inspect")

raw = r.host_adb("recovery-adb", "devices", "-l")[0]
assert p.SERIAL in raw and "recovery" in raw
raw = r.adb("recovery-identity", "getprop ro.product.model; getprop ro.twrp.version; uname -a; cat /proc/sys/kernel/random/boot_id", 20)[0]
assert raw.splitlines()[0] == "SM-X710" and raw.splitlines()[1].startswith("3.7")
recovery_boot_id = p.evidence.canonical_boot_id(raw.splitlines()[3])
raw = r.adb("partitions-before", "set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do blockdev --getsize64 /dev/block/by-name/$n; sha256sum /dev/block/by-name/$n; done", 70)[0]
assert p.parse_hashes("\n".join(x for x in raw.splitlines() if "/dev/block/by-name/" in x), "/dev/block/by-name/") == BASE["partitions"]
assert [int(x) for x in raw.splitlines() if x.isdigit()] == [
    100663296, 100663296, 8388608, 16777216, 131072,
]
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
    "rollback-test260-boot.img": "rollback-test260-boot.img",
    "rollback-test260-vendor_boot.img": "rollback-test260-vendor_boot.img",
    "test260-rollback-modules.sha256": "test260-rollback-modules.sha256",
    "test263-candidate-modules.sha256": "test263-candidate-modules.sha256",
    "module-swap.sh": "module-swap.sh",
    "twrp-mount-debian.sh": "twrp-mount-debian.sh",
}
expected = {
    "candidate-boot.img": 'cc31efa00efa6ae2e27b2229c584ccaba9541d398366c87a0ac0ee344f2237e6',
    "candidate-vendor_boot.img": 'efddf31cfac5da0fab55b44029629155076977cb2d7695a384d446dd4b5ad0d1',
    "candidate-modules.tar.gz": 'a50b498c21985bd25cde7cc33f2cf4c498ab17b64590225d25f5f909e4e2bef6',
    "rollback-test260-boot.img": BASE["partitions"]["boot"],
    "rollback-test260-vendor_boot.img": BASE["partitions"]["vendor_boot"],
}
for local, remote in files.items():
    local_path = Path("/mnt/d/android/gts9-active/gts9-test263/module-swap.sh") if local == "module-swap.sh" else STAGE / local
    data = local_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == SEALED[local]["sha256"], local
    if local in expected:
        assert digest == expected[local], local
    r.host_adb("push-" + local.replace(".", "-"), "-s", p.SERIAL, "push", ("D:/android/gts9-active/gts9-test263/module-swap.sh" if local == "module-swap.sh" else WIN + "/" + local), "/tmp/test263-a01-" + remote, timeout=75)
    got = r.adb("hash-" + local.replace(".", "-"), "sha256sum /tmp/test263-a01-" + remote, 30)[0].split()[0]
    assert got == digest, local

r.adb("mount-readonly", "sh /tmp/test263-a01-twrp-mount-debian.sh", 25)
raw = r.adb("root-identity", "cat /mnt/debian/etc/machine-id; grep ' /mnt/debian ' /proc/mounts; dd if=/dev/block/mmcblk1p1 bs=1 skip=1128 count=16 2>/dev/null | od -An -tx1; find /mnt/debian/usr/lib/modules -maxdepth 1 -type d -print", 25)[0]
assert raw.splitlines()[0] == "3c2a1b8f2d624db4b5ffdc836050fcf6"
assert "/dev/block/mmcblk1p1 /mnt/debian ext4 ro," in raw
assert "85 18 19 a7 0d 96 42 17 b6 4a ae ee e5 d8 be 61" in raw
assert ".gts9-test263-original" not in raw and ".gts9-test263-stage" not in raw
raw = r.adb("verify-current-modules", "cd /mnt/debian/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty && sha256sum -c /tmp/test263-a01-test260-rollback-modules.sha256", 65)[0]
assert len([x for x in raw.splitlines() if x.endswith(": OK")]) == 181
r.adb("recovery-pstore", "for f in /sys/fs/pstore/*; do test -f \"$f\" && { echo \"$f\"; cat \"$f\"; }; done", 20, required=False)
r.adb("recovery-dmesg", "dmesg", 25)
p.write_json(A / "recovery-inspect/summary.json", {"verdict": "TWRP identity, five partitions, root and 181 current modules verified; staged files hash-verified; no partition/rootfs write yet", "battery_capacity": int(props["POWER_SUPPLY_CAPACITY"]), "battery_temp_deciC": int(props["POWER_SUPPLY_TEMP"]), "partition_hashes": BASE["partitions"], "recovery_boot_id": recovery_boot_id})
print("Recovery inspection and staging passed; no permanent write", flush=True)
