#!/usr/bin/env python3
"""Read-only bounded charger-to-PC recovery using Test253 pure cable checks."""
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as capture
import production_stability_evidence as evidence
from adbd_cable_evidence import CableCycle, review_adbd

A = Path(__file__).resolve().parent
assert json.loads((A / "unplug/summary.json").read_text())["verdict"] == "passed"
legacy = runpy.run_path(str(ROOT / "scripts/adbd-cable-observer.py"))
BOOT = "d745248e6a164243b9ccc5e6ede21fb2"
PID = 827
SHA = "053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5"
capture.SERIAL = "gts9wifi-0001"
folder = A / "pc-recovery"
if folder.exists():
    raise SystemExit("refusing to reuse an evidence directory")
r = capture.Recorder(folder)
wifi = ["env", "GTS9_DEVICE=10.191.121.37", capture.SSH]
cycle = CableCycle(BOOT, PID, SHA)
ready = False
floor = None
samples = []
start = time.monotonic()
known_path = ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt"
known = {x["MESSAGE"] for x in map(json.loads, known_path.read_text().splitlines()) if int(x.get("PRIORITY", 7)) <= 3}
try:
    while True:
        begun = time.monotonic()
        prefix = f"sample-{len(samples):03}-"
        snapshot = legacy["parse_snapshot"](r.command(prefix + "wifi-state", wifi + [legacy["SNAPSHOT"]], timeout=12)[0])
        if floor is None:
            floor = snapshot["uptime"]
        native_table = r.host_adb(prefix + "adb-devices", "devices", "-l", timeout=8)[0]
        cycle.sample(online=snapshot["online"], native_seen=capture.SERIAL in native_table,
                     started=begun, ended=time.monotonic(), uptime=snapshot["uptime"],
                     boot=snapshot["boot"], pid=snapshot["pid"], sha256=snapshot["sha256"],
                     udc_binding=snapshot["udc_binding"], udc_state=snapshot["udc_state"])
        samples.append(dict(snapshot, elapsed_seconds=round(begun-start, 3)))
        capture.write_json(folder / "samples.json", samples)
        if cycle.first_off_end is not None and cycle.last_off_start-cycle.first_off_end >= 10 and not ready:
            ready = True
            print("READY: reconnect computer USB once; no charger or reboot", flush=True)
        if cycle.return_seen:
            pnp = r.ps(prefix + "windows-usb", capture.PS_USB, timeout=30)[0]
            if capture.has_code43(pnp):
                raise RuntimeError("Windows-Code43")
            native, ns = r.adb(prefix + "native-shell", "cat /proc/sys/kernel/random/boot_id; systemctl show -p MainPID --value gts9-adbd.service; sha256sum /proc/827/exe", timeout=8, required=False)
            ncm, ss = r.ssh(prefix + "ncm-ssh", "cat /proc/sys/kernel/random/boot_id", timeout=8, required=False)
            if ns == 0 and ss == 0:
                nb, np, nh = legacy["native_identity"](native)
                r.ps(prefix + "ncm-banner", capture.PS_NCM_BOUND_BANNER, timeout=30)
                bound = cycle.recovered(native_boot=nb, native_pid=np, native_sha256=nh, ncm_boot=ncm.strip(), now=time.monotonic())
                journal = r.command(prefix + "kernel-json", wifi + ["journalctl -b -k --no-pager -o json"], timeout=35)[0]
                scan = evidence.inspect_journal(journal, BOOT, known, accepted_startup_variants=True,
                    startup_iova_range=(0xb8000000, 0xbab00000), accepted_qca_cycles=True, observed_uptime=snapshot["uptime"])
                capture.write_json(folder / "kernel-scan.json", scan)
                if scan["fault_counts"] or scan["suspects"]:
                    raise RuntimeError("kernel-fault-or-suspect")
                daemon = r.command(prefix + "adbd-json", wifi + ["journalctl -b -u gts9-adbd.service --no-pager -o json"], timeout=25)[0]
                review = review_adbd(daemon, expected_boot=BOOT, expected_pid=PID, source_floor=floor,
                    allow_pre_enable_disable=True, warning_source_range=(cycle.last_off_uptime, cycle.return_uptime+5))
                result = {"verdict": "passed", "boot_id": BOOT, "daemon_pid": PID,
                          "recovery_upper_bound_seconds": round(bound, 3), "adbd_review": review,
                          "transient_failed_commands": [str(p.name) for p in folder.glob('*.command.json') if json.loads(p.read_text())["status"] != 0],
                          "device_writes": False, "host_server_restarts": 0}
                break
            if time.monotonic()-cycle.last_off_start > 60:
                raise RuntimeError("60s-ADB-NCM-recovery-exceeded")
        elif begun-start > 600:
            raise RuntimeError("computer-not-connected-within-600s")
        time.sleep(max(.05, 5-(time.monotonic()-begun)))
except Exception as exc:
    capture.write_json(folder / "summary.json", {"verdict": "stopped", "error": str(exc), "boot_id": BOOT, "device_writes": False})
    raise
capture.write_json(folder / "summary.json", result)
print("BOUNDED_NATIVE_NCM_RECOVERY_PASSED", result["recovery_upper_bound_seconds"], flush=True)
