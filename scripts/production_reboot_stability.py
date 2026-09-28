#!/usr/bin/env python3
"""Test250: unchanged Test249 production, 20 attributed ordinary warm reboots.

No build, flash, partition write, kernel argument, service or USB change exists
in this runner. `preflight` is read-only; `run` issues `systemctl reboot` only
after the recorded production identity and transport gates have passed.
"""

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import time

import production_stability_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
TEST250_ROOT = ROOT / "reference/boot-tests/test-250-production-warm-reboot"
P = TEST250_ROOT
BASE = ROOT / "reference/boot-tests/test-249-no-dcc-production"
ADB = "/mnt/d/android/platform-tools/adb.exe"
SERIAL = "gts9wifi-0001"
SSH = str(ROOT / "scripts/gts9-ssh.sh")
POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
RELEASE = "7.2.0-rc3-gts9wifi-dirty"
MODULE_ROOT = "/usr/lib/modules/" + RELEASE
ROUNDS = 20
WINDOW = 150
WAIT_BOOT = 180
WINDOW_POLL = 5
PS_BANNER = r'''$c = New-Object System.Net.Sockets.TcpClient
try {
  $a = $c.BeginConnect('169.254.42.1', 22, $null, $null)
  if (-not $a.AsyncWaitHandle.WaitOne(5000)) { throw 'TCP connect timeout' }
  $c.EndConnect($a)
  $s = $c.GetStream(); $s.ReadTimeout = 5000
  $b = New-Object byte[] 256
  $n = $s.Read($b, 0, $b.Length)
  [Console]::Write([Text.Encoding]::ASCII.GetString($b, 0, $n))
} finally { $c.Close() }
'''
PS_NCM_BOUND_BANNER = r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$report = [ordered]@{ok=$false; interface_index=$null; source_ipv4=$null;
  local_endpoint=$null; remote_endpoint=$null; socket_interface=$null; banner=$null; error=$null}
$c=$null
try {
  $nic = @(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and
    $_.PnPDeviceID -match 'VID_0525&PID_A4A7&MI_00' -and $_.InterfaceDescription -match 'NCM' })
  if ($nic.Count -ne 1) { throw 'Production NCM interface not unique/up' }
  $ip = @(Get-NetIPAddress -InterfaceIndex $nic[0].ifIndex -AddressFamily IPv4 |
    Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -like '169.254.*' })
  if ($ip.Count -ne 1) { throw 'Production NCM IPv4 not unique/preferred' }
  $report.interface_index=[int]$nic[0].ifIndex; $report.source_ipv4=$ip[0].IPAddress
  $c = New-Object System.Net.Sockets.TcpClient([System.Net.Sockets.AddressFamily]::InterNetwork)
  $c.Client.Bind([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Parse($ip[0].IPAddress),0))
  # Winsock IP_UNICAST_IF=31; setting uses network-order index, getting uses host order.
  $c.Client.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::IP,
    [System.Net.Sockets.SocketOptionName]31,[System.Net.IPAddress]::HostToNetworkOrder([int]$nic[0].ifIndex))
  $report.socket_interface=$c.Client.GetSocketOption([System.Net.Sockets.SocketOptionLevel]::IP,
    [System.Net.Sockets.SocketOptionName]31)
  if ($report.socket_interface -ne $report.interface_index) { throw 'Wrong socket interface' }
  $a=$c.BeginConnect('169.254.42.1',22,$null,$null)
  if (-not $a.AsyncWaitHandle.WaitOne(5000)) { throw 'TCP connect timeout' }
  $c.EndConnect($a)
  $report.local_endpoint=$c.Client.LocalEndPoint.ToString()
  $report.remote_endpoint=$c.Client.RemoteEndPoint.ToString()
  $s=$c.GetStream(); $s.ReadTimeout=5000
  $b=New-Object byte[] 256; $n=$s.Read($b,0,$b.Length)
  $report.banner=[Text.Encoding]::ASCII.GetString($b,0,$n)
  if (-not $report.banner.StartsWith('SSH-2.0-')) { throw 'Invalid SSH banner' }
  $report.ok=$true
} catch { $report.error=$_.Exception.Message }
finally { if ($null -ne $c) { $c.Close() } }
[Console]::Write(($report | ConvertTo-Json -Compress))
if (-not $report.ok) { exit 1 }
'''
PS_USB = r'''Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object { $_.InstanceId -match 'VID_0525|VID_18D1|VID_0000&PID_0002' } |
  ForEach-Object {
    $problem = Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_ProblemCode' -ErrorAction SilentlyContinue
    [PSCustomObject]@{Status=$_.Status; ProblemCode=$problem.Data; Class=$_.Class;
      FriendlyName=$_.FriendlyName; InstanceId=$_.InstanceId}
  } | Format-List
Get-NetAdapter -ErrorAction SilentlyContinue |
  Where-Object { $_.InterfaceDescription -match 'NCM|USB' } |
  Select-Object Name, Status, InterfaceDescription | Format-List
'''
PS_PNP_EVENTS = r'''Get-WinEvent -FilterHashtable @{
  LogName='Microsoft-Windows-Kernel-PnP/Configuration'
  StartTime=(Get-Date).AddMinutes(-30)
} -MaxEvents 100 -ErrorAction SilentlyContinue |
  Where-Object { $_.Message -match 'VID_0000&PID_0002|DEVICE_DESCRIPTOR_FAILURE|VID_0525' } |
  Select-Object TimeCreated, Id, ProviderName, Message | Format-List
'''


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def one_line(text):
    lines = text.replace("\r", "").strip().splitlines()
    if len(lines) != 1:
        raise ValueError(f"expected one line, got {len(lines)}")
    return lines[0].strip()


class CaptureError(RuntimeError):
    pass


class KernelEvidenceError(CaptureError):
    def __init__(self, message, scan):
        super().__init__(message)
        self.scan = scan


def has_code43(text):
    return re.search(r"^\s*ProblemCode\s*:\s*43\s*$", text, re.M) is not None


class Recorder:
    def __init__(self, folder):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)

    def command(self, name, argv, timeout=15, required=True):
        target = self.folder / (name + ".txt")
        if target.exists():
            raise CaptureError(f"refusing to overwrite {target}")
        started = now()
        try:
            result = subprocess.run(argv, capture_output=True, timeout=timeout)
            stdout, stderr, status = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, status = exc.stdout or b"", exc.stderr or b"", "timeout"
        target.write_bytes(stdout)
        (self.folder / (name + ".stderr")).write_bytes(stderr)
        write_json(self.folder / (name + ".command.json"),
                   {"argv": argv, "started_utc": started, "ended_utc": now(), "status": status})
        if required and status != 0:
            raise CaptureError(f"{name}: status={status}; {stderr[-300:]!r}")
        return stdout.decode(errors="replace").replace("\r", ""), status

    def adb(self, name, script, timeout=15, required=True):
        return self.command(name, [ADB, "-s", SERIAL, "shell", script], timeout, required)

    def host_adb(self, name, *args, timeout=12, required=True):
        return self.command(name, [ADB, *args], timeout, required)

    def ssh(self, name, script, timeout=15, required=True):
        return self.command(name, [SSH, script], timeout, required)

    def ps(self, name, script, timeout=20, required=True):
        return self.command(name, [POWERSHELL, "-NoProfile", "-Command", script], timeout, required)


def checked_file(path, manifest):
    relative = str(path.relative_to(BASE))
    meta = manifest[relative]
    content = path.read_bytes()
    if len(content) != meta["bytes"] or hashlib.sha256(content).hexdigest() != meta["sha256"]:
        raise ValueError(f"Test249 manifest mismatch: {relative}")
    return content


def baseline():
    manifest = json.loads((BASE / "SHA256.json").read_text())
    names = ("final-acceptance/identity.json", "final-acceptance/partitions.txt",
             "final-acceptance/removed-capabilities.txt", "final-acceptance/profile.txt",
             "final-acceptance/kernel-json.txt", "validation/candidate-module-checksums.txt",
             "validation/diagnostic-absence.json")
    data = {name: checked_file(BASE / name, manifest) for name in names}
    identity = json.loads(data["final-acceptance/identity.json"])
    removed = data["final-acceptance/removed-capabilities.txt"].decode().splitlines()
    config = removed[1].split()[0]
    partition_rows = data["final-acceptance/partitions.txt"].decode().splitlines()[1:-1]
    partitions = {row.split()[1].rsplit("/", 1)[-1]: row.split()[0] for row in partition_rows}
    modules = {row.split(maxsplit=1)[1]: row.split()[0] for row in
               data["validation/candidate-module-checksums.txt"].decode().splitlines()}
    old_rows = [json.loads(line) for line in data["final-acceptance/kernel-json.txt"].decode().splitlines()]
    known_priority3 = {row["MESSAGE"] for row in old_rows if int(row.get("PRIORITY", 7)) == 3}
    cycle_approved = P == TEST250_ROOT / "attempt-05"
    region_backed = P in (TEST250_ROOT / "attempt-03", TEST250_ROOT / "attempt-04", TEST250_ROOT / "attempt-05")
    qca_approved = P == TEST250_ROOT / "attempt-04" or cycle_approved
    variants = P in (TEST250_ROOT / "attempt-02", TEST250_ROOT / "attempt-03", TEST250_ROOT / "attempt-04", TEST250_ROOT / "attempt-05")
    if qca_approved and not cycle_approved:
        policy = json.loads((P / "policy.json").read_text())
        if policy != {"owner_authorization": "adopted post-attempt03 bounded classification",
                      "message": evidence.QCA_BAUDRATE_EVENT, "maximum_count": 1,
                      "priority": 3, "maximum_source_seconds": 20,
                      "setup_deadline_seconds": 5, "soc": "wcn6855",
                      "powered_controller_required": True,
                      "other_bluetooth_errors_stop": True, "rounds": ROUNDS,
                      "observation_seconds": WINDOW, "production_changes": False}:
            raise ValueError("approved QCA classification registration changed")
    if cycle_approved:
        policy = json.loads((P / "policy.json").read_text())
        if policy != {"owner_authorization": "adopted round05 bounded cycle classification",
                      "classification": "bounded-per-setup-cycle",
                      "message": evidence.QCA_BAUDRATE_EVENT, "maximum_count": 2,
                      "maximum_setup_count": 3, "maximum_per_setup_count": 1,
                      "priority": 3, "maximum_source_seconds": 20,
                      "maximum_completion_source_seconds": 20,
                      "setup_deadline_seconds": 5, "soc": "wcn6855",
                      "powered_controller_required": True,
                      "other_bluetooth_errors_stop": True, "rounds": ROUNDS,
                      "observation_seconds": WINDOW, "production_changes": False}:
            raise ValueError("approved QCA cycle classification registration changed")
    iova_range = (0xb8000000, 0xb8200000)
    if region_backed:
        checked = json.loads(checked_file(BASE / "validation/build-check.json", manifest))
        name = "out/kernel-no-dcc-production/sm8550-samsung-gts9wifi.dtb"
        meta = checked["artifacts"][name]
        content = (ROOT / name).read_bytes()
        if len(content) != meta["bytes"] or hashlib.sha256(content).hexdigest() != meta["sha256"]:
            raise ValueError("accepted Test249 DTB artifact identity changed")
        reg = subprocess.check_output(["fdtget", "-t", "x", str(ROOT / name),
                                       "/reserved-memory/splash_region", "reg"])
        cells = [int(x, 16) for x in reg.decode().split()]
        if len(cells) != 4:
            raise ValueError("invalid accepted splash-region reg")
        start, size = (cells[0] << 32) | cells[1], (cells[2] << 32) | cells[3]
        iova_range = start, start + size
        if iova_range != (0xb8000000, 0xbab00000):
            raise ValueError("accepted Test249 splash-region bounds changed")
    if variants:
        accepted_twrp = checked_file(BASE / "production-twrp-continued/kernel-follow.jsonl", manifest)
        for raw in (accepted_twrp.decode(), data["final-acceptance/kernel-json.txt"].decode()):
            rows = [json.loads(line) for line in raw.splitlines()]
            counts = {}
            for row in rows:
                kind = evidence.startup_variant(row, iova_range)
                if kind:
                    counts[kind] = counts.get(kind, 0) + 1
            if counts != {"boot_register_warning": 1, "smmu_context_fault": 10,
                          "smmu_fsr": 10, "smmu_fsynr": 10}:
                raise ValueError("accepted Test249 startup-class references changed")
    accepted_cmdline = data["final-acceptance/profile.txt"].decode().splitlines()[1].split()
    owned_cmdline = (ROOT / "boot/cmdline.example.txt").read_text().split()
    if not all(token in accepted_cmdline for token in owned_cmdline):
        raise ValueError("repository production cmdline differs from Test249 acceptance")
    if len(partitions) != 5 or len(modules) != 181 or not identity["DCC_path_absent"]:
        raise ValueError("incomplete Test249 accepted baseline")
    return {"config_sha256": config, "notes_sha256": identity["notes_sha256"],
            "partitions": partitions, "modules": modules, "known_priority3": known_priority3,
            "accepted_startup_variants": variants,
            "startup_iova_range": iova_range, "ncm_source_bound": region_backed,
            "accepted_qca_baudrate": qca_approved,
            "accepted_qca_cycles": cycle_approved,
            "owned_cmdline_tokens": owned_cmdline,
            "test249_manifest_sha256": hashlib.sha256((BASE / "SHA256.json").read_bytes()).hexdigest()}


def inspect(raw, boot, base, observed_uptime=None):
    return evidence.inspect_journal(raw, boot, base["known_priority3"],
                                    accepted_startup_variants=base.get("accepted_startup_variants", False),
                                    startup_iova_range=base.get("startup_iova_range", (0xb8000000, 0xb8200000)),
                                    accepted_qca_baudrate=base.get("accepted_qca_baudrate", False),
                                    accepted_qca_cycles=base.get("accepted_qca_cycles", False),
                                    observed_uptime=observed_uptime)


def parse_bluetooth_health(raw, boot):
    lines = raw.strip().splitlines()
    keys = ("boot_id", "uptime", "bluetooth", "address", "controllers")
    if len(lines) < 7 or lines[5] != "controller:" or any(
            not line.startswith(key + "=") for line, key in zip(lines[:5], keys)):
        raise ValueError("incomplete Bluetooth health evidence")
    fields = {key: lines[index].split("=", 1)[1].strip() for index, key in enumerate(keys)}
    controller = [line for line in lines[6:] if re.fullmatch(
        r"Controller (?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2} \(public\)", line)]
    powered = [line.strip() for line in lines[6:] if line.strip().startswith("Powered:")]
    observed_boot = evidence.canonical_boot_id(fields["boot_id"])
    uptime = float(fields["uptime"].split()[0])
    healthy = (observed_boot == boot and fields["bluetooth"] == "active" and
               fields["address"] == "active" and fields["controllers"].split() == ["hci0"] and
               len(controller) == 1 and powered == ["Powered: yes"] and uptime >= 0)
    return {"boot_id": observed_boot, "uptime_seconds": uptime, "healthy": healthy,
            "bluetooth_service": fields["bluetooth"], "address_service": fields["address"],
            "controllers": fields["controllers"].split(), "powered": powered == ["Powered: yes"],
            "controller": controller[0] if len(controller) == 1 else None}


def bluetooth_health(rec, boot, prefix=""):
    raw = rec.adb(prefix + "bluetooth-state",
        "printf 'boot_id='; cat /proc/sys/kernel/random/boot_id; "
        "printf 'uptime='; cat /proc/uptime; "
        "printf 'bluetooth='; systemctl is-active bluetooth.service || true; "
        "printf 'address='; systemctl is-active gts9-bluetooth-address.service || true; "
        "printf 'controllers='; ls /sys/class/bluetooth | tr '\\n' ' '; echo; "
        "echo controller:; timeout 8 bluetoothctl show", 15)[0]
    report = parse_bluetooth_health(raw, boot)
    write_json(rec.folder / (prefix + "bluetooth-health.json"), report)
    if not report["healthy"]:
        raise CaptureError("same-boot powered Bluetooth controller/units not healthy")
    return report


def parse_hashes(text, root):
    result = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            raise ValueError(f"malformed hash row: {line[:90]}")
        path = parts[1].strip()
        if not path.startswith(root):
            raise ValueError(f"unexpected hash path: {path}")
        key = path[len(root):].lstrip("/")
        if key in result:
            raise ValueError(f"duplicate hash path: {key}")
        result[key] = parts[0]
    return result


def production_state(rec, base, prefix="", full=False):
    """Capture a boot-bound, read-only production identity and health snapshot."""
    def adb(name, script, timeout=15):
        return rec.adb(prefix + name, script, timeout)[0]

    boot = evidence.canonical_boot_id(one_line(adb("boot-id", "cat /proc/sys/kernel/random/boot_id")))
    uname = adb("uname", "uname -a")
    cmdline = adb("cmdline", "cat /proc/cmdline")
    uptime = float(one_line(adb("uptime", "cat /proc/uptime")).split()[0])
    notes = one_line(adb("kernel-notes", "sha256sum /sys/kernel/notes")).split()[0]
    if full:
        encoded_notes = adb("kernel-notes-base64", "base64 /sys/kernel/notes")
        decoded_notes = base64.b64decode("".join(encoded_notes.split()), validate=True)
        if hashlib.sha256(decoded_notes).hexdigest() != notes:
            raise CaptureError("captured kernel build notes differ from device SHA-256")
        (rec.folder / (prefix + "kernel-notes.bin")).write_bytes(decoded_notes)
    config_hash = one_line(adb("config-sha256", "zcat /proc/config.gz | sha256sum")).split()[0]
    config = adb("embedded-config", "zcat /proc/config.gz", 25) if full else ""
    dcc = adb("dcc-state", "printf 'dev='; test -e /dev/hvc0 && echo present || echo absent; "
              "printf 'sysfs='; test -e /sys/class/tty/hvc0 && echo present || echo absent; "
              "printf 'getty='; systemctl is-active serial-getty@hvc0.service || true; "
              "printf 'symbol='; grep -wE 'hvc_dcc0_put_chars|hvc_write' /proc/kallsyms || true")
    profile = adb("production-profile", "cat /proc/sys/kernel/watchdog "
                  "/proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic "
                  "/proc/sys/kernel/panic /sys/module/ramoops/parameters/ecc")
    failed = adb("systemd-failed", "systemctl --failed --no-legend --plain --no-pager")
    usb = adb("usb-state", "for f in /sys/class/udc/*/state; do echo $f; cat $f; done; "
              "ip -br addr show usb0; ss -lnt; "
              "systemctl is-active ssh.service gts9-usb-acm.service gts9-adbd.service || true")
    bluetooth = bluetooth_health(rec, boot, prefix) if base.get("accepted_qca_baudrate") else None
    if base.get("ncm_source_bound"):
        reg = base64.b64decode("".join(adb("splash-region-base64", "base64 "
            "/sys/firmware/devicetree/base/reserved-memory/splash_region/reg").split()), validate=True)
        cells = struct.unpack(">4I", reg)
        start, size = (cells[0] << 32) | cells[1], (cells[2] << 32) | cells[3]
        if (start, start + size) != base["startup_iova_range"]:
            raise CaptureError("live DTB splash-region identity differs from Test249")
    if full:
        parts = adb("partitions", "for n in boot vendor_boot init_boot dtbo vbmeta; "
                    "do sha256sum /dev/disk/by-partlabel/$n; done", 40)
        modules = adb("module-hashes", f"find {MODULE_ROOT} -type f -exec sha256sum {{}} +", 45)
        backups = adb("module-backups", "found=$(find /usr/lib/modules -maxdepth 1 -type d "
                      "-name '.gts9-test*' -print); "
                      "test -z \"$found\" && echo backups_absent || { printf '%s\\n' \"$found\"; exit 1; }")
        actual_parts = parse_hashes(parts, "/dev/disk/by-partlabel/")
        actual_modules = parse_hashes(modules, MODULE_ROOT + "/")
        if actual_parts != base["partitions"] or actual_modules != base["modules"] or backups.strip() != "backups_absent":
            raise CaptureError("Test249 partition/module baseline mismatch")
    after = evidence.canonical_boot_id(one_line(adb("boot-id-confirm", "cat /proc/sys/kernel/random/boot_id")))
    dcc_lines = dcc.splitlines()
    # The final `symbol=` marker has no value when grep finds no DCC write
    # symbol. It is intentionally a fourth line, not evidence of a symbol.
    dcc_ok = dcc_lines == ["dev=absent", "sysfs=absent", "getty=inactive", "symbol="]
    expected_config = config_hash == base["config_sha256"]
    if full:
        expected_config = expected_config and hashlib.sha256(config.encode()).hexdigest() == config_hash
    forbidden = ("csdlock_debug=", "gts9_lastactivity=", "irqchip.gicv3_pseudo_nmi=",
                 "gts9_watchdog_debug=", "softlockup_panic=1", "cpuidle.off=1")
    tokens = cmdline.split()
    profile_ok = (profile.splitlines() == ["0"] * 5 and
                  all(token in tokens for token in base.get("owned_cmdline_tokens", ())) and
                  not any(token.startswith(prefix) for token in tokens for prefix in forbidden))
    config_ok = (not full or all(x in config for x in ("# CONFIG_HVC_DCC is not set",
                  "# CONFIG_ARM64_PSEUDO_NMI is not set", "# CONFIG_CSD_LOCK_WAIT_DEBUG is not set")))
    ok = (boot == after and RELEASE in uname and notes == base["notes_sha256"] and
          expected_config and config_ok and dcc_ok and profile_ok and not failed.strip())
    report = {"boot_id": boot, "uptime_seconds": uptime, "uname": uname.strip(),
              "config_sha256": config_hash, "notes_sha256": notes, "dcc_absent": dcc_ok,
              "profile_ok": profile_ok, "failed_units": failed.splitlines(),
              "partitions_modules_checked": full, "identity_ok": ok,
              "usb_device_state": usb.strip()}
    if bluetooth is not None:
        report["bluetooth_health"] = bluetooth
    write_json(rec.folder / (prefix + "production-state.json"), report)
    if not ok:
        raise CaptureError("current device is not accepted Test249 production or has failed units")
    return report


def bound_banner_ok(raw):
    row = json.loads(raw)
    index = row.get("interface_index")
    source = row.get("source_ipv4", "")
    return (row.get("ok") is True and isinstance(index, int) and index > 0 and
            row.get("socket_interface") == index and source.startswith("169.254.") and
            row.get("local_endpoint", "").startswith(source + ":") and
            row.get("remote_endpoint") == "169.254.42.1:22" and
            row.get("banner", "").startswith("SSH-2.0-"))


def transport(rec, boot, prefix="", source_bound=False):
    adb_text, adb_rc = rec.host_adb(prefix + "adb-state", "devices", "-l", required=False)
    adb_ok = adb_rc == 0 and re.search(rf"^{SERIAL}\s+device\b", adb_text, re.M) is not None
    pnp, _ = rec.ps(prefix + "windows-usb-state", PS_USB)
    code43 = has_code43(pnp)
    if code43:
        rec.ps(prefix + "windows-pnp-events", PS_PNP_EVENTS, required=False)
        report = {"adb_ok": adb_ok, "ssh_ok": False, "ncm_banner_ok": False,
                  "ncm_initial_failure": False, "code43": True}
        write_json(rec.folder / (prefix + "transport.json"), report)
        return report
    ncm_initial_failure = False
    banner_ok = False
    first_failure_utc = None
    recovery_utc = None
    recovery_seconds = None
    started = time.monotonic()
    for attempt in range(3):
        banner, status = rec.ps(prefix + f"windows-ssh-banner-{attempt}",
                                PS_NCM_BOUND_BANNER if source_bound else PS_BANNER,
                                timeout=20 if source_bound else 12, required=False)
        if status == 0 and (bound_banner_ok(banner) if source_bound else banner.startswith("SSH-2.0-")):
            banner_ok = True
            recovery_utc = now() if ncm_initial_failure else None
            recovery_seconds = round(time.monotonic() - started, 3) if recovery_utc else None
            break
        ncm_initial_failure = True
        if first_failure_utc is None:
            first_failure_utc = now()
        if attempt < 2:
            time.sleep(10)
    ssh_text, ssh_rc = rec.ssh(prefix + "ssh-state", "cat /proc/sys/kernel/random/boot_id", timeout=18, required=False)
    ssh_ok = ssh_rc == 0 and evidence.canonical_boot_id(ssh_text) == boot if ssh_text.strip() else False
    report = {"adb_ok": adb_ok, "ssh_ok": ssh_ok, "ncm_banner_ok": banner_ok,
              "ncm_initial_failure": ncm_initial_failure, "code43": bool(code43),
              "ncm_first_failure_utc": first_failure_utc, "ncm_recovery_utc": recovery_utc,
              "ncm_recovery_seconds_from_first_attempt": recovery_seconds}
    report["ncm_source_bound"] = source_bound
    write_json(rec.folder / (prefix + "transport.json"), report)
    return report


def journal(rec, boot, prefix=""):
    boot = evidence.canonical_boot_id(boot)
    raw = rec.adb(prefix + "kernel-journal-json", f"journalctl -b {boot} -k --no-pager -o json", 35)[0]
    rec.adb(prefix + "kernel-journal", f"journalctl -b {boot} -k --no-pager -o short-monotonic", 35)
    return raw


def status_report(rec, base, prefix="", full=False):
    state = production_state(rec, base, prefix, full)
    history = rec.adb(prefix + "boots", "journalctl --list-boots --no-pager", 25)[0]
    if evidence.boot_list(history)[-1] != evidence.canonical_boot_id(state["boot_id"]):
        raise CaptureError("current boot is not last in persistent journal")
    raw = journal(rec, state["boot_id"], prefix)
    inspected = inspect(raw, state["boot_id"], base)
    write_json(rec.folder / (prefix + "journal-analysis.json"), inspected)
    if inspected["fault_counts"] or inspected["suspects"]:
        raise CaptureError("current boot has kernel failure or suspect messages")
    link = transport(rec, state["boot_id"], prefix, source_bound=base.get("ncm_source_bound", False))
    final_boot = evidence.canonical_boot_id(one_line(rec.adb(prefix + "final-boot-id",
                                                   "cat /proc/sys/kernel/random/boot_id")[0]))
    if final_boot != state["boot_id"]:
        raise CaptureError("boot changed during production status capture")
    if not (link["adb_ok"] and link["ssh_ok"] and link["ncm_banner_ok"]) or link["code43"] or link["ncm_initial_failure"]:
        raise CaptureError("production transport not clean")
    return state, history, inspected, link


def assert_registration_pushed():
    if subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip() != "test":
        raise CaptureError("Test250 physical runner requires the test branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
    remote = subprocess.check_output(["git", "rev-parse", "origin/test"], cwd=ROOT).strip()
    if head != remote:
        raise CaptureError("Test250 runner commit is not yet pushed to origin/test")
    paths = ["scripts/production-reboot-stability.sh", "scripts/production_reboot_stability.py",
             "scripts/production_stability_evidence.py",
             str((P / "README.md").relative_to(ROOT))]
    if P in (TEST250_ROOT / "attempt-04", TEST250_ROOT / "attempt-05"):
        paths.append(str((P / "policy.json").relative_to(ROOT)))
    if subprocess.run(["git", "ls-files", "--error-unmatch", "--", *paths],
                      cwd=ROOT, capture_output=True).returncode != 0:
        raise CaptureError("Test250 runner/registration files are not committed")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=ROOT).returncode != 0:
        raise CaptureError("Test250 runner or registration differs from its pushed commit")
    for path in paths:
        local = (ROOT / path).read_bytes()
        published = subprocess.check_output(["git", "show", "origin/test:" + path], cwd=ROOT)
        if local != published:
            raise CaptureError(f"Test250 runner/registration has not been pushed: {path}")


def preflight():
    assert_registration_pushed()
    base = baseline()
    folder = P / "preflight"
    if folder.exists():
        raise CaptureError("preflight already exists; do not overwrite evidence")
    rec = Recorder(folder)
    report = {"started_utc": now(), "test249_manifest_sha256": base["test249_manifest_sha256"],
              "verdict": "in_progress"}
    write_json(folder / "summary.json", report)
    try:
        state, history, inspected, link = status_report(rec, base, full=True)
        report.update(verdict="accepted_production", boot_id=state["boot_id"],
                      config_sha256=state["config_sha256"], notes_sha256=state["notes_sha256"],
                      module_files=181, partition_hashes=base["partitions"],
                      journal_rows=inspected["rows"], transport=link,
                      accepted_startup_variants=base["accepted_startup_variants"],
                      startup_variant_counts=inspected["startup_variant_counts"],
                      journal_boots=len(evidence.boot_list(history)))
        if base.get("accepted_qca_baudrate"):
            report.update(accepted_qca_baudrate=True, bluetooth_health=state["bluetooth_health"],
                          accepted_qca_cycles=base.get("accepted_qca_cycles", False),
                          qca_baudrate_warning=inspected["qca_baudrate_warning"])
    except Exception as exc:
        report.update(verdict="stop", error=repr(exc))
        collect_failure(rec, report.get("boot_id"))
        raise
    finally:
        report["ended_utc"] = now()
        write_json(folder / "summary.json", report)
    print(json.dumps(report, indent=2), flush=True)


def wait_new_boot(rec, before):
    end = time.monotonic() + WAIT_BOOT
    attempt = 0
    while time.monotonic() < end:
        text, status = rec.adb(f"poll-{attempt:03d}",
                               "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime", 7, required=False)
        if status == 0:
            lines = text.strip().splitlines()
            if len(lines) == 2:
                try:
                    found = evidence.canonical_boot_id(lines[0])
                    uptime = float(lines[1].split()[0])
                    if found != before:
                        return found, uptime
                except (ValueError, IndexError):
                    pass
        if attempt % 4 == 0:
            pnp, _ = rec.ps(f"wait-windows-usb-{attempt:03d}", PS_USB)
            if has_code43(pnp):
                rec.ps("wait-windows-pnp-events", PS_PNP_EVENTS, required=False)
                raise CaptureError("Windows Code43 descriptor failure during boot wait")
        attempt += 1
        time.sleep(3)
    raise CaptureError("no independently verified new Debian boot within 180 seconds")


def observe_window(rec, boot, first_uptime, base):
    if first_uptime > 60:
        raise CaptureError(f"first ADB visibility too late: {first_uptime:.2f}s")
    follow = rec.folder / "kernel-follow.jsonl"
    command = [ADB, "-s", SERIAL, "shell",
               f"journalctl -b {boot} -k -f -n all --no-pager -o json"]
    started_utc = now()
    started_monotonic = time.monotonic()
    completed = False
    with follow.open("wb") as output, (rec.folder / "kernel-follow.stderr").open("wb") as error:
        proc = subprocess.Popen(command, stdout=output, stderr=error)
        try:
            uptime = first_uptime
            count = 0
            while uptime < WINDOW:
                text = rec.adb(f"health-poll-{count:03d}",
                               "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime", 7)[0]
                lines = text.strip().splitlines()
                if len(lines) != 2 or evidence.canonical_boot_id(lines[0]) != boot:
                    raise CaptureError("boot identity changed during observation")
                uptime = float(lines[1].split()[0])
                write_json(rec.folder / "observation-progress.json", {
                    "boot_id": boot, "last_successful_poll_uptime_seconds": uptime,
                    "registered_window_completed": uptime >= WINDOW,
                    "host_observation_elapsed_seconds": round(time.monotonic() - started_monotonic, 3)})
                # Only complete lines can be parsed while ADB is still writing.
                # Parse the entire boot prefix to keep warning-trace context.
                stream = follow.read_bytes()
                complete = stream[:stream.rfind(b"\n") + 1].decode(errors="replace")
                if complete:
                    scan = inspect(complete, boot, base, observed_uptime=uptime)
                    write_json(rec.folder / "live-journal-analysis.json", scan)
                    if scan["fault_counts"] or scan["suspects"]:
                        raise KernelEvidenceError("new boot kernel fault during observation", scan)
                print(f"Test250 {rec.folder.name}: {boot} uptime={uptime:.2f}s", flush=True)
                count += 1
                if count % 3 == 0:
                    pnp, _ = rec.ps(f"observe-windows-usb-{count:03d}", PS_USB)
                    if has_code43(pnp):
                        raise CaptureError("Windows Code43 during observation")
                if proc.poll() is not None:
                    raise CaptureError("live kernel journal transport exited early")
                if uptime < WINDOW:
                    time.sleep(min(WINDOW_POLL, max(0, WINDOW - uptime)))
            completed = True
            return uptime
        finally:
            active = proc.poll() is None
            if active:
                proc.terminate()
            try:
                status = proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                status = proc.wait(timeout=4)
            write_json(rec.folder / "kernel-follow.command.json",
                       {"argv": command, "status": status,
                        "host_stopped_at_window_end": active and completed,
                        "host_stopped_on_non_clean": active and not completed,
                        "registered_window_completed": completed,
                        "started_utc": started_utc, "ended_utc": now()})


def collect_failure(rec, boot):
    """Best-effort, read-only evidence after the first non-clean condition."""
    try:
        rec.adb("failure-boots", "journalctl --list-boots --no-pager", 15, required=False)
        rec.adb("failure-current-kernel-json", "journalctl -b -k --no-pager -o json", 20, required=False)
        rec.adb("failure-usb-device", "for f in /sys/class/udc/*/state; do echo $f; cat $f; done; "
                "ls -l /sys/kernel/config/usb_gadget/gts9/configs/c.1/; "
                "ip -br addr show usb0; ss -lnt; "
                "systemctl is-active ssh.service gts9-usb-acm.service gts9-adbd.service || true",
                15, required=False)
        if boot:
            rec.adb("failure-kernel-json", f"journalctl -b {boot} -k --no-pager -o json", 20, required=False)
            rec.adb("failure-kernel-journal", f"journalctl -b {boot} -k --no-pager -o short-monotonic", 20, required=False)
    except Exception:
        pass
    try:
        rec.ps("failure-windows-usb", PS_USB, required=False)
        rec.ps("failure-windows-pnp-events", PS_PNP_EVENTS, required=False)
    except Exception:
        pass


def round_run(index, base, before_expected):
    folder = P / f"round-{index:02d}"
    if folder.exists():
        raise CaptureError(f"round {index} already has evidence; manual review required")
    rec = Recorder(folder)
    result = {"round": index, "started_utc": now(), "verdict": "in_progress",
              "before_boot_id": None, "after_boot_id": None, "observation_seconds": 0}
    write_json(folder / "verdict.json", result)
    try:
        before_state = production_state(rec, base, "before-")
        before = before_state["boot_id"]
        result["before_boot_id"] = before
        if before != before_expected:
            raise CaptureError("source boot changed since verified previous round")
        before_history = rec.adb("boots-before", "journalctl --list-boots --no-pager", 25)[0]
        if evidence.boot_list(before_history)[-1] != before:
            raise CaptureError("source boot history mismatch")
        before_raw = journal(rec, before, "before-")
        before_scan = inspect(before_raw, before, base)
        if before_scan["fault_counts"] or before_scan["suspects"]:
            raise CaptureError("source boot acquired kernel fault before reboot")
        before_link = transport(rec, before, "before-", source_bound=base.get("ncm_source_bound", False))
        if not (before_link["adb_ok"] and before_link["ssh_ok"] and before_link["ncm_banner_ok"]) or before_link["code43"] or before_link["ncm_initial_failure"]:
            raise CaptureError("source boot transport not clean")
        result["reboot_requested_utc"] = now()
        write_json(folder / "verdict.json", result)
        # The only device mutation in this runner. A transport closure is NOT
        # evidence of reboot; wait_new_boot and boot-list attribution are gates.
        rec.adb("reboot-request", "systemctl reboot", 12, required=False)
        after, first_uptime = wait_new_boot(rec, before)
        result["after_boot_id"] = after
        result["first_adb_uptime_seconds"] = first_uptime
        (folder / "after-boot-id.txt").write_text(after + "\n")
        write_json(folder / "verdict.json", result)
        initial_history = rec.adb("boots-after-initial", "journalctl --list-boots --no-pager", 25)[0]
        initial_attribution = evidence.attribute(before, after, before_history, initial_history)
        if initial_attribution != "attributed":
            raise CaptureError(f"new boot attribution: {initial_attribution}")
        # Shutdown faults belong to the just-ended target, not the new boot.
        ended_raw = journal(rec, before, "ended-target-")
        ended_scan = inspect(ended_raw, before, base)
        write_json(folder / "ended-target-journal-analysis.json", ended_scan)
        if ended_scan["fault_counts"] or ended_scan["suspects"]:
            raise KernelEvidenceError("just-ended target boot acquired a kernel fault", ended_scan)
        uptime = observe_window(rec, after, first_uptime, base)
        result["observation_seconds"] = uptime
        result["new_boot_uptime_seconds"] = uptime
        result["registered_window_completed"] = True
        result["elapsed_seconds_from_first_adb_to_last_poll"] = round(uptime - first_uptime, 2)
        after_history = rec.adb("boots-after", "journalctl --list-boots --no-pager", 25)[0]
        attribution = evidence.attribute(before, after, before_history, after_history)
        result["attribution"] = attribution
        # Preserve the just-ended target boot separately from the new boot.
        after_state = production_state(rec, base)
        if after_state["boot_id"] != after:
            raise CaptureError("observer boot changed before final health gate")
        result["config_sha256"] = after_state["config_sha256"]
        result["notes_sha256"] = after_state["notes_sha256"]
        result["dcc_absent"] = after_state["dcc_absent"]
        result["systemd_failed_units"] = after_state["failed_units"]
        raw = journal(rec, after)
        scan = inspect(raw, after, base)
        result["journal_rows"] = scan["rows"]
        result["kernel_fault_counts"] = scan["fault_counts"]
        result["kernel_suspects"] = scan["suspects"]
        result["known_warning_count"] = scan["known_warning_count"]
        result["startup_variant_counts"] = scan["startup_variant_counts"]
        if base.get("accepted_qca_baudrate"):
            result["bluetooth_health"] = after_state["bluetooth_health"]
            result["qca_baudrate_warning"] = scan["qca_baudrate_warning"]
        link = transport(rec, after, source_bound=base.get("ncm_source_bound", False))
        result["transport"] = link
        if not link["code43"]:
            final_boot = evidence.canonical_boot_id(one_line(rec.adb(
                "round-final-boot-id", "cat /proc/sys/kernel/random/boot_id")[0]))
            if final_boot != after:
                raise CaptureError("boot changed after the observation window")
        if scan["fault_counts"]:
            result["verdict"] = "failure_observed"
        elif link["code43"]:
            result["verdict"] = "usb-code43"
        else:
            result["verdict"] = evidence.round_verdict(
                attribution=attribution, journal=scan, identity_ok=after_state["identity_ok"],
                dcc_absent=after_state["dcc_absent"], uptime=uptime,
                adb_ok=link["adb_ok"], ssh_ok=link["ssh_ok"],
                ncm_ok=link["ncm_banner_ok"], ncm_initial_failure=link["ncm_initial_failure"],
                failed_units=after_state["failed_units"])
    except Exception as exc:
        result.update(verdict="usb-code43" if "Code43" in str(exc) else "suspect",
                      error=repr(exc))
        progress = folder / "observation-progress.json"
        if progress.exists():
            snapshot = json.loads(progress.read_text())
            result["observation_seconds"] = snapshot["last_successful_poll_uptime_seconds"]
        result["registered_window_completed"] = False
        if isinstance(exc, KernelEvidenceError):
            result.update(kernel_fault_counts=exc.scan["fault_counts"],
                          kernel_suspects=exc.scan["suspects"])
            if base.get("accepted_qca_baudrate"):
                result["qca_baudrate_warning"] = exc.scan.get("qca_baudrate_warning")
            if exc.scan["fault_counts"]:
                result["verdict"] = "failure_observed"
        collect_failure(rec, result.get("after_boot_id"))
    finally:
        result["ended_utc"] = now()
        write_json(folder / "verdict.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return result


def summary(rounds, base, final=None):
    clean = sum(row["verdict"] == "clean" for row in rounds)
    first_bad = next((row["round"] for row in rounds if row["verdict"] != "clean"), None)
    fault_totals = {}
    for row in rounds:
        for name, count in row.get("kernel_fault_counts", {}).items():
            fault_totals[name] = fault_totals.get(name, 0) + count
    result = {"registered_rounds": ROUNDS, "completed_rounds": len(rounds), "clean_rounds": clean,
              "attempted_rounds": len(rounds),
              "fully_observed_rounds": sum(row.get("registered_window_completed") is True for row in rounds),
              "first_non_clean_round": first_bad, "rounds": rounds,
              "kernel_config_sha256": base["config_sha256"],
              "kernel_notes_sha256": base["notes_sha256"],
              "dcc_absent_in_completed_clean_rounds": all(
                  row.get("dcc_absent") is True for row in rounds if row["verdict"] == "clean"),
              "kernel_fault_counts": fault_totals,
              "test249_manifest_sha256": base["test249_manifest_sha256"],
              "accepted_startup_variants": base.get("accepted_startup_variants", False),
              "accepted_qca_baudrate": base.get("accepted_qca_baudrate", False),
              "accepted_qca_cycles": base.get("accepted_qca_cycles", False),
              "final_verdict": "in_progress"}
    if first_bad is not None:
        result["final_verdict"] = "stopped_on_first_non_clean"
    elif final is not None:
        result["final_acceptance"] = final
        result["final_verdict"] = "20_attributed_clean_warm_reboots" if final.get("passed") else "final_acceptance_failed"
    return result


def final_acceptance(base, last):
    rec = Recorder(P / "final-acceptance")
    result = {"started_utc": now(), "passed": False}
    write_json(rec.folder / "verdict.json", result)
    try:
        state, history, inspected, link = status_report(rec, base, full=True)
        if state["boot_id"] != last:
            raise CaptureError("final boot ID changed")
        result.update(passed=True, boot_id=last, uptime_seconds=state["uptime_seconds"],
                      partition_hashes=base["partitions"], module_files=181,
                      kernel_journal_rows=inspected["rows"], transport=link)
        if base.get("accepted_qca_baudrate"):
            result.update(bluetooth_health=state["bluetooth_health"],
                          qca_baudrate_warning=inspected["qca_baudrate_warning"])
    except Exception as exc:
        result["error"] = repr(exc)
    finally:
        result["ended_utc"] = now()
        write_json(rec.folder / "verdict.json", result)
    return result


def write_results(result):
    count = result["completed_rounds"]
    bad = result["first_non_clean_round"]
    if bad is None and result["final_verdict"] == "20_attributed_clean_warm_reboots":
        finding = (f"Test250 completed {count} attributed production warm-reboot rounds with no "
                   "detected CPU-stall/panic signature within the registered observation windows.")
        followup = "A separately registered Test251 may study cold and power-path transitions."
    elif bad is None:
        finding = f"Test250 observed {count} clean rounds, but final acceptance did not pass."
        followup = "Review the final acceptance evidence before any further hardware action."
    else:
        finding = f"Test250 stopped after {count} round(s); first non-clean round: {bad}."
        followup = "Review the first non-clean production boot offline before any further reboot or Test251."
    text = f"""# Test250: production warm-reboot stability regression

{finding}

Registered rounds: {ROUNDS}; minimum new-boot window: {WINDOW} seconds.
Final verdict: `{result['final_verdict']}`. Exact per-round boot IDs, transport
states, kernel fault counts and source-time journals are in `summary.json` and
the immutable round directories. The Test249 production kernel, config, DTB,
modules, rootfs services and USB gadget settings were not changed. The only
device action was ordinary `systemctl reboot` when the prior round was clean.

{followup}

This is bounded warm-reboot observation, not a failure-rate estimate or proof
that every historical CPU wedge had the DCC cause. Cold boot, battery-only
boot and Type-C power transitions were not tested here.
"""
    (P / "RESULTS.md").write_text(text)


def run():
    assert_registration_pushed()
    base = baseline()
    pre = json.loads((P / "preflight/summary.json").read_text())
    if pre.get("verdict") != "accepted_production" or pre.get("test249_manifest_sha256") != base["test249_manifest_sha256"]:
        raise CaptureError("Test250 accepted preflight is missing or stale")
    preflight_path = str((P / "preflight").relative_to(ROOT))
    if subprocess.run(["git", "ls-files", "--error-unmatch", "--", preflight_path + "/summary.json"],
                      cwd=ROOT, capture_output=True).returncode != 0:
        raise CaptureError("Test250 preflight has not been committed")
    if subprocess.check_output(["git", "status", "--porcelain", "--", preflight_path], cwd=ROOT).strip():
        raise CaptureError("Test250 preflight evidence has uncommitted files")
    if (P / "summary.json").exists() or any((P / f"round-{i:02d}").exists() for i in range(1, ROUNDS + 1)):
        raise CaptureError("run evidence already exists; never restart blindly")
    rows = []
    before = evidence.canonical_boot_id(pre["boot_id"])
    for index in range(1, ROUNDS + 1):
        row = round_run(index, base, before)
        rows.append(row)
        write_json(P / "summary.json", summary(rows, base))
        if not evidence.may_continue(row["verdict"]):
            write_results(summary(rows, base))
            raise CaptureError(f"stopped on first non-clean round {index}: {row['verdict']}")
        before = row["after_boot_id"]
    final = final_acceptance(base, before)
    result = summary(rows, base, final)
    write_json(P / "summary.json", result)
    write_results(result)
    if not final["passed"]:
        raise CaptureError("20 rounds observed but final acceptance failed")
    print(json.dumps({"final_verdict": result["final_verdict"], "clean_rounds": 20,
                      "last_boot_id": before}, indent=2), flush=True)


def main():
    global P
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run"))
    parser.add_argument("--attempt", type=int, choices=(2, 3, 4, 5),
                        help="Explicitly registered fresh attempt; preserves the stopped original evidence")
    args = parser.parse_args()
    if args.attempt:
        P = TEST250_ROOT / f"attempt-{args.attempt:02d}"
    try:
        {"preflight": preflight, "run": run}[args.action]()
    except (CaptureError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Test250 STOP: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
