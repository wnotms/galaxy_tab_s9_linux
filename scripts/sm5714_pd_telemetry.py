#!/usr/bin/env python3
"""Read-only SM5714 battery power telemetry; TCPM values are not input meters."""

import argparse
import json
from pathlib import Path
import re
import sys
import time

import production_reboot_stability as capture
import production_stability_evidence as evidence

SAMPLE_COMMAND = r'''set -eu
echo 'SECTION meta'
printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
printf 'uptime='; cut -d' ' -f1 /proc/uptime
echo 'SECTION battery'; cat /sys/class/power_supply/sm5714-battery/uevent
echo 'SECTION usb'; cat /sys/class/power_supply/sm5714-usb/uevent
echo 'SECTION tcpm'; cat /sys/class/power_supply/tcpm-source-psy-3-0033/uevent
echo 'SECTION typec'
for f in power_role data_role power_operation_mode; do
    printf '%s=' "$f"; cat "/sys/class/typec/port0/$f"
done
'''


def active_type(value):
    matches = re.findall(r"\[([^]]+)\]", value)
    if len(matches) != 1:
        raise ValueError("USB type does not have exactly one active bracketed value")
    return matches[0]


def parse_sample(raw):
    sections = {}
    current = None
    for line in raw.replace("\r", "").splitlines():
        if line.startswith("SECTION "):
            current = line.split(" ", 1)[1]
            if current in sections:
                raise ValueError("duplicate telemetry section")
            sections[current] = {}
        elif "=" in line:
            if current is None:
                raise ValueError("telemetry field before section")
            key, value = line.split("=", 1)
            sections[current][key] = value
    if set(sections) != {"meta", "battery", "usb", "tcpm", "typec"}:
        raise ValueError("missing telemetry section")
    bat, usb, pd, meta, roles = (sections[x] for x in ("battery", "usb", "tcpm", "meta", "typec"))
    voltage = int(bat["POWER_SUPPLY_VOLTAGE_NOW"])
    current = int(bat["POWER_SUPPLY_CURRENT_NOW"])
    contract_uv = int(pd["POWER_SUPPLY_VOLTAGE_NOW"])
    limit = int(usb["POWER_SUPPLY_INPUT_CURRENT_LIMIT"])
    return {
        "boot_id": evidence.canonical_boot_id(meta["boot_id"]),
        "uptime_seconds": float(meta["uptime"]),
        "battery_voltage_uv": voltage, "battery_current_ua": current,
        "battery_net_power_w": voltage * current / 1e12,
        "battery_soc": int(bat["POWER_SUPPLY_CAPACITY"]),
        "battery_temp_deciC": int(bat["POWER_SUPPLY_TEMP"]),
        "battery_health": bat["POWER_SUPPLY_HEALTH"],
        "battery_status": bat["POWER_SUPPLY_STATUS"],
        "usb_online": int(usb["POWER_SUPPLY_ONLINE"]),
        "usb_type": active_type(usb["POWER_SUPPLY_USB_TYPE"]),
        "tcpm_online": int(pd["POWER_SUPPLY_ONLINE"]),
        "tcpm_type": active_type(pd["POWER_SUPPLY_USB_TYPE"]),
        "contract_voltage_uv": contract_uv,
        "contract_current_ua": int(pd["POWER_SUPPLY_CURRENT_NOW"]),
        "input_current_limit_ua": limit,
        "configured_input_ceiling_w": contract_uv * limit / 1e12,
        "measured_input_power_w": None,
        "power_role": active_type(roles["power_role"]),
        "data_role": active_type(roles["data_role"]),
        "power_operation_mode": roles["power_operation_mode"],
    }


def assess(sample, boot, previous=(), attached=False):
    """Return a fatal reason, or None. No policy writes or power inference."""
    if sample["boot_id"] != evidence.canonical_boot_id(boot):
        return "boot-changed"
    if sample["battery_health"] != "Good":
        return "battery-health"
    if not 3400000 <= sample["battery_voltage_uv"] <= 4440000:
        return "battery-voltage"
    if sample["battery_temp_deciC"] >= 450:
        return "battery-temperature"
    if sample["battery_current_ua"] > 2100000:
        return "battery-charge-current"
    if sample["power_role"] != "sink" or sample["data_role"] != "device":
        return "unexpected-role"
    for old in previous:
        delta = sample["uptime_seconds"] - old["uptime_seconds"]
        if 0 < delta <= 60 and sample["battery_temp_deciC"] - old["battery_temp_deciC"] >= 30:
            return "rapid-temperature-rise"
    voltage = sample["contract_voltage_uv"]
    if sample["tcpm_online"] and sample["tcpm_type"] not in {"C", "PD"}:
        return "unsupported-active-pd-type"
    if voltage not in {0, 5000000, 9000000}:
        return "unsupported-contract-voltage"
    if sample["usb_online"] and voltage:
        maximum = 1500000 if voltage == 9000000 else 1800000
        limit = sample["input_current_limit_ua"]
        if limit > maximum or limit > sample["contract_current_ua"]:
            return "input-limit-exceeds-policy-or-grant"
    if attached and (not sample["usb_online"] or not sample["tcpm_online"] or not voltage):
        return "charger-or-contract-lost"
    return None


def summarize(samples):
    if not samples:
        raise ValueError("no charging samples")
    powers = [x["battery_net_power_w"] for x in samples]
    return {
        "battery_net_power_w": {"min": min(powers), "max": max(powers),
                                "mean": sum(powers) / len(powers)},
        "positive_current_samples": sum(x["battery_current_ua"] > 0 for x in samples),
        "sample_count": len(samples),
        "soc_start": samples[0]["battery_soc"], "soc_end": samples[-1]["battery_soc"],
        "temperature_deciC_min": min(x["battery_temp_deciC"] for x in samples),
        "temperature_deciC_max": max(x["battery_temp_deciC"] for x in samples),
        "contract_voltage_uv_values": sorted({x["contract_voltage_uv"] for x in samples}),
        "configured_input_ceiling_w_max": max(x["configured_input_ceiling_w"] for x in samples),
        "actual_input_power_measured": False, "actual_vbus_independently_measured": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wifi", required=True)
    parser.add_argument("--boot", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to reuse an evidence directory")
    rec = capture.Recorder(args.output)
    baseline = capture.ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt"
    known = {x["MESSAGE"] for x in map(json.loads, baseline.read_text().splitlines())
             if int(x.get("PRIORITY", 7)) <= 3}
    argv = ["env", "GTS9_DEVICE=" + args.wifi, capture.SSH]
    charging, all_samples = [], []
    start = time.monotonic()
    first_online = None
    window = None
    checkpoint = False
    last_journal = None
    try:
        with (args.output / "samples.jsonl").open("w") as stream:
            while True:
                loop_start = time.monotonic()
                number = len(all_samples)
                prefix = f"sample-{number:04}-"
                raw = rec.command(prefix + "telemetry", argv + [SAMPLE_COMMAND], timeout=12)[0]
                sample = parse_sample(raw)
                sample["elapsed_seconds"] = round(loop_start - start, 3)
                error = assess(sample, args.boot, all_samples, attached=window is not None)
                sample["stop_reason"] = error
                all_samples.append(sample)
                stream.write(json.dumps(sample, sort_keys=True) + "\n")
                stream.flush()
                if error:
                    raise RuntimeError(error)
                if sample["usb_online"] and first_online is None:
                    first_online = loop_start
                ready = (sample["usb_online"] and sample["tcpm_online"] and
                         sample["contract_voltage_uv"] in {5000000, 9000000} and
                         sample["contract_current_ua"] >= 100000)
                if ready and window is None:
                    window = loop_start
                    print("CHARGING_WINDOW_STARTED", sample["contract_voltage_uv"], flush=True)
                if first_online is not None and not ready and loop_start - first_online > 45:
                    raise RuntimeError("contract-not-stable-within-45s")
                if window is None and loop_start - start > 600:
                    raise RuntimeError("charger-not-connected-within-600s")
                if window is not None:
                    charging.append(sample)
                if last_journal is None or loop_start - last_journal >= 30:
                    journal = rec.command(prefix + "kernel-json", argv + ["journalctl -b -k --no-pager -o json"], timeout=35)[0]
                    scan = evidence.inspect_journal(journal, args.boot, known,
                             accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
                             accepted_qca_cycles=True, observed_uptime=sample["uptime_seconds"])
                    capture.write_json(args.output / (prefix + "kernel-scan.json"), scan)
                    if scan["fault_counts"] or scan["suspects"]:
                        raise RuntimeError("kernel-fault-or-suspect")
                    failed = rec.command(prefix + "failed-units", argv + ["systemctl --failed --no-pager --plain"], timeout=15)[0]
                    if "0 loaded units listed." not in failed:
                        raise RuntimeError("systemd-failed-unit")
                    last_journal = loop_start
                if window is not None and not checkpoint and loop_start - window >= 300:
                    stats = summarize(charging)
                    if stats["positive_current_samples"] < len(charging) // 2 or stats["soc_end"] < stats["soc_start"]:
                        raise RuntimeError("charging-trend-suspect")
                    capture.write_json(args.output / "five-minute.json", {
                        "verdict": "telemetry-clean", "observation_seconds": round(loop_start - window, 3),
                        "statistics": stats})
                    checkpoint = True
                    print("FIVE_MINUTE_TELEMETRY_PASSED", flush=True)
                if window is not None and loop_start - window >= 1500:
                    break
                time.sleep(max(0.05, 5 - (time.monotonic() - loop_start)))
        stats = summarize(charging)
        if stats["positive_current_samples"] < len(charging) // 2 or stats["soc_end"] < stats["soc_start"]:
            raise RuntimeError("charging-trend-suspect")
        result = {"verdict": "bounded-battery-telemetry-passed", "boot_id": args.boot,
                  "observation_seconds": round(loop_start - window, 3), "statistics": stats,
                  "independent_vbus_gate_passed": False, "device_configuration_writes": False}
    except Exception as exc:
        result = {"verdict": "stopped", "reason": str(exc), "boot_id": args.boot,
                  "samples": len(all_samples), "device_configuration_writes": False}
        capture.write_json(args.output / "summary.json", result)
        print("STOP: unplug charger and preserve evidence:", exc, flush=True)
        raise
    capture.write_json(args.output / "summary.json", result)
    print("CHARGING_TELEMETRY_COMPLETE: unplug stage follows", flush=True)


if __name__ == "__main__":
    main()
