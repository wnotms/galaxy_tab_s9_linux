#!/usr/bin/env python3
"""Prepare an offline trace feasibility report; never arm tracing or flash."""

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "reference/boot-tests/test-228-csd-ipi-diagnostic"
EVENTS = ["csd:csd_queue_cpu", "csd:csd_function_entry", "csd:csd_function_exit",
          "ipi:ipi_raise", "ipi:ipi_entry", "ipi:ipi_exit", "rcu:rcu_stall_warning"]


def retention_budget(text_bytes, duration_s, console_bytes, reserve_bytes=128 * 1024):
    """Text throughput bounds console retention, NOT binary trace ring capacity."""
    if duration_s <= 0 or text_bytes <= 0 or console_bytes <= reserve_bytes:
        raise ValueError("invalid retention budget")
    rate = text_bytes / duration_s
    return {"historical_text_bytes_per_s": rate,
            "console_bytes": console_bytes, "reserved_for_other_printk_bytes": reserve_bytes,
            "optimistic_text_retention_s": (console_bytes - reserve_bytes) / rate,
            "required_history_s": 41,
            "fits_historical_text_rate": rate * 41 <= console_bytes - reserve_bytes}


def prepare(source, config):
    paths = {
        "smp": source / "kernel/smp.c",
        "rcu": source / "kernel/rcu/tree.c",
        "trace": source / "kernel/trace/trace.c",
        "rcu_dump": source / "kernel/rcu/rcu.h",
        "arm64_ipi": source / "arch/arm64/kernel/smp.c",
        "dts": ROOT / "kernel/dts/sm8550-samsung-gts9wifi.dts",
        "config": config,
        "available_events": RECORD / "baselines/tracepoints-available.txt",
        "historical_rate": RECORD / "baselines/event-rate-measurement.txt",
    }
    text = {name: path.read_text() for name, path in paths.items()}
    handler = text["rcu"].split("static void rcu_barrier_handler(", 1)[1].split("\n}", 1)[0]
    dump = text["trace"].split("void ftrace_dump(enum", 1)[1].split("EXPORT_SYMBOL", 1)[0]
    checks = {
        "rcu_barrier_handler_takes_raw_spinlock": "raw_spin_lock(&rcu_state.barrier_lock)" in handler,
        "ftrace_dump_releases_concurrency_guard": "atomic_dec(&dump_running);\n}" in dump,
        "rcu_dump_once_per_callsite": "static atomic_t ___rfd_beenhere" in text["rcu_dump"],
        "cur_csd_tracks_csd_work": "/* Record current CSD work for current CPU, NULL to erase. */" in text["smp"],
        "ipi_entry_precedes_csd_dispatch": "trace_ipi_entry(ipi_types[ipinr]);" in text["arm64_ipi"],
        "events_available_in_archived_boot": all(event in text["available_events"].splitlines() for event in EVENTS),
        "config_supports_event_tracing": all(f"CONFIG_{symbol}=y" in text["config"].splitlines()
                                              for symbol in ("TRACING", "EVENT_TRACING", "TRACEPOINTS", "PSTORE_CONSOLE")),
    }
    console_bytes = int(re.search(r"console-size\s*=\s*<(0x[0-9a-f]+)>;", text["dts"])[1], 16)
    measurement = re.search(r"=== bytes ===\s*(\d+)", text["historical_rate"])
    budget = retention_budget(int(measurement[1]), 30, console_bytes)
    return {
        "status": "offline-prepared; capture-readiness-unproven",
        "hardware_actions": [],
        "checks": checks,
        "proposed_events": EVENTS,
        "trace_clock": "global",
        "primary_trigger": "rcupdate.rcu_cpu_stall_ftrace_dump=1",
        "buffer_size_kb": "UNSET: size each CPU from binary stats and retained timestamps",
        "budget": budget,
        "blockers": [
            "Historical measurement has no exact enabled event set or per-CPU binary stats.",
            "41 seconds = 20 seconds pre-onset + nominal 21 seconds to RCU report; allow trigger delay too.",
            "896 KiB ramoops console cannot retain the historical multi-MiB text dump; reduce/filter or provide a proven sink.",
            "Validate start/end and per-CPU coverage in recovered dump before interpreting missing events.",
            "An early-boot trace must be enabled before the earliest observed failure; SSH arming is too late.",
        ],
        "input_sha256": {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path):
                         hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".work/linux-mainline")
    parser.add_argument("--config", type=Path, default=RECORD / "diagnostic-config.txt")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.source, args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Offline report: {args.output}")
    print(f"Source checks passed: {all(report['checks'].values())}; capture readiness: UNPROVEN")
    print(f"Historical text fits console for at most {report['budget']['optimistic_text_retention_s']:.2f}s with reserve, need >=41s")
    if not all(report["checks"].values()):
        parser.exit(1, "Source or capability assumptions changed: review the report.\n")


if __name__ == "__main__":
    main()
