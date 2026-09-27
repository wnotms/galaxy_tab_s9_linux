#!/usr/bin/env python3
"""Offline byte-bounded tail experiment on the complete test-229 capture.

This is not a kernel dumper. Prefix sizes are modeling assumptions, not measured
printk overhead; a fitting file never establishes persistence or hardware readiness.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

CPUS = tuple(range(8))
EVENTS = {
    "csd:csd_queue_cpu", "csd:csd_function_entry", "csd:csd_function_exit",
    "ipi:ipi_raise", "ipi:ipi_entry", "ipi:ipi_exit", "rcu:rcu_stall_warning",
}
METADATA_BYTES = 16 * 1024
# Pinned ramoops: requested 896 KiB -> 512 KiB zone; header 12 bytes, ECC=0.
DEFAULT_BUDGET = 512 * 1024 - 12 - 128 * 1024
DEFAULT_CAPTURE = Path(__file__).resolve().parents[1] / "reference/boot-tests/test-229-trace-retention-calibration"


def read_capture(root):
    """Require the original complete observation; fail closed on missing evidence."""
    capture = root / "calibration"
    data = (capture / "trace.txt").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != (root / "final-state/trace-sha256.txt").read_text().split()[0]:
        raise ValueError("trace hash differs from device hash")
    boot = (capture / "boot-id-before.txt").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", boot):
        raise ValueError("invalid boot ID")
    if boot != (capture / "boot-id-after.txt").read_text().strip():
        raise ValueError("boot changed")
    if "[global]" not in (capture / "trace_clock.txt").read_text():
        raise ValueError("cross-CPU clock not global")
    enabled = set((capture / "set_event.txt").read_text().split())
    if enabled != EVENTS:
        raise ValueError("unexpected enabled events")
    for event in enabled:
        if (capture / (event.replace(":", "-") + ".filter")).read_text().strip() != "none":
            raise ValueError("filtered source")
    rows, markers = [], {}
    for line in data.splitlines(keepends=True):
        if line.startswith(b"#"):
            continue
        match = re.search(rb"\s([0-7])\S{5}\s+(\d+)us[ +!#*@]*:\s+(\w+):", line)
        if not match or not line.endswith(b"\n"):
            raise ValueError("malformed or partial trace record")
        cpu, us, event = match.groups()
        cpu, us = int(cpu), int(us)
        if event.decode() not in {e.split(":")[1] for e in EVENTS} | {"tracing_mark_write"}:
            raise ValueError("unknown event")
        rows.append((us, cpu, line))
        marker = re.search(rb"GTS9_T229_(START|END)_cpu=([0-7])", line)
        if marker:
            phase, named_cpu = marker.groups()
            key = (cpu, phase.decode())
            if cpu != int(named_cpu) or key in markers:
                raise ValueError("invalid boundary marker")
            markers[key] = us
    if not rows or any(a[0] > b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("empty or unordered trace")
    counts = Counter(r[1] for r in rows)
    stats = {}
    for cpu in CPUS:
        stats[cpu] = {}
        for phase in ("before", "after"):
            values = dict(line.split(":", 1) for line in
                          (capture / f"cpu{cpu}-{phase}.stats").read_text().splitlines())
            stats[cpu][phase] = values
            for field in ("overrun", "commit overrun", "dropped events", "read events"):
                if int(values[field]) != 0:
                    raise ValueError("source lost or consumed records")
            expected = 0 if phase == "before" else counts[cpu]
            if int(values["entries"]) != expected:
                raise ValueError("source entry count mismatch")
        if (cpu, "START") not in markers or (cpu, "END") not in markers:
            raise ValueError("missing CPU boundary")
        if markers[cpu, "END"] - markers[cpu, "START"] < 60_000_000:
            raise ValueError("source CPU coverage below 60 seconds")
    start = max(markers[c, "START"] for c in CPUS)
    end = min(markers[c, "END"] for c in CPUS)
    return rows, {"source_sha256": digest, "boot_id": boot,
                  "enabled_events": sorted(enabled), "filters": "none",
                  "clock": "global", "common_start_us": start, "trigger_us": end,
                  "source_loss_counters": "zero_on_every_cpu", "source_stats": stats}


def serialize(rows, source, budget=DEFAULT_BUDGET, prefix_bytes=32, window_seconds=41):
    """Equal per-CPU budgets retain contiguous tails, including sender records.

    Keep raw lines, ordering and identities. Never fill a hole with older records
    when a large record will not fit. Unused space is deliberate fairness reserve.
    """
    if budget <= METADATA_BYTES or prefix_bytes < 0 or window_seconds <= 0:
        raise ValueError("invalid budget, prefix size or interval")
    end = source["trigger_us"]
    cutoff = end - window_seconds * 1_000_000
    if cutoff < source["common_start_us"]:
        raise ValueError("requested window predates complete source coverage")
    allowance = (budget - METADATA_BYTES) // len(CPUS)
    selected, cpus = [], []
    for cpu in CPUS:
        candidates = [r for r in rows if r[1] == cpu and cutoff <= r[0] <= end]
        tail, used = [], 0
        for row in reversed(candidates):
            cost = len(row[2]) + prefix_bytes
            if used + cost > allowance:
                break
            tail.append(row)
            used += cost
        tail.reverse()
        selected.extend(tail)
        dropped = len(candidates) - len(tail)
        # Equal timestamps can straddle the cut; a dropped record always fails
        # completeness even when the retained timestamp span appears sufficient.
        cpus.append({"cpu": cpu, "input_records": len(candidates),
                     "kept_records": len(tail), "dropped_records": dropped,
                     "truncated": bool(dropped), "serialized_record_bytes": used,
                     "first_kept_us": tail[0][0] if tail else None,
                     "last_kept_us": tail[-1][0] if tail else None,
                     "retained_event_span_seconds": (tail[-1][0] - tail[0][0]) / 1e6 if tail else 0,
                     "complete_requested_window": dropped == 0})
    selected.sort(key=lambda r: (r[0], r[1]))
    complete = all(c["complete_requested_window"] for c in cpus)
    report = {"format": "gts9-offline-tail-v1", **source,
              "cutoff_us": cutoff, "window_seconds": window_seconds,
              "trace_budget_bytes": budget, "metadata_reserve_bytes": METADATA_BYTES,
              "per_cpu_record_budget_bytes": allowance,
              "modeled_prefix_bytes_per_line": prefix_bytes,
              "per_cpu": cpus, "complete_all_cpu_window": complete,
              "cross_cpu_missing_event_inference": "inconclusive" if not complete else "requires_live_validation",
              "ready_for_wedge_series": False,
              "persistent_recovery": "not_tested", "early_boot_coverage": "not_tested"}
    # One modeled prefix for the metadata line and one per raw event line.
    prefix = b"~" * prefix_bytes
    metadata = prefix + json.dumps(report, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(metadata) > METADATA_BYTES:
        raise ValueError("metadata exceeds its reserved byte budget")
    payload = metadata + b"".join(prefix + r[2] for r in selected)
    if len(payload) > budget:
        raise ValueError("serialization exceeds total budget")
    report["metadata_actual_bytes"] = len(metadata)
    report["serialized_bytes"] = len(payload)
    report["serialized_sha256"] = hashlib.sha256(payload).hexdigest()
    return payload, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-bytes", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--prefix-bytes", type=int, default=32)
    parser.add_argument("--window-seconds", type=int, default=41)
    args = parser.parse_args()
    rows, source = read_capture(args.capture)
    payload, report = serialize(rows, source, args.budget_bytes, args.prefix_bytes, args.window_seconds)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "modeled-console.txt").write_bytes(payload)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("serialized_bytes", "complete_all_cpu_window", "ready_for_wedge_series")}))


if __name__ == "__main__":
    main()
