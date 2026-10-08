"""Read-only desktop activity sampling; no governor, OPP or charging writes."""
import os
from pathlib import Path
import time


def process_stat(text):
    fields = text[text.rindex(")") + 2:].split()
    return {"start_ticks": int(fields[19]), "cpu_ticks": int(fields[11]) + int(fields[12])}


def cpu_activity(before, after):
    # guest/guest_nice are already included in user/nice. Do not count twice.
    delta = [b - a for a, b in zip(before[:8], after[:8])]
    if len(delta) != 8 or any(value < 0 for value in delta) or sum(delta) <= 0:
        raise ValueError("CPU counter interval is not valid")
    return 100 * (sum(delta) - delta[3] - delta[4]) / sum(delta)


def process_activity(before, after, seconds, ticks_per_second):
    if seconds <= 0 or ticks_per_second <= 0:
        raise ValueError("activity interval must be positive")
    result = []
    for pid, current in after.items():
        old = before.get(pid)
        if old is None or old["start_ticks"] != current["start_ticks"]:
            continue
        ticks = current["cpu_ticks"] - old["cpu_ticks"]
        if ticks < 0:
            continue
        result.append({"pid": pid, "comm": current["comm"],
                       "one_cpu_percent": 100 * ticks / ticks_per_second / seconds})
    return sorted(result, key=lambda row: row["one_cpu_percent"], reverse=True)


def safe_pack(battery):
    return battery["health"] == "Good" and 0 <= int(battery["temp"]) < 420


def snapshot():
    def read(path):
        return Path(path).read_text().strip()

    battery = Path("/sys/class/power_supply/sm5714-battery")
    result = {
        "monotonic": time.monotonic(),
        "boot_id": read("/proc/sys/kernel/random/boot_id"),
        "cpu_ticks": [int(s) for s in read("/proc/stat").splitlines()[0].split()[1:]],
        "battery": {n: read(battery / n) for n in ("capacity", "temp", "health", "status", "current_now", "voltage_now")},
        "processes": {}, "thermal_mC": {}, "gpu": {}, "cpu7_idle_us": {}, "backlight": {},
    }
    # Read process names/counters only, never command lines or environment.
    for process in Path("/proc").glob("[0-9]*"):
        try:
            text = read(process / "stat")
            name = text[text.index("(") + 1:text.rindex(")")]
            result["processes"][process.name] = dict(process_stat(text), comm=name)
        except (OSError, ValueError, IndexError):
            pass  # exited/reused process will not qualify for a delta
    for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
        try:
            name = read(zone / "type")
            if name.startswith(("cpu", "gpuss")):
                result["thermal_mC"][name] = int(read(zone / "temp"))
        except (OSError, ValueError):
            pass  # unavailable sensor is omitted, never substituted with zero
    gpu = Path("/sys/class/devfreq/3d00000.gpu")
    for name in ("cur_freq", "governor", "trans_stat"):
        try:
            result["gpu"][name] = read(gpu / name)
        except OSError:
            pass
    for name in ("runtime_status", "runtime_active_time", "runtime_suspended_time"):
        try:
            result["gpu"][name] = read(gpu / "device/power" / name)
        except OSError:
            pass
    for state in Path("/sys/devices/system/cpu/cpu7/cpuidle").glob("state*"):
        try:
            result["cpu7_idle_us"][read(state / "name")] = int(read(state / "time"))
        except (OSError, ValueError):
            pass
    for device in Path("/sys/class/backlight").glob("*"):
        try:
            result["backlight"][device.name] = {n: read(device / n) for n in ("brightness", "max_brightness")}
        except OSError:
            pass
    return result


def interval(before, after):
    if before["boot_id"] != after["boot_id"]:
        raise ValueError("boot changed during interval")
    seconds = after["monotonic"] - before["monotonic"]
    return {
        "seconds": seconds,
        "CPU_capacity_activity_percent": cpu_activity(before["cpu_ticks"], after["cpu_ticks"]),
        "top_processes": process_activity(before["processes"], after["processes"], seconds, os.sysconf("SC_CLK_TCK"))[:15],
    }
