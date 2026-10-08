"""Reproduce event metrics from the preserved little-endian ARM64 evdev data."""
from pathlib import Path
from collections import Counter
import json
import struct
import tarfile

root = Path(__file__).resolve().parent
summary = {"verdict": "OWNER_POSITION_PALM_ACCEPTED_PRESSURE_BUTTON_UNOBSERVED",
           "host_tests": {"executed": False, "reason": "evidence-only stage; unchanged 27-test qualification reused"},
           "kernel_build": {"executed": False, "reason": "unchanged modules"},
           "devices": {}}
joined = []
with tarfile.open(root / "capture-evidence.tar.gz") as archive:
    meta = json.loads(archive.extractfile("meta.json").read())
    terminal = json.loads(archive.extractfile("terminal.json").read())
    summary.update(boot_id=meta["boot_id"], capture=terminal,
                   final_health=json.loads(archive.extractfile("final-health.json").read()))
    for name in ("pen", "touch"):
        data = archive.extractfile(name + ".bin").read()
        assert len(data) == terminal["byte_counts"][name] and len(data) % 24 == 0
        events = list(struct.iter_unpack("<qqHHi", data))
        counts = Counter((typ, code) for _, _, typ, code, _ in events)
        metrics = {"events": len(events), "frames": counts[(0, 0)], "axes": {}, "keys": {}}
        for typ, code in sorted(counts):
            values = [value for _, _, t, c, value in events if t == typ and c == code]
            if typ in (1, 3):
                metrics["keys" if typ == 1 else "axes"][str(code)] = dict(
                    min=min(values), max=max(values), last=values[-1], count=len(values))
        summary["devices"][name] = metrics
        joined.extend((sec * 1000000 + usec, name, typ, code, value)
                      for sec, usec, typ, code, value in events)
    summary["kernel_final_records"] = len(archive.extractfile("kernel-final.jsonl").read().splitlines())
pen_near = False
last_pen_out = None
starts_near = 0
starts_after_out = 0
for timestamp, name, typ, code, value in sorted(joined):
    if (name, typ, code) == ("pen", 1, 320):
        pen_near = bool(value)
        if not pen_near:
            last_pen_out = timestamp
    if (name, typ, code) == ("touch", 3, 57) and value >= 0:
        starts_near += int(pen_near)
        starts_after_out += int(not pen_near and last_pen_out is not None)
summary["touch_tracking_starts_during_observed_pen_proximity"] = starts_near
summary["touch_tracking_starts_after_pen_out"] = starts_after_out
summary["limitation"] = "No capture clock ioctl change; merge uses native evdev timestamps. No tip/pressure/side-button event observed; absence alone is not proof of either attempted operation or suppression."
owner = json.loads((root / "owner-confirmation.json").read_text())
summary["owner_clarification"] = owner.get("follow_up_answer")
print(json.dumps(summary, indent=2, sort_keys=True))
