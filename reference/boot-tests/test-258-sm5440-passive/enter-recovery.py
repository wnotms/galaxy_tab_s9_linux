#!/usr/bin/env python3
"""Enter TWRP from the exact Test255 boot via the established BCB helper."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as p

A = Path(__file__).resolve().parent
STAGE = Path("/mnt/d/android/gts9-active/gts9-test258")
WIN = "D:/android/gts9-active/gts9-test258"
BASE = json.loads((A / "normal-preflight/summary.json").read_text())
p.SERIAL = "gts9wifi-0001"
r = p.Recorder(A / "enter-recovery")

head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
remote = subprocess.check_output(["git", "rev-parse", "origin/test"], cwd=ROOT).strip()
assert head == remote, "push exact deployment registration before maintenance"
assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()
assert all(BASE["checks"].values()), "fresh normal baseline must pass"

raw = r.adb("immediate-identity", "set -e; cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; cat /sys/class/power_supply/sm5714-battery/uevent", 30)[0]
lines = raw.splitlines()
assert p.evidence.canonical_boot_id(lines[0]) == BASE["boot_id"]
assert lines[1].split()[0] == BASE["config_sha256"]
assert lines[2].split()[0] == BASE["notes_sha256"]
props = dict(x.split("=", 1) for x in lines[3:] if x.startswith("POWER_SUPPLY_"))
assert props["POWER_SUPPLY_HEALTH"] == "Good" and props["POWER_SUPPLY_PRESENT"] == "1"
assert 5 <= int(props["POWER_SUPPLY_CAPACITY"]) < 80
assert 200 <= int(props["POWER_SUPPLY_TEMP"]) < 380
assert 3500000 <= int(props["POWER_SUPPLY_VOLTAGE_NOW"]) < 4300000
# Five-partition hashes were captured on this same baseline boot. The next
# partition gate is at the TWRP write boundary; no write occurred in between.

helper = ROOT / "boot/gts9-debian-to-recovery.sh"
assert hashlib.sha256((STAGE / helper.name).read_bytes()).digest() == hashlib.sha256(helper.read_bytes()).digest()
r.host_adb("push-helper", "-s", p.SERIAL, "push", WIN + "/" + helper.name, "/tmp/test258-to-recovery.sh", timeout=25)
remote_hash = r.adb("helper-hash", "sha256sum /tmp/test258-to-recovery.sh")[0].split()[0]
assert remote_hash == hashlib.sha256(helper.read_bytes()).hexdigest()
assert "(empty, boots mainline)" in r.adb("bcb-check", "TMPDIR=/tmp sh /tmp/test258-to-recovery.sh --check")[0]
r.adb("bcb-request", "TMPDIR=/tmp sh /tmp/test258-to-recovery.sh --yes --no-reboot", 25)
r.adb("plain-reboot", "systemctl reboot", 20, required=False)

start = time.monotonic()
for n in range(45):
    raw, _ = r.host_adb(f"wait-recovery-{n:02}", "devices", "-l", timeout=8, required=False)
    if "R52X10045LT" in raw and "recovery" in raw:
        p.write_json(A / "enter-recovery/summary.json", {"verdict": "TWRP observed; no boot/vendor/module write yet", "seconds": round(time.monotonic() - start, 3), "previous_boot_id": BASE["boot_id"]})
        print("TWRP available after", round(time.monotonic() - start, 1), "seconds", flush=True)
        break
    time.sleep(2)
else:
    raise RuntimeError("TWRP not observed within bounded wait; no image write")
