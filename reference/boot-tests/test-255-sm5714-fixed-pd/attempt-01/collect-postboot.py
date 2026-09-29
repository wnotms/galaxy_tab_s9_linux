#!/usr/bin/env python3
"""Read-only first-boot Test255 identity, transport and kernel evidence capture."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as p

A = Path(__file__).resolve().parent
p.SERIAL = "gts9wifi-0001"
r = p.Recorder(A / "postboot")
checks = {}


def take(name, script, timeout=20):
    raw, status = r.adb(name, script, timeout, required=False)
    checks[name] = status == 0
    return raw


boot = take("boot-id", "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime")
take("kernel-journal-json", "journalctl -b -k --no-pager -o json", 60)
take("kernel-journal", "journalctl -b -k --no-pager -o short-monotonic", 60)
take("journal-boots", "journalctl --list-boots --no-pager")
take("uname", "uname -a")
take("cmdline", "cat /proc/cmdline")
take("config-hash", "set -o pipefail; zcat /proc/config.gz | sha256sum")
take("notes-hash", "sha256sum /sys/kernel/notes")
take("partitions", "set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done", 75)
take("module-directories", "find /usr/lib/modules -maxdepth 1 -type d -print")
for name, directory in (
    ("modules-current", "/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty"),
    ("modules-test254", "/usr/lib/modules/.gts9-test255-original"),
    ("modules-test252", "/usr/lib/modules/.gts9-test254-original"),
    ("modules-test249", "/usr/lib/modules/.gts9-test252-original"),
):
    take(name, f"find {directory} -type f -exec sha256sum {{}} +", 90)
take("dcc", "zcat /proc/config.gz | grep -E '^(# CONFIG_HVC_DCC is not set|CONFIG_HVC_DCC=)'; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; systemctl is-active serial-getty@hvc0.service || true")
take("typec", "set -e; for f in /sys/class/typec/port0/power_role /sys/class/typec/port0/data_role /sys/class/typec/port0/port_type /sys/class/typec/port0/orientation /sys/class/typec/port0/usb_power_delivery_revision; do printf '%s=' \"$f\"; cat \"$f\"; done; ls -la /sys/class/typec")
take("supplies", "for f in /sys/class/power_supply/sm5714-battery/uevent /sys/class/power_supply/sm5714-usb/uevent; do echo \"$f\"; cat \"$f\"; done")
take("battery", "set -e; for f in capacity temp voltage_now current_now status health; do printf '%s=' \"$f\"; cat /sys/class/power_supply/sm5714-battery/\"$f\"; done")
take("usb", "for f in /sys/class/udc/*/state; do printf '%s=' \"$f\"; cat \"$f\"; done; ip -4 -o addr show; systemctl show ssh gts9-adbd -p ActiveState -p MainPID --no-pager")
take("test253-adbd", "set -e; sha256sum /usr/local/libexec/gts9-adbd-reconnect /usr/libexec/gts9-adbd-run; systemctl show gts9-adbd -p ActiveState -p MainPID -p ExecStart --no-pager")
take("failed-units", "systemctl --failed --no-pager --plain")
take("final-boot", "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime")

raw, status = r.host_adb("adb-devices", "devices", "-l", timeout=15, required=False)
checks["adb-devices"] = status == 0 and "gts9wifi-0001" in raw and "device" in raw
raw, status = r.ssh("ncm-ssh", "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime", timeout=18, required=False)
checks["ncm-ssh"] = status == 0
ip = take("wifi-address", "ip -4 -o addr show wlp1s0")
match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/", ip)
if match:
    raw, status = r.command("wifi-ssh", ["env", "GTS9_DEVICE=" + match.group(1), p.SSH, "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime"], timeout=18, required=False)
    checks["wifi-ssh"] = status == 0
else:
    checks["wifi-ssh"] = False
raw, status = r.ps("windows-usb", p.PS_USB, timeout=25, required=False)
checks["windows-usb"] = status == 0 and not p.has_code43(raw)
raw, status = r.ps("windows-ncm-banner", p.PS_NCM_BOUND_BANNER, timeout=35, required=False)
checks["windows-ncm-banner"] = status == 0 and '"ok":true' in raw.lower()

current = p.evidence.canonical_boot_id(boot.splitlines()[0]) if boot.strip() else None
p.write_json(A / "postboot/capture-status.json", {"boot_id": current, "capture_checks": checks, "all_captures_succeeded": all(checks.values()), "assessment": "identity and safety verdict pending"})
print("first-boot capture complete:", sum(checks.values()), "/", len(checks), "capture gates", flush=True)
