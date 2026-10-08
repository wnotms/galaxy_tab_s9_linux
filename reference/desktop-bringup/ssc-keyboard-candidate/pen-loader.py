#!/usr/bin/python3
"""Optional X710 Wacom loader, gated to the accepted Test331 kernel."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

PROFILE = {'release': '7.2.0-rc3-gts9wifi-dirty', 'config_sha256': '599ca47ab41a29469c3d5830e475049fca9f33bd2ab0923ad014e5ba3fa6ec6c', 'notes_sha256': '3fe9191a85ec0eaecbe8c24dd2e58b7281050876adbc60d8f21c73f5b917c5bd', 'module_sha256': '6ddebabd6cd38d1d4e8b13610b32f0f4fb737d7c939c14854afac876b70c86e5'}
MODULE = Path("/usr/local/lib/gts9-desktop/wacom-wez01.ko")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(root=Path("/"), *, machine=None, release=None):
    def path(name):
        return root / name.lstrip("/")

    result = {"status": "skipped", "reason": "unqualified identity"}
    try:
        result["boot_id"] = path("/proc/sys/kernel/random/boot_id").read_text().strip()
        machine = machine if machine is not None else os.uname().machine
        release = release if release is not None else os.uname().release
        compatible = path("/sys/firmware/devicetree/base/compatible").read_bytes()
        if machine != "aarch64" or release != PROFILE["release"] or b"samsung,gts9wifi" not in compatible:
            return result
        if any(x == "lpcharge=1" or x.startswith(("sm5440_fedora.", "sm5440_direct."))
               for x in path("/proc/cmdline").read_text().split()):
            result["reason"] = "charging experiment or low-power boot"
            return result
        result["config_sha256"] = _sha(gzip.decompress(path("/proc/config.gz").read_bytes()))
        result["notes_sha256"] = _sha(path("/sys/kernel/notes").read_bytes())
        if any(result[k] != PROFILE[k] for k in ("config_sha256", "notes_sha256")):
            return result
        result["module_sha256"] = _sha(path(str(MODULE)).read_bytes())
        if result["module_sha256"] != PROFILE["module_sha256"]:
            raise ValueError("installed module hash mismatch")
        clients = []
        for client in path("/sys/bus/i2c/devices").glob("*-0056"):
            node = client / "of_node/compatible"
            if node.exists() and b"wacom,w90xx" in node.read_bytes().split(b"\0"):
                clients.append(client)
        if len(clients) != 1:
            raise ValueError("expected exactly one Wacom WEZ01 DT client")
        client = clients[0]
        result["client"] = client.name
        driver = client / "driver"
        bound = driver.resolve().name if driver.exists() else None
        loaded = path("/sys/module/wacom_wez01").exists()
        if loaded:
            if bound != "wacom-wez01" or not list(client.glob("input/input*/event*")):
                raise ValueError("loaded pen lacks bound input")
            result.update(status="already-loaded", reason="no insmod or hardware write")
        elif bound is not None:
            raise ValueError("pen client is owned by another driver")
        else:
            battery = path("/sys/class/power_supply/sm5714-battery")
            if (battery / "health").read_text().strip() != "Good" or not 0 <= int((battery / "temp").read_text()) < 420:
                raise ValueError("battery safety gate failed")
            result.update(status="ready", reason="qualified kernel/module and existing DT client")
    except (OSError, EOFError, ValueError) as exc:
        result.update(status="error", reason=str(exc))
    result["insmod_attempts"] = 0
    return result


def run(load=False, *, inspect_state=inspect, invoke=subprocess.run,
        clock=time.monotonic, sleep=time.sleep):
    result = inspect_state()
    result.setdefault("insmod_attempts", 0)
    if result["status"] != "ready" or not load:
        return result
    result["insmod_attempts"] = 1
    try:
        command = invoke(["/sbin/insmod", str(MODULE)], capture_output=True,
                         text=True, timeout=8)
        result["loader"] = {"returncode": command.returncode,
                            "stdout": command.stdout, "stderr": command.stderr}
        if command.returncode:
            raise ValueError("normal kernel loader rejected module; no retry")
        deadline = clock() + 5
        while True:
            state = inspect_state()
            if state.get("boot_id") != result.get("boot_id"):
                raise ValueError("boot changed during pen load")
            if state["status"] == "already-loaded":
                result.update(status="loaded", reason="one normal load; bound input ready")
                return result
            if state["status"] != "ready" or clock() >= deadline:
                raise ValueError("pen probe did not reach qualified bound input: " + state["reason"])
            sleep(0.1)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result.update(status="error", reason=str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load", action="store_true", help="permit one normal load after identity gates")
    result = run(parser.parse_args().load)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
