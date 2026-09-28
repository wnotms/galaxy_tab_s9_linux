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
import sys
import time

import production_stability_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "reference/boot-tests/test-250-production-warm-reboot"
BASE = ROOT / "reference/boot-tests/test-249-no-dcc-production"
ADB = "/mnt/d/android/gts9-active/platform-tools/adb.exe"
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
PS_USB = r'''Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object { $_.InstanceId -match 'VID_0525|VID_18D1|VID_0000&PID_0002' } |
  Select-Object Status, Problem, Class, FriendlyName, InstanceId | Format-List
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
    accepted_cmdline = data["final-acceptance/profile.txt"].decode().splitlines()[1].split()
    owned_cmdline = (ROOT / "boot/cmdline.example.txt").read_text().split()
    if not all(token in accepted_cmdline for token in owned_cmdline):
        raise ValueError("repository production cmdline differs from Test249 acceptance")
    if len(partitions) != 5 or len(modules) != 181 or not identity["DCC_path_absent"]:
        raise ValueError("incomplete Test249 accepted baseline")
    return {"config_sha256": config, "notes_sha256": identity["notes_sha256"],
            "partitions": partitions, "modules": modules, "known_priority3": known_priority3,
            "owned_cmdline_tokens": owned_cmdline,
            "test249_manifest_sha256": hashlib.sha256((BASE / "SHA256.json").read_bytes()).hexdigest()}


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
              "systemctl is-active ssh.service gts9-usb-net.service gts9-usb-adb.service || true")
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
    dcc_ok = dcc_lines[:3] == ["dev=absent", "sysfs=absent", "getty=inactive"] and len(dcc_lines) == 3
    expected_config = config_hash == base["config_sha256"]
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
    write_json(rec.folder / (prefix + "production-state.json"), report)
    if not ok:
        raise CaptureError("current device is not accepted Test249 production or has failed units")
    return report


def transport(rec, boot, prefix=""):
    adb_text, adb_rc = rec.host_adb(prefix + "adb-state", "devices", "-l", required=False)
    adb_ok = adb_rc == 0 and re.search(rf"^{SERIAL}\s+device\b", adb_text, re.M) is not None
    pnp, _ = rec.ps(prefix + "windows-usb-state", PS_USB, required=False)
    code43 = "VID_0000&PID_0002" in pnp and re.search(r"Error|43", pnp, re.I) is not None
    if code43:
        rec.ps(prefix + "windows-pnp-events", PS_PNP_EVENTS, required=False)
        report = {"adb_ok": adb_ok, "ssh_ok": False, "ncm_banner_ok": False,
                  "ncm_initial_failure": False, "code43": True}
        write_json(rec.folder / (prefix + "transport.json"), report)
        return report
    ncm_initial_failure = False
    banner_ok = False
    for attempt in range(3):
        banner, status = rec.ps(prefix + f"windows-ssh-banner-{attempt}", PS_BANNER, timeout=12, required=False)
        if status == 0 and banner.startswith("SSH-2.0-"):
            banner_ok = True
            break
        ncm_initial_failure = True
        if attempt < 2:
            time.sleep(10)
    ssh_text, ssh_rc = rec.ssh(prefix + "ssh-state", "cat /proc/sys/kernel/random/boot_id", timeout=18, required=False)
    ssh_ok = ssh_rc == 0 and evidence.canonical_boot_id(ssh_text) == boot if ssh_text.strip() else False
    report = {"adb_ok": adb_ok, "ssh_ok": ssh_ok, "ncm_banner_ok": banner_ok,
              "ncm_initial_failure": ncm_initial_failure, "code43": bool(code43)}
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
    inspected = evidence.inspect_journal(raw, state["boot_id"], base["known_priority3"])
    write_json(rec.folder / (prefix + "journal-analysis.json"), inspected)
    if inspected["fault_counts"] or inspected["suspects"]:
        raise CaptureError("current boot has kernel failure or suspect messages")
    link = transport(rec, state["boot_id"], prefix)
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
             "reference/boot-tests/test-250-production-warm-reboot/README.md"]
    if subprocess.run(["git", "ls-files", "--error-unmatch", "--", *paths],
                      cwd=ROOT, capture_output=True).returncode != 0:
        raise CaptureError("Test250 runner/registration files are not committed")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=ROOT).returncode != 0:
        raise CaptureError("Test250 runner or registration differs from its pushed commit")
    local = (P / "README.md").read_bytes()
    published = subprocess.check_output(["git", "show", "origin/test:reference/boot-tests/"
                                         "test-250-production-warm-reboot/README.md"], cwd=ROOT)
    if local != published:
        raise CaptureError("Test250 registration has not been pushed to origin/test")


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
                      journal_boots=len(evidence.boot_list(history)))
    except Exception as exc:
        report.update(verdict="stop", error=repr(exc))
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
            pnp, _ = rec.ps(f"wait-windows-usb-{attempt:03d}", PS_USB, required=False)
            if "VID_0000&PID_0002" in pnp and re.search(r"Error|43", pnp, re.I):
                rec.ps("wait-windows-pnp-events", PS_PNP_EVENTS, required=False)
                raise CaptureError("Windows Code43 descriptor failure during boot wait")
        attempt += 1
        time.sleep(3)
    raise CaptureError("no independently verified new Debian boot within 180 seconds")


def observe_window(rec, boot, first_uptime):
    if first_uptime > 60:
        raise CaptureError(f"first ADB visibility too late: {first_uptime:.2f}s")
    follow = rec.folder / "kernel-follow.jsonl"
    command = [ADB, "-s", SERIAL, "shell",
               f"journalctl -b {boot} -k -f -n all --no-pager -o json"]
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
                print(f"Test250 {rec.folder.name}: {boot} uptime={uptime:.2f}s", flush=True)
                count += 1
                if uptime < WINDOW:
                    if proc.poll() is not None:
                        raise CaptureError("live kernel journal transport exited early")
                    time.sleep(min(WINDOW_POLL, max(0, WINDOW - uptime)))
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
                        "host_stopped_at_window_end": active, "ended_utc": now()})


def collect_failure(rec, boot):
    """Best-effort, read-only evidence after the first non-clean condition."""
    try:
        rec.adb("failure-boots", "journalctl --list-boots --no-pager", 15, required=False)
        rec.adb("failure-current-kernel-json", "journalctl -b -k --no-pager -o json", 20, required=False)
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
        before_scan = evidence.inspect_journal(before_raw, before, base["known_priority3"])
        if before_scan["fault_counts"] or before_scan["suspects"]:
            raise CaptureError("source boot acquired kernel fault before reboot")
        before_link = transport(rec, before, "before-")
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
        uptime = observe_window(rec, after, first_uptime)
        result["observation_seconds"] = uptime
        result["new_boot_uptime_seconds"] = uptime
        result["live_observation_seconds"] = round(uptime - first_uptime, 2)
        after_history = rec.adb("boots-after", "journalctl --list-boots --no-pager", 25)[0]
        attribution = evidence.attribute(before, after, before_history, after_history)
        result["attribution"] = attribution
        # Preserve the just-ended target boot separately from the new boot.
        rec.adb("ended-target-kernel-json", f"journalctl -b {before} -k --no-pager -o json", 30)
        after_state = production_state(rec, base)
        if after_state["boot_id"] != after:
            raise CaptureError("observer boot changed before final health gate")
        result["config_sha256"] = after_state["config_sha256"]
        result["notes_sha256"] = after_state["notes_sha256"]
        result["dcc_absent"] = after_state["dcc_absent"]
        result["systemd_failed_units"] = after_state["failed_units"]
        raw = journal(rec, after)
        scan = evidence.inspect_journal(raw, after, base["known_priority3"])
        result["journal_rows"] = scan["rows"]
        result["kernel_fault_counts"] = scan["fault_counts"]
        result["kernel_suspects"] = scan["suspects"]
        result["known_warning_count"] = scan["known_warning_count"]
        link = transport(rec, after)
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
              "first_non_clean_round": first_bad, "rounds": rounds,
              "kernel_config_sha256": base["config_sha256"],
              "kernel_notes_sha256": base["notes_sha256"],
              "dcc_absent_in_completed_clean_rounds": all(
                  row.get("dcc_absent") is True for row in rounds if row["verdict"] == "clean"),
              "kernel_fault_counts": fault_totals,
              "test249_manifest_sha256": base["test249_manifest_sha256"],
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
    preflight_path = "reference/boot-tests/test-250-production-warm-reboot/preflight"
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run"))
    args = parser.parse_args()
    try:
        {"preflight": preflight, "run": run}[args.action]()
    except (CaptureError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Test250 STOP: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
