#!/usr/bin/env python3
"""Replay this calibration's capacity calculation; never contacts a device."""
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT / "calibration"
raw = (CAPTURE / "trace.txt").read_bytes()
records = []
markers = {}
events = collections.Counter()
for line in raw.splitlines(keepends=True):
    if line.startswith(b"#"):
        continue
    match = re.search(rb"\s([0-7])\S{5}\s+(\d+)us[ +!#*@]*:\s+(\w+):", line)
    if not match:
        raise ValueError(f"Unparsed record: {line!r}")
    cpu, us, event = match.groups()
    cpu, us = int(cpu), int(us)
    records.append((us, cpu, len(line)))
    events[event.decode()] += 1
    marker = re.search(rb"GTS9_T229_(START|END)_cpu=([0-7])", line)
    if marker:
        phase, named_cpu = marker.groups()
        assert cpu == int(named_cpu)
        assert (cpu, phase.decode()) not in markers
        markers[cpu, phase.decode()] = us
assert records and all(a[0] <= b[0] for a, b in zip(records, records[1:]))


def peak_window(rows, seconds=41):
    """Largest serialized record volume in any closed window of this duration."""
    left = total = peak = 0
    end = None
    for right, (us, _, size) in enumerate(rows):
        total += size
        while us - rows[left][0] > seconds * 1_000_000:
            total -= rows[left][2]
            left += 1
        if total > peak:
            peak, end = total, us
    return {"bytes": peak, "window_end_relative_us": end}


cpus = []
for cpu in range(8):
    stats = {}
    for line in (CAPTURE / f"cpu{cpu}-after.stats").read_text().splitlines():
        key, value = line.split(":", 1)
        stats[key] = float(value) if "." in value else int(value)
    rows = [row for row in records if row[1] == cpu]
    assert len(rows) == stats["entries"]
    seconds = (markers[cpu, "END"] - markers[cpu, "START"]) / 1e6
    assert seconds >= 60
    for key in ("overrun", "commit overrun", "dropped events", "read events"):
        assert stats[key] == 0, (cpu, key, stats[key])
    cpus.append({"cpu": cpu, "marker_coverage_seconds": seconds,
                 "binary_stats": stats, "serialized_bytes": sum(r[2] for r in rows),
                 "peak_41s_serialized": peak_window(rows)})

assert (CAPTURE / "global-before.txt").read_bytes() == (CAPTURE / "global-after.txt").read_bytes()
assert (CAPTURE / "boot-id-before.txt").read_bytes() == (CAPTURE / "boot-id-after.txt").read_bytes()
assert (CAPTURE / "exit.status").read_text().strip() == "0"
assert (CAPTURE / "instance-removal.status").read_text().strip() == "0"
device_hash = (ROOT / "final-state/trace-sha256.txt").read_text().split()[0]
assert hashlib.sha256(raw).hexdigest() == device_hash
budget = (896 - 128) * 1024
peak = peak_window(records)
result = {
    "boot_id": (CAPTURE / "boot-id-before.txt").read_text().strip(),
    "trace_sha256": device_hash, "trace_text_bytes": len(raw),
    "record_count": len(records), "events": dict(sorted(events.items())),
    "all_cpu_common_marker_seconds": (min(markers[c, "END"] for c in range(8)) - max(markers[c, "START"] for c in range(8))) / 1e6,
    "per_cpu": cpus, "peak_41s_serialized": peak,
    "console_bytes": 896 * 1024, "other_log_reserve_bytes": 128 * 1024,
    "trace_budget_bytes": budget, "peak_41s_to_budget_ratio": peak["bytes"] / budget,
    "memory_coverage": "pass_for_observed_healthy_workload",
    "serialized_capacity": "reject" if peak["bytes"] > budget else "requires_printk_overhead_validation",
    "reboot_persistence": "not_tested", "early_boot_coverage": "not_tested",
    "ready_for_wedge_series": False,
    "limitations": "Latency-format trace read, not an actual panic/printk dump. Byte comparison excludes printk prefixes and later crash logs; observed workload is disarmed production steady state. Per-CPU windows omit remote sender records. No absence-based causal conclusion is supported."
}
print(json.dumps(result, indent=2))
