#!/usr/bin/python3
"""Optional desktop touch loader, qualified only for the exact Test331 kernel.

Keep this module outside the paired production module directory. TCPM/charging
experiments must not acquire a new touch load. No retries, forced loading,
unloading, firmware updates or sysfs writes are performed here.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

PROFILE = {
    "kernel": "Test331",
    "release": "7.2.0-rc3-gts9wifi-dirty",
    "config_sha256": "51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a",
    "notes_sha256": "03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95",
    "module_sha256": "ac2fbdc6489b847771a65a1971d28f0b5d601c796c50d68c92f85a70feaf5e45",
}
MODULE = Path("/usr/local/lib/gts9-desktop/fts1ba90a.ko")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(root=Path("/"), *, machine=None, release=None):
    """Read existing sysfs/DT only; this is not an I2C address scan."""
    def path(name):
        return root / name.lstrip("/")

    result = {"status": "skipped", "reason": "unqualified identity"}
    try:
        result["boot_id"] = path("/proc/sys/kernel/random/boot_id").read_text().strip()
        machine = machine if machine is not None else os.uname().machine
        release = release if release is not None else os.uname().release
        compatibles = path("/sys/firmware/devicetree/base/compatible").read_bytes().split(b"\0")
        if machine != "aarch64" or release != PROFILE["release"] or b"samsung,gts9wifi" not in compatibles:
            return result
        cmdline = path("/proc/cmdline").read_text().split()
        if any(token.startswith(("sm5440_fedora.", "sm5440_direct.", "sm5440-direct."))
               or token == "lpcharge=1" for token in cmdline):
            result["reason"] = "charging experiment or low-power charging boot"
            return result
        config = gzip.decompress(path("/proc/config.gz").read_bytes())
        result["config_sha256"] = digest(config)
        result["notes_sha256"] = digest(path("/sys/kernel/notes").read_bytes())
        if any(result[key] != PROFILE[key] for key in ("config_sha256", "notes_sha256")):
            return result
    except (OSError, EOFError, ValueError) as exc:
        result["reason"] = "identity unavailable: " + str(exc)
        return result

    # All subsequent failures are on the approved kernel; do not conceal them
    # as a successful skip. A Wants relationship still leaves rescue/GDM free.
    try:
        result["module_sha256"] = digest(path(str(MODULE)).read_bytes())
        if result["module_sha256"] != PROFILE["module_sha256"]:
            raise ValueError("installed module hash mismatch")
        clients = []
        for client in path("/sys/bus/i2c/devices").glob("*-0049"):
            compatible = client / "of_node/compatible"
            if compatible.exists() and b"st,fts1ba90a" in compatible.read_bytes().split(b"\0"):
                clients.append(client)
        if len(clients) != 1:
            raise ValueError("expected exactly one existing FTS1BA90A DT client")
        client = clients[0]
        result["client"] = client.name
        driver = client / "driver"
        bound = driver.resolve().name if driver.exists() else None
        loaded = path("/sys/module/fts1ba90a").exists()
        if loaded:
            if (bound != "fts1ba90a" or not list(client.glob("input/input*/event*"))
                    or not (client / "double_tap_to_wake").exists()):
                result["probe_pending"] = True
                raise ValueError("loaded driver lacks bound touchscreen/input")
            if (client / "double_tap_to_wake").read_text().strip() != "0":
                raise ValueError("double-tap wake is outside the qualified scope")
            result.update(status="already-loaded", reason="no insmod or hardware write")
        else:
            if bound is not None:
                raise ValueError("touchscreen is owned by another driver")
            battery = path("/sys/class/power_supply/sm5714-battery")
            if (battery / "health").read_text().strip() != "Good" or not 0 <= int((battery / "temp").read_text()) < 420:
                raise ValueError("battery safety gate failed")
            result.update(status="ready", reason="qualified kernel/module and existing DT client")
    except (OSError, ValueError) as exc:
        result.update(status="error", reason=str(exc))
    return result


def run(load=False, *, inspect_state=inspect, invoke=subprocess.run,
        clock=time.monotonic, sleep=time.sleep):
    result = inspect_state()
    result["insmod_attempts"] = 0
    if result["status"] != "ready" or not load:
        return result
    result["insmod_attempts"] = 1
    try:
        command = invoke(["/sbin/insmod", str(MODULE)], capture_output=True, text=True, timeout=8)
        result["loader"] = {"returncode": command.returncode, "stdout": command.stdout, "stderr": command.stderr}
        if command.returncode:
            raise ValueError("normal kernel loader rejected module; no retry")
        # The driver probes asynchronously. Observe only, never rebind or unload.
        deadline = clock() + 5
        while True:
            state = inspect_state()
            if state.get("boot_id") != result.get("boot_id"):
                raise ValueError("boot changed during touch load")
            if state["status"] == "already-loaded":
                result.update(status="loaded", reason="one normal load; bound input ready")
                return result
            if not state.get("probe_pending") or clock() >= deadline:
                raise ValueError("touch probe did not reach qualified bound input: " + state["reason"])
            sleep(0.1)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result.update(status="error", reason=str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load", action="store_true", help="permit one normal load after identity gates")
    args = parser.parse_args()
    result = run(args.load)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
