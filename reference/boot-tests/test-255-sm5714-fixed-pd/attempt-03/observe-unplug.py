#!/usr/bin/env python3
"""Read-only host capture of the already registered charger-unplug window."""

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as capture
import production_stability_evidence as evidence
import sm5714_pd_telemetry as telemetry

A = Path(__file__).resolve().parent
BOOT = "d745248e6a164243b9ccc5e6ede21fb2"
WIFI = "10.191.121.37"
assert json.loads((A / "charging/summary.json").read_text())["verdict"] == "bounded-battery-telemetry-passed"
folder = A / "unplug"
if folder.exists():
    raise SystemExit("refusing to reuse an evidence directory")
r = capture.Recorder(folder)
argv = ["env", "GTS9_DEVICE=" + WIFI, capture.SSH]
baseline = ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt"
known = {x["MESSAGE"] for x in map(json.loads, baseline.read_text().splitlines())
         if int(x.get("PRIORITY", 7)) <= 3}
samples = []
start = time.monotonic()
window = offline = last_journal = None
try:
    while True:
        now = time.monotonic()
        prefix = f"sample-{len(samples):04}-"
        raw = r.command(prefix + "telemetry", argv + [telemetry.SAMPLE_COMMAND], timeout=12)[0]
        sample = telemetry.parse_sample(raw)
        reason = telemetry.assess(sample, BOOT, samples)
        sample["elapsed_seconds"] = round(now - start, 3)
        samples.append(sample)
        capture.write_json(folder / "samples.json", samples)
        if reason:
            raise RuntimeError(reason)
        detached = not sample["usb_online"] and not sample["tcpm_online"]
        discharging = detached and sample["battery_status"] == "Discharging" and sample["battery_current_ua"] < 0
        if detached and offline is None:
            offline = now
        if discharging and window is None:
            window = now
            print("BATTERY_ONLY_WINDOW_STARTED", flush=True)
        if window is not None and not discharging:
            raise RuntimeError("battery-only-window-interrupted")
        if offline is not None and window is None and now - offline > 15:
            raise RuntimeError("discharge-not-established-within-15s")
        if window is None and now - start > 600:
            raise RuntimeError("charger-not-unplugged-within-600s")
        if last_journal is None or now - last_journal >= 30:
            journal = r.command(prefix + "kernel-json", argv + ["journalctl -b -k --no-pager -o json"], timeout=35)[0]
            scan = evidence.inspect_journal(journal, BOOT, known, accepted_startup_variants=True,
                    startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True,
                    observed_uptime=sample["uptime_seconds"])
            capture.write_json(folder / (prefix + "kernel-scan.json"), scan)
            if scan["fault_counts"] or scan["suspects"]:
                raise RuntimeError("kernel-fault-or-suspect")
            failed = r.command(prefix + "failed-units", argv + ["systemctl --failed --no-pager --plain"], timeout=15)[0]
            if "0 loaded units listed." not in failed:
                raise RuntimeError("systemd-failed-unit")
            last_journal = now
        if window is not None and now - window >= 150:
            result = {"verdict": "passed", "boot_id": BOOT, "observation_seconds": round(now - window, 3),
                      "first_discharge_elapsed_seconds": round(window - start, 3),
                      "last_sample": sample, "device_writes": False}
            break
        time.sleep(max(.05, 5 - (time.monotonic() - now)))
except Exception as exc:
    capture.write_json(folder / "summary.json", {"verdict": "stopped", "error": str(exc),
                       "boot_id": BOOT, "device_writes": False})
    raise
capture.write_json(folder / "summary.json", result)
print("BATTERY_ONLY_150S_PASSED", flush=True)
