"""Bounded non-grabbing pen/touch recording on the qualified pair boot."""
from contextlib import ExitStack
from pathlib import Path
import fcntl
import json
import os
import select
import struct
import time

BOOT = "28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af"
ROOT = Path("/var/log/gts9-test363-pair")
EXPECTED = {"pen": ("event4", "Wacom WEZ01 S Pen"),
            "touch": ("event5", "FTS1BA90A Touchscreen")}
assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT
layout = struct.Struct("@llHHi")
assert layout.size == 24
ROOT.mkdir(exist_ok=False)
meta = dict(boot_id=BOOT, pid=os.getpid(), grabbing=False,
            proc_start_ticks=Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19],
            deadline_seconds=600, event_struct="@llHHi", devices={})
counts = {key: 0 for key in EXPECTED}
start = time.monotonic()
reason = "deadline"
try:
    with ExitStack() as stack:
        readers = {}
        for key, (event, name) in EXPECTED.items():
            assert (Path("/sys/class/input") / event / "device/name").read_text().strip() == name
            fd = os.open("/dev/input/" + event, os.O_RDONLY | os.O_NONBLOCK)
            stack.callback(os.close, fd)
            raw = stack.enter_context((ROOT / (key + ".bin")).open("xb"))
            readers[fd] = (key, raw)
            meta["devices"][key] = dict(event=event, name=name, axes={})
            for code in ((0, 1, 24, 25, 26, 27) if key == "pen" else (53, 54)):
                buf = bytearray(24)
                fcntl.ioctl(fd, 0x80184540 + code, buf, True)
                meta["devices"][key]["axes"][str(code)] = list(struct.unpack("6i", buf))
        (ROOT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        while time.monotonic() - start < 600:
            assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT
            battery = Path("/sys/class/power_supply/sm5714-battery")
            assert (battery / "health").read_text().strip() == "Good"
            assert 0 <= int((battery / "temp").read_text()) < 420
            if (ROOT / "stop").exists():
                reason = "owner_result_collected"
                break
            ready, _, _ = select.select(list(readers), [], [], 1)
            for fd in ready:
                key, raw = readers[fd]
                data = os.read(fd, layout.size * 256)
                if not data:
                    raise RuntimeError("input device closed: " + key)
                raw.write(data)
                raw.flush()
                counts[key] += len(data)
                if counts[key] > 32 * 1024 * 1024:
                    raise RuntimeError("event volume exceeded: " + key)
except BaseException as exc:
    reason = repr(exc)
    raise
finally:
    (ROOT / "terminal.json").write_text(json.dumps(dict(
        pid=os.getpid(), reason=reason, seconds=time.monotonic() - start,
        byte_counts=counts), indent=2) + "\n")
