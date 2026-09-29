#!/usr/bin/env python3
"""Compare first Debian boot with the registered Test255 candidate and rollback."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_stability_evidence as evidence

A = Path(__file__).resolve().parent
P = A / "postboot"
B = A / "preflight"
NEW = "a5b8b87f1487422a9035a1db74f85667"
OLD = "6c3dde80334e495589169a1e576c8024"
checks = {}


def text(name, root=P):
    return (root / name).read_text(errors="replace")


def check(name, value):
    checks[name] = bool(value)
    if not value:
        print("FAIL", name)


def hashes(path, prefix):
    rows = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (/.+)", line)
        if match:
            rows[match[2].removeprefix(prefix)] = match[1]
    return rows


capture = json.loads(text("capture-status.json"))
check("capture-complete", capture["all_captures_succeeded"])
check("boot-id", evidence.canonical_boot_id(text("boot-id.txt").splitlines()[0]) == NEW and
      evidence.canonical_boot_id(text("final-boot.txt").splitlines()[0]) == NEW)
check("unique-journal-attribution", evidence.attribute(OLD, NEW, text("boots.txt", B),
      text("journal-boots.txt")) == "attributed")
check("config-hash", text("config-hash.txt").split()[0] ==
      "cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f")
check("notes-hash", text("notes-hash.txt").split()[0] ==
      "fb3d249642e900d9bb591fb629c1865b370b50098d44970b986cc793f45c160c")
expected_parts = json.loads(text("summary.json", A / "install"))["partitions"]
check("five-partitions", hashes(P / "partitions.txt", "/dev/disk/by-partlabel/") == expected_parts)
check("unchanged-cmdline", text("cmdline.txt").strip() == text("cmdline.txt", B).strip())

candidate = json.loads((ROOT / "reference/boot-tests/test-255-sm5714-fixed-pd/validation/module-hashes.json").read_text())
current = hashes(P / "modules-current.txt", "/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/")
check("matched-current-modules", len(current) == 181 and current == candidate)
for name, now, before, now_prefix, before_prefix in (
    ("test254-rollback", "modules-test254", "modules-current", ".gts9-test255-original", "7.2.0-rc3-gts9wifi-dirty"),
    ("test252-rollback", "modules-test252", "modules-test252", ".gts9-test254-original", ".gts9-test254-original"),
    ("test249-rollback", "modules-test249", "modules-test249", ".gts9-test252-original", ".gts9-test252-original"),
):
    actual = hashes(P / f"{now}.txt", f"/usr/lib/modules/{now_prefix}/")
    accepted = hashes(B / f"{before}.txt", f"/usr/lib/modules/{before_prefix}/")
    check(name, len(actual) == 181 and actual == accepted)
expected_dirs = {"/usr/lib/modules", "/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty"} | {
    "/usr/lib/modules/.gts9-test255-original", "/usr/lib/modules/.gts9-test254-original",
    "/usr/lib/modules/.gts9-test252-original"}
check("module-directories", set(text("module-directories.txt").splitlines()) == expected_dirs)

check("dcc-absent", "# CONFIG_HVC_DCC is not set" in text("dcc.txt") and "inactive" in text("dcc.txt"))
typec = text("typec.txt")
check("sink-device", "power_role=[sink]" in typec and "data_role=[device]" in typec and
      "port_type=[sink]" in typec)
check("pdic-probed", "SM-X710 fixed5/9V Sink/Device TCPC registered" in text("kernel-journal.txt"))
check("no-systemd-fail", "0 loaded units listed." in text("failed-units.txt"))
check("ncm-wifi-same-boot", all(evidence.canonical_boot_id(text(f"{name}.txt").splitlines()[0]) == NEW
      for name in ("ncm-ssh", "wifi-ssh")))
win_usb = text("windows-usb.txt")
check("windows-usb-no-code43", "ProblemCode  : 43" not in win_usb and
      win_usb.count("ProblemCode  : 0") >= 3)
check("windows-source-bound-ncm", json.loads(text("windows-ncm-banner.txt"))["ok"])
check("test253-adbd-active", "ActiveState=active" in text("test253-adbd.txt") and
      "053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5" in text("test253-adbd.txt"))
scan = json.loads(text("kernel-scan.json"))
check("no-kernel-fault", not scan["fault_counts"] and not scan["suspects"])
check("startup-variants-bounded", scan["startup_variant_counts"] == {
    "boot_register_warning": 1, "smmu_context_fault": 10, "smmu_fsr": 10, "smmu_fsynr": 10})
check("qca-startup-recovered", scan["qca_baudrate_warning"]["state"] == "accepted")
battery = dict(line.split("=", 1) for line in text("battery.txt").splitlines() if "=" in line)
check("battery-safe", battery["health"] == "Good" and int(battery["temp"]) < 450 and
      int(battery["voltage_now"]) <= 4440000)
check("pc-usb-current-limit", "POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000" in text("supplies.txt"))
check("no-sm5440-probe", not re.search(r"(?i)sm5440.*probe", text("kernel-journal.txt")))

result = {"verdict": "passed" if all(checks.values()) else "stopped", "checks": checks,
          "boot_id": NEW, "uptime_seconds": float(text("final-boot.txt").splitlines()[1].split()[0]),
          "kernel_scan": scan, "matched_modules": len(current), "battery": battery,
          "scope": "candidate first boot and PC USB only; unplug/battery/PC reconnect pending; no PD charger"}
(P / "verdict.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(result["verdict"], len(checks), "checks", result["uptime_seconds"], "seconds")
if result["verdict"] != "passed":
    raise SystemExit(1)
