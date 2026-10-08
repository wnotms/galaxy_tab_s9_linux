#!/usr/bin/python3
"""Load the opt-in X710 Wacom + palm-aware FTS pair once, safely."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

PROFILE = {'release': '7.2.0-rc3-gts9wifi-dirty', 'config_sha256': '599ca47ab41a29469c3d5830e475049fca9f33bd2ab0923ad014e5ba3fa6ec6c', 'notes_sha256': 'ee5e7513c130df77cdbe1ff165e6926a0427ff3de1aeaa2e78ce50f75bb90eb4', 'pen_sha256': '6ddebabd6cd38d1d4e8b13610b32f0f4fb737d7c939c14854afac876b70c86e5', 'touch_sha256': '590c1a3e3a215e0dbfbdc9986697a2ef3dd82f64bb21e29539b328cf18746253'}
PEN = Path("/usr/local/lib/gts9-desktop/wacom-wez01.ko")
TOUCH = Path("/usr/local/lib/gts9-desktop/fts1ba90a-palm.ko")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _client(root, suffix, compatible):
    clients = []
    for client in (root / "sys/bus/i2c/devices").glob("*-" + suffix):
        node = client / "of_node/compatible"
        if node.exists() and compatible in node.read_bytes().split(b"\0"):
            clients.append(client)
    if len(clients) != 1:
        raise ValueError("expected one " + compatible.decode() + " DT client")
    return clients[0]


def inspect(root=Path("/"), *, machine=None, release=None, allow_pair=False):
    def path(name):
        return root / name.lstrip("/")

    result = {"status": "skipped", "reason": "unqualified identity", "insmod_attempts": 0}
    try:
        result["boot_id"] = path("/proc/sys/kernel/random/boot_id").read_text().strip()
        machine = machine if machine is not None else os.uname().machine
        release = release if release is not None else os.uname().release
        if machine != "aarch64" or release != PROFILE["release"]:
            return result
        if b"samsung,gts9wifi" not in path("/sys/firmware/devicetree/base/compatible").read_bytes():
            return result
        if any(x == "lpcharge=1" or x.startswith(("sm5440_fedora.", "sm5440_direct."))
               for x in path("/proc/cmdline").read_text().split()):
            result["reason"] = "charging experiment or low-power boot"
            return result
        result["config_sha256"] = digest(gzip.decompress(path("/proc/config.gz").read_bytes()))
        result["notes_sha256"] = digest(path("/sys/kernel/notes").read_bytes())
        if any(result[k] != PROFILE[k] for k in ("config_sha256", "notes_sha256")):
            return result
        result["pen_sha256"] = digest(path(str(PEN)).read_bytes())
        result["touch_sha256"] = digest(path(str(TOUCH)).read_bytes())
        if result["pen_sha256"] != PROFILE["pen_sha256"] or result["touch_sha256"] != PROFILE["touch_sha256"]:
            raise ValueError("paired module hash mismatch")
        pen = _client(path("/"), "0056", b"wacom,w90xx")
        touch = _client(path("/"), "0049", b"st,fts1ba90a")
        result.update(pen_client=pen.name, touch_client=touch.name)
        pen_loaded = path("/sys/module/wacom_wez01").exists()
        touch_loaded = path("/sys/module/fts1ba90a").exists()
        result["pen_loaded"] = pen_loaded
        result["touch_loaded"] = touch_loaded
        if touch_loaded:
            if allow_pair and pen_loaded and (pen / "driver").resolve().name == "wacom-wez01" \
                    and (touch / "driver").resolve().name == "fts1ba90a":
                result.update(status="already-loaded-pair", reason="paired modules already bound")
                return result
            raise ValueError("FTS is already loaded; do not replace accepted touch module")
        if (pen / "driver").exists():
            if not pen_loaded or (pen / "driver").resolve().name != "wacom-wez01":
                raise ValueError("Wacom client is owned by another driver")
        if (touch / "driver").exists():
            raise ValueError("FTS client is owned by another driver")
        battery = path("/sys/class/power_supply/sm5714-battery")
        if (battery / "health").read_text().strip() != "Good" or not 0 <= int((battery / "temp").read_text()) < 420:
            raise ValueError("battery safety gate failed")
        result.update(status="ready", reason="qualified exact pair and unbound clients")
    except (OSError, EOFError, ValueError) as exc:
        result.update(status="error", reason=str(exc))
    return result


def run(load=False, *, inspect_state=inspect, invoke=subprocess.run,
        clock=time.monotonic, sleep=time.sleep):
    result = inspect_state()
    if result["status"] != "ready" or not load:
        return result
    try:
        for module in (PEN, TOUCH):
            result["insmod_attempts"] += 1
            command = invoke(["/sbin/insmod", str(module)], capture_output=True,
                             text=True, timeout=8)
            result.setdefault("loader", []).append({"module": str(module),
                "returncode": command.returncode, "stdout": command.stdout,
                "stderr": command.stderr})
            if command.returncode:
                raise ValueError("normal loader rejected pair; no retry")
            deadline = clock() + 5
            while True:
                state = inspect_state(allow_pair=(module == TOUCH))
                if state.get("boot_id") != result.get("boot_id"):
                    raise ValueError("boot changed during paired load")
                if module == PEN and state.get("pen_loaded") and not state.get("touch_loaded"):
                    break
                if module == TOUCH and state.get("status") == "already-loaded-pair":
                    break
                if clock() >= deadline:
                    raise ValueError("paired probe did not complete")
                sleep(0.1)
        result.update(status="loaded", reason="one normal Wacom then FTS pair load")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result.update(status="error", reason=str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load", action="store_true", help="permit one normal pair load")
    result = run(parser.parse_args().load)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
