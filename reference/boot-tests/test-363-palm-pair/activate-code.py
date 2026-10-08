"""One registered pair service start on the owner-rebooted Test331 boot."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

BOOT = "28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af"
report = {"expected_boot": BOOT, "started_at": time.time(), "commands": []}


def command(argv, accepted=(0,), timeout=20):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    report["commands"].append(dict(argv=argv, returncode=result.returncode,
                                   stdout=result.stdout, stderr=result.stderr))
    if result.returncode not in accepted:
        raise RuntimeError("command failed: " + repr(argv))
    return result.stdout


try:
    assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT
    loader = Path("/usr/local/libexec/gts9-palm").read_bytes()
    assert hashlib.sha256(loader).hexdigest() == "3d2c9022b0a6726970ba07c517bdcad18c3d040e91183da22a74abc829f89157"
    ns = {"__name__": "pair_gate"}
    exec(compile(loader, "installed-gts9-palm", "exec"), ns)
    report["preflight"] = ns["inspect"]()
    assert report["preflight"]["status"] == "ready"
    assert not report["preflight"]["pen_loaded"]
    assert not report["preflight"]["touch_loaded"]
    assert command(["systemctl", "--failed", "--no-legend", "--plain"]).strip() == ""
    report["kernel_before_json"] = command(["journalctl", "-b", "-k", "-o", "json", "--no-pager"])
    command(["systemctl", "start", "gts9-palm.service"], timeout=35)
    assert command(["systemctl", "is-active", "gts9-palm.service"]).strip() == "active"
    report["postflight"] = ns["inspect"](allow_pair=True)
    assert report["postflight"]["status"] == "already-loaded-pair"
    assert report["postflight"]["boot_id"] == BOOT
    for key in ("pen_client", "touch_client"):
        client = Path("/sys/bus/i2c/devices") / report["postflight"][key]
        events = list(client.glob("input/input*/event*"))
        assert events, "no input event device: " + key
        report[key + "_events"] = [str(event) for event in events]
    report["input_devices"] = Path("/proc/bus/input/devices").read_text()
    report["unit_journal_json"] = command(["journalctl", "-b", "-u", "gts9-palm.service", "-o", "json", "--no-pager"])
    assert command(["systemctl", "--failed", "--no-legend", "--plain"]).strip() == ""
    battery = Path("/sys/class/power_supply/sm5714-battery")
    report["battery"] = {n: (battery / n).read_text().strip()
                         for n in ("capacity", "temp", "health", "status")}
    assert report["battery"]["health"] == "Good" and 0 <= int(report["battery"]["temp"]) < 420
    report["verdict"] = "PAIR_BOUND_OWNER_INPUT_PENDING"
except Exception as exc:
    report.update(verdict="STOP", error=repr(exc))
finally:
    try:
        report["kernel_after_json"] = command(["journalctl", "-b", "-k", "-o", "json", "--no-pager"])
    except Exception as exc:
        report.update(verdict="STOP", collection_error=repr(exc))
    report["finished_at"] = time.time()
    print(json.dumps(report))
if report["verdict"] == "STOP":
    raise SystemExit(1)
