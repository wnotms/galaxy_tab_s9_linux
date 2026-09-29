#!/usr/bin/env python3
"""Read-only, stop-on-first-failure 150-second PC USB observation."""

import datetime
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as capture
import production_stability_evidence as evidence

A = Path(__file__).resolve().parent
BOOT = "d745248e6a164243b9ccc5e6ede21fb2"
WIFI = "10.191.121.37"
capture.SERIAL = "gts9wifi-0001"
r = capture.Recorder(A / "pc-window")
assert json.loads((A / "preflight/verdict.json").read_text())["verdict"] == "passed"
assert json.loads((A / "charging/summary.json").read_text())["verdict"] == "bounded-battery-telemetry-passed"
assert json.loads((A / "unplug/summary.json").read_text())["verdict"] == "passed"
reference = ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt"
known = {x["MESSAGE"] for x in map(json.loads, reference.read_text().splitlines())
         if int(x.get("PRIORITY", 7)) <= 3}
started = time.monotonic()
started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
samples = []


def same_boot(raw):
    if evidence.canonical_boot_id(raw.splitlines()[0]) != BOOT:
        raise RuntimeError("boot ID changed during observation")


try:
    while True:
        index = len(samples)
        prefix = f"sample-{index:02}-"
        sample_time = time.monotonic()
        state = r.adb(prefix + "state", "set -e; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/class/typec/port0/power_role /sys/class/typec/port0/data_role; cat /sys/class/power_supply/sm5714-battery/uevent; cat /sys/class/power_supply/sm5714-usb/uevent", 15)[0]
        same_boot(state)
        uptime = float(state.splitlines()[1].split()[0])
        if "[sink]" not in state or "[device]" not in state:
            raise RuntimeError("Type-C role changed")
        if "POWER_SUPPLY_ONLINE=1" not in state or "[SDP]" not in state:
            raise RuntimeError("PC USB supply state changed")
        if "POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000" not in state:
            raise RuntimeError("unexpected PC input-current limit")
        temp = int(re.search(r"POWER_SUPPLY_TEMP=(\d+)", state)[1])
        voltage = int(re.search(r"POWER_SUPPLY_VOLTAGE_NOW=(\d+)", state)[1])
        current = int(re.search(r"POWER_SUPPLY_CURRENT_NOW=(-?\d+)", state)[1])
        if temp >= 450 or voltage > 4440000 or "POWER_SUPPLY_HEALTH=Good" not in state:
            raise RuntimeError("battery safety gate failed")
        ncm = r.ssh(prefix + "ncm-ssh", "cat /proc/sys/kernel/random/boot_id", 15)[0]
        wifi = r.command(prefix + "wifi-ssh", ["env", f"GTS9_DEVICE={WIFI}", capture.SSH,
                         "cat /proc/sys/kernel/random/boot_id"], timeout=15)[0]
        same_boot(ncm)
        same_boot(wifi)
        win = r.ps(prefix + "windows-usb", capture.PS_USB, timeout=30)[0]
        if capture.has_code43(win) or win.count("ProblemCode  : 0") < 3:
            raise RuntimeError("Windows USB PnP/Code43 gate failed")
        banner = r.ps(prefix + "ncm-banner", capture.PS_NCM_BOUND_BANNER, timeout=35)[0]
        if not json.loads(banner)["ok"]:
            raise RuntimeError("Windows NCM banner failed")
        journal = r.adb(prefix + "kernel-json", "journalctl -b -k --no-pager -o json", 40)[0]
        scan = evidence.inspect_journal(journal, BOOT, known, accepted_startup_variants=True,
                                        startup_iova_range=(0xb8000000, 0xbab00000),
                                        accepted_qca_cycles=True, observed_uptime=uptime)
        capture.write_json(r.folder / (prefix + "kernel-scan.json"), scan)
        if scan["fault_counts"] or scan["suspects"]:
            raise RuntimeError("kernel fault or suspect acquired during observation")
        failed = r.adb(prefix + "failed-units", "systemctl --failed --no-pager --plain", 15)[0]
        if "0 loaded units listed." not in failed:
            raise RuntimeError("systemd failed unit acquired during observation")
        samples.append({"index": index, "elapsed_seconds": round(sample_time - started, 3),
                        "uptime_seconds": uptime, "temp_deciC": temp, "vbat_uv": voltage,
                        "ibat_ua": current, "adb": True, "ncm": True, "wifi": True,
                        "code43": False, "kernel_fault_counts": scan["fault_counts"]})
        capture.write_json(r.folder / "samples.json", samples)
        if sample_time - started >= 150:
            break
        time.sleep(10)
    result = {"verdict": "passed", "boot_id": BOOT, "start_utc": started_utc,
              "observation_seconds": round(sample_time - started, 3), "samples": len(samples),
              "temperatures_deciC": [x["temp_deciC"] for x in samples],
              "device_writes": False, "first_non_clean_sample": None,
              "scope": "PC USB after direct PD charger and battery-only window on the same candidate boot"}
except Exception as exc:
    result = {"verdict": "stopped", "boot_id": BOOT, "start_utc": started_utc,
              "error": str(exc), "completed_samples": len(samples), "device_writes": False}
    capture.write_json(r.folder / "summary.json", result)
    raise
capture.write_json(r.folder / "summary.json", result)
print("PC USB observation passed:", result["observation_seconds"], "seconds", flush=True)
