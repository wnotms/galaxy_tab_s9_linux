#!/usr/bin/env python3
"""Read-only Test255 identity gates over Wi-Fi for direct PD telemetry."""

import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as capture
import production_stability_evidence as evidence
import sm5714_pd_telemetry as telemetry

A = Path(__file__).resolve().parent
PARENT = A.parent
OLD = "a5b8b87f1487422a9035a1db74f85667"
BOOT = "d745248e6a164243b9ccc5e6ede21fb2"
CONFIG = "cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f"
NOTES = "fb3d249642e900d9bb591fb629c1865b370b50098d44970b986cc793f45c160c"
WIFI = "10.191.121.37"
phase = sys.argv[1] if len(sys.argv) > 1 else "preflight"
if phase not in {"preflight", "final"}:
    raise SystemExit("phase must be preflight or final")
capture.SERIAL = "gts9wifi-0001"
if (A / phase).exists():
    raise SystemExit("refusing to reuse an evidence directory")
r = capture.Recorder(A / phase)
def remote(name, command, timeout=15):
    return r.command(name, ["env", "GTS9_DEVICE=" + WIFI, capture.SSH, command], timeout=timeout)

checks = {}


def check(name, value):
    checks[name] = bool(value)


def read_hashes(raw, prefix):
    return capture.parse_hashes(raw, prefix)


try:
    state = remote("boot-and-uptime", "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime")[0]
    check("boot-id", evidence.canonical_boot_id(state.splitlines()[0]) == BOOT)
    uptime = float(state.splitlines()[1].split()[0])
    raw = remote("kernel-json", "journalctl -b -k --no-pager -o json", 60)[0]
    remote("kernel-journal", "journalctl -b -k --no-pager -o short-monotonic", 60)
    baseline_journal = ROOT / "reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt"
    accepted = {x["MESSAGE"] for x in map(json.loads, baseline_journal.read_text().splitlines())
                if int(x.get("PRIORITY", 7)) <= 3}
    scan = evidence.inspect_journal(raw, BOOT, accepted, accepted_startup_variants=True,
                                   startup_iova_range=(0xb8000000, 0xbab00000),
                                   accepted_qca_cycles=True, observed_uptime=uptime)
    capture.write_json(r.folder / "kernel-scan.json", scan)
    check("no-kernel-fault", not scan["fault_counts"] and not scan["suspects"])
    history = remote("boot-history", "journalctl --list-boots --no-pager")[0]
    ids = evidence.boot_list(history)
    check("owner-reboot-attribution", OLD in ids and ids[ids.index(OLD) + 1:] == [BOOT])
    remote("uname", "uname -a")
    cmdline = remote("cmdline", "cat /proc/cmdline")[0]
    check("cmdline-unchanged", cmdline.strip() == (PARENT / "attempt-01/preflight/cmdline.txt").read_text().strip())
    config = remote("embedded-config", "zcat /proc/config.gz", 30)[0]
    check("exact-embedded-config", hashlib.sha256(config.encode()).hexdigest() == CONFIG)
    check("kernel-notes", remote("notes-hash", "sha256sum /sys/kernel/notes")[0].split()[0] == NOTES)
    check("dcc-off", "# CONFIG_HVC_DCC is not set" in config)
    dcc = remote("dcc-state", "set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; if systemctl is-active --quiet serial-getty@hvc0.service; then exit 1; fi; echo DCC-absent")[0]
    check("dcc-nodes-getty-absent", dcc.strip() == "DCC-absent")
    check("stage1-container-config-preserved", all(f"{name}=y" in config for name in
          ("CONFIG_BATTERY_SM5714", "CONFIG_QCOM_SPMI_ADC5_GEN3", "CONFIG_USER_NS", "CONFIG_POSIX_MQUEUE")))
    parts = read_hashes(remote("partitions", "set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done", 75)[0], "/dev/disk/by-partlabel/")
    expected_parts = json.loads((PARENT / "attempt-01/install/summary.json").read_text())["partitions"]
    check("five-partitions", parts == expected_parts)
    module_manifest = json.loads((PARENT / "validation/module-hashes.json").read_text())
    current = read_hashes(remote("modules-current", "find /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty -type f -exec sha256sum {} +", 90)[0], "/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/")
    check("181-candidate-modules", len(current) == 181 and current == module_manifest)
    for name, directory, previous in (
        ("test254", ".gts9-test255-original", "modules-test254.txt"),
        ("test252", ".gts9-test254-original", "modules-test252.txt"),
        ("test249", ".gts9-test252-original", "modules-test249.txt"),
    ):
        prefix = f"/usr/lib/modules/{directory}/"
        actual = read_hashes(remote(f"modules-{name}", f"find {prefix} -type f -exec sha256sum {{}} +", 90)[0], prefix)
        original = read_hashes((PARENT / "attempt-01/postboot" / previous).read_text(), prefix)
        check(f"181-{name}-rollback-modules", len(actual) == 181 and actual == original)
    directories = remote("module-directories", "find /usr/lib/modules -maxdepth 1 -type d -print")[0]
    check("module-directories-unchanged", set(directories.splitlines()) ==
          set((PARENT / "attempt-01/postboot/module-directories.txt").read_text().splitlines()))

    original_settings = read_hashes((PARENT / "attempt-01/preflight/protected-settings.txt").read_text(), "/")
    command = "set -e; sha256sum " + " ".join(shlex.quote("/" + name) for name in original_settings)
    settings = read_hashes(remote("protected-settings", command, 30)[0], "/")
    check("protected-settings-unchanged", settings == original_settings)
    adbd = remote("test253-adbd", "set -e; sha256sum /usr/local/libexec/gts9-adbd-reconnect /usr/libexec/gts9-adbd-run; systemctl show gts9-adbd -p ActiveState -p MainPID -p ExecStart --no-pager")[0]
    check("test253-adbd-active", "ActiveState=active" in adbd and
          "053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5" in adbd and
          "d2e840b5ef9723cde15da7a889a79d0700a5d54aabd54873c8b602694a0dedc3" in adbd)
    typec = remote("typec", "set -e; for f in power_role data_role port_type orientation power_operation_mode; do printf '%s=' \"$f\"; cat /sys/class/typec/port0/\"$f\"; done")[0]
    check("sink-device", "power_role=[sink]" in typec and "data_role=[device]" in typec and "port_type=[sink]" in typec)
    supplies = remote("power-supplies", "set -e; for f in /sys/class/power_supply/*/uevent; do echo \"$f\"; cat \"$f\"; done")[0]
    sample = telemetry.parse_sample(remote("telemetry", telemetry.SAMPLE_COMMAND)[0])
    check("telemetry-safe", telemetry.assess(sample, BOOT) is None)
    if phase == "preflight":
        check("battery-only-before-charger", sample["usb_online"] == 0 and
              sample["tcpm_online"] == 0 and sample["battery_status"] == "Discharging" and
              sample["battery_current_ua"] < 0)
    check("battery-safe", "POWER_SUPPLY_HEALTH=Good" in supplies and
          int(re.search(r"POWER_SUPPLY_TEMP=(\d+)", supplies)[1]) < 450 and
          int(re.search(r"POWER_SUPPLY_VOLTAGE_NOW=(\d+)", supplies)[1]) <= 4440000)
    check("no-failed-units", "0 loaded units listed." in remote("failed-units", "systemctl --failed --no-pager --plain")[0])
    remote("usb-state", "for f in /sys/class/udc/*/state; do printf '%s=' \"$f\"; cat \"$f\"; done; ip -4 -o addr show")
    end = remote("final-boot", "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime")[0]
    check("boot-unchanged-during-capture", evidence.canonical_boot_id(end.splitlines()[0]) == BOOT)
    result = {"verdict": "passed" if all(checks.values()) else "stopped", "checks": checks,
              "boot_id": BOOT, "start_uptime_seconds": uptime,
              "end_uptime_seconds": float(end.splitlines()[1].split()[0]),
              "kernel_scan": scan, "config_sha256": CONFIG, "notes_sha256": NOTES,
              "partitions": parts, "modules": len(current), "device_writes": False,
              "battery_telemetry": sample,
              "scope": "exact installed candidate identity over Wi-Fi; direct PD telemetry scope"}
except Exception as exc:
    result = {"verdict": "stopped", "error": str(exc), "checks": checks, "device_writes": False}
    capture.write_json(r.folder / "verdict.json", result)
    raise
capture.write_json(r.folder / "verdict.json", result)
print(phase, result["verdict"], len(checks), "gates", flush=True)
if result["verdict"] != "passed":
    raise SystemExit(1)
