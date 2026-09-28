#!/usr/bin/env python3
"""Owner-authorized Test250 rounds 13–20, with a CPU-focused verdict.

The stopped attempt-05 is never rewritten. The only device mutation here is
one ordinary systemctl reboot per round, after a pushed registration/preflight.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import production_reboot_stability as old
import production_stability_evidence as evidence

ROOT = old.ROOT
ATTEMPT = old.TEST250_ROOT / "attempt-05"
P = old.TEST250_ROOT / "continuation-cpu-13-20"
SOURCE_BOOT = "a48bfed924f64996833e789baf2ab011"
CPU_SUSPECT = re.compile(r"(?:cpu|rcu|csd|lockup|panic|oops|BUG:|SError|hung task|workqueue|call trace|\bstall\b|non-responsive|unexpected backtrace)", re.I)


def baseline():
    old.P = ATTEMPT  # Reuse the sealed, Test249-verified identity and DTB bounds.
    return old.baseline()


def ensure_pushed():
    if subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip() != "test":
        raise old.CaptureError("not on test branch")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT) != subprocess.check_output(
            ["git", "rev-parse", "origin/test"], cwd=ROOT):
        raise old.CaptureError("registration or evidence not pushed to origin/test")
    paths = ["scripts/production_cpu_reboot_continuation.py",
             "reference/boot-tests/test-250-production-warm-reboot/continuation-cpu-13-20/README.md"]
    for path in paths:
        local = (ROOT / path).read_bytes()
        if local != subprocess.check_output(["git", "show", "origin/test:" + path], cwd=ROOT):
            raise old.CaptureError("runner/registration differs from pushed commit: " + path)
    old_summary = json.loads((ATTEMPT / "summary.json").read_text())
    if (old_summary["clean_rounds"] != 12 or old_summary["round13_reboot_issued"] or
            old_summary["rounds"][-1]["after_boot_id"] != SOURCE_BOOT or
            old_summary["final_verdict"] != "stopped_on_first_non_clean"):
        raise old.CaptureError("attempt-05 chain is not the sealed twelve-round source")


def identity(rec, base, prefix="", full=False):
    # Bluetooth is recorded by the journal but is not a CPU-focused stop gate.
    identity_base = dict(base, accepted_qca_baudrate=False)
    return old.production_state(rec, identity_base, prefix, full)


def scan(raw, boot, base, uptime=None):
    report = old.inspect(raw, boot, base, observed_uptime=uptime)
    report["cpu_relevant_suspects"] = [row for row in report["suspects"]
                                      if CPU_SUSPECT.search(row["message"])]
    return report


def cpu_fault(report):
    return bool(report["fault_counts"] or report["cpu_relevant_suspects"])


def transport(rec, boot, prefix=""):
    try:
        return old.transport(rec, boot, prefix, source_bound=True)
    except (old.CaptureError, ValueError) as exc:
        row = {"adb_ok": None, "ssh_ok": None, "ncm_banner_ok": None,
               "code43": None, "observer_error": repr(exc)}
        old.write_json(rec.folder / (prefix + "transport.json"), row)
        return row


def capture_status(rec, base, expected, *, full=False):
    state = identity(rec, base, full=full)
    if state["boot_id"] != expected:
        raise old.CaptureError("source/final boot differs from registered chain")
    history = rec.adb("boots", "journalctl --list-boots --no-pager", 25)[0]
    if evidence.boot_list(history)[-1] != expected:
        raise old.CaptureError("persistent boot history does not end in current boot")
    raw = old.journal(rec, expected)
    result = scan(raw, expected, base)
    old.write_json(rec.folder / "journal-analysis.json", result)
    if cpu_fault(result):
        raise old.KernelEvidenceError("CPU-relevant fault in current boot", result)
    link = transport(rec, expected)
    final_id = evidence.canonical_boot_id(old.one_line(rec.adb("final-boot-id",
        "cat /proc/sys/kernel/random/boot_id")[0]))
    if final_id != expected:
        raise old.CaptureError("boot changed during capture")
    return state, history, result, link


def preflight():
    ensure_pushed()
    if (P / "preflight").exists():
        raise old.CaptureError("preflight already exists")
    base = baseline()
    rec = old.Recorder(P / "preflight")
    verdict = {"started_utc": old.now(), "verdict": "in_progress"}
    old.write_json(rec.folder / "summary.json", verdict)
    try:
        state, history, report, link = capture_status(rec, base, SOURCE_BOOT, full=True)
        verdict.update(verdict="accepted", source_boot_id=SOURCE_BOOT,
                       test249_manifest_sha256=base["test249_manifest_sha256"],
                       config_sha256=base["config_sha256"], notes_sha256=base["notes_sha256"],
                       partition_hashes=base["partitions"], module_files=len(base["modules"]),
                       kernel_fault_counts=report["fault_counts"],
                       kernel_suspects=report["suspects"], transport=link,
                       history_boots=len(evidence.boot_list(history)))
    except Exception as exc:
        verdict.update(verdict="inconclusive", error=repr(exc))
        old.collect_failure(rec, SOURCE_BOOT)
        raise
    finally:
        verdict["ended_utc"] = old.now()
        old.write_json(rec.folder / "summary.json", verdict)
    print(json.dumps(verdict, indent=2), flush=True)


def wait_new_boot(rec, before):
    end = time.monotonic() + old.WAIT_BOOT
    attempt = 0
    while time.monotonic() < end:
        output, status = rec.adb(f"poll-{attempt:03d}",
            "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime", 7, required=False)
        if status == 0:
            lines = output.strip().splitlines()
            if len(lines) == 2:
                found = evidence.canonical_boot_id(lines[0])
                if found != before:
                    return found, float(lines[1].split()[0])
        if attempt % 4 == 0:
            pnp, _ = rec.ps(f"wait-windows-usb-{attempt:03d}", old.PS_USB, required=False)
            if old.has_code43(pnp):
                rec.ps(f"wait-windows-pnp-events-{attempt:03d}",
                       old.PS_PNP_EVENTS, required=False)
        attempt += 1
        time.sleep(3)
    raise old.CaptureError("new boot not observable through ADB within 180 s")


def observe(rec, boot, first_uptime, base):
    if first_uptime > 60:
        raise old.CaptureError("first ADB visibility later than 60 s; startup window missing")
    follow = rec.folder / "kernel-follow.jsonl"
    command = [old.ADB, "-s", old.SERIAL, "shell",
               f"journalctl -b {boot} -k -f -n all --no-pager -o json"]
    completed = False
    with follow.open("wb") as out, (rec.folder / "kernel-follow.stderr").open("wb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err)
        try:
            uptime = first_uptime
            count = 0
            while uptime < old.WINDOW:
                output = rec.adb(f"health-poll-{count:03d}",
                    "cat /proc/sys/kernel/random/boot_id; cat /proc/uptime", 7)[0]
                lines = output.strip().splitlines()
                if len(lines) != 2 or evidence.canonical_boot_id(lines[0]) != boot:
                    raise old.CaptureError("boot changed during 150 s observation")
                uptime = float(lines[1].split()[0])
                old.write_json(rec.folder / "observation-progress.json",
                    {"boot_id": boot, "last_successful_poll_uptime_seconds": uptime,
                     "registered_window_completed": uptime >= old.WINDOW})
                data = follow.read_bytes()
                complete = data[:data.rfind(b"\n") + 1].decode(errors="replace")
                if complete:
                    report = scan(complete, boot, base, uptime)
                    old.write_json(rec.folder / "live-journal-analysis.json", report)
                    if cpu_fault(report):
                        raise old.KernelEvidenceError("CPU fault during observation", report)
                if proc.poll() is not None:
                    raise old.CaptureError("live kernel journal transport exited")
                print(f"continuation round boot={boot} uptime={uptime:.2f}s", flush=True)
                count += 1
                if uptime < old.WINDOW:
                    time.sleep(min(old.WINDOW_POLL, old.WINDOW - uptime))
            completed = True
            return uptime
        finally:
            active = proc.poll() is None
            if active:
                proc.terminate()
            try:
                status = proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill(); status = proc.wait(timeout=4)
            old.write_json(rec.folder / "kernel-follow.command.json",
                {"argv": command, "status": status, "registered_window_completed": completed,
                 "host_stopped_at_window_end": active and completed})


def previous(index):
    if index == 13:
        return SOURCE_BOOT
    prior = json.loads((P / f"round-{index-1:02d}" / "verdict.json").read_text())
    if prior["verdict"] != "cpu_clear" or not prior["registered_window_completed"]:
        raise old.CaptureError("prior round did not qualify for continuation")
    return prior["after_boot_id"]


def run_round(index):
    ensure_pushed()
    if json.loads((P / "preflight" / "summary.json").read_text())["verdict"] != "accepted":
        raise old.CaptureError("pushed full preflight has not passed")
    base = baseline()
    before_expected = previous(index)
    folder = P / f"round-{index:02d}"
    if folder.exists():
        raise old.CaptureError("round evidence exists; refuse duplicate reboot")
    rec = old.Recorder(folder)
    result = {"round": index, "started_utc": old.now(), "verdict": "in_progress",
              "before_boot_id": None, "after_boot_id": None,
              "registered_window_completed": False}
    old.write_json(folder / "verdict.json", result)
    try:
        before_state = identity(rec, base, "before-")
        before = before_state["boot_id"]
        result["before_boot_id"] = before
        if before != before_expected:
            raise old.CaptureError("source boot differs from previous chain")
        before_history = rec.adb("boots-before", "journalctl --list-boots --no-pager", 25)[0]
        if evidence.boot_list(before_history)[-1] != before:
            raise old.CaptureError("source history mismatch")
        before_raw = old.journal(rec, before, "before-")
        before_scan = scan(before_raw, before, base)
        old.write_json(folder / "before-journal-analysis.json", before_scan)
        if cpu_fault(before_scan):
            raise old.KernelEvidenceError("CPU fault on source boot", before_scan)
        result["source_transport"] = transport(rec, before, "before-")
        result["reboot_requested_utc"] = old.now()
        old.write_json(folder / "verdict.json", result)
        rec.adb("reboot-request", "systemctl reboot", 12, required=False)
        after, first_uptime = wait_new_boot(rec, before)
        result.update(after_boot_id=after, first_adb_uptime_seconds=first_uptime)
        (folder / "after-boot-id.txt").write_text(after + "\n")
        old.write_json(folder / "verdict.json", result)
        initial_history = rec.adb("boots-after-initial", "journalctl --list-boots --no-pager", 25)[0]
        if evidence.attribute(before, after, before_history, initial_history) != "attributed":
            raise old.CaptureError("unexpected boot in initial journal history")
        ended_raw = old.journal(rec, before, "ended-target-")
        ended_scan = scan(ended_raw, before, base)
        old.write_json(folder / "ended-target-journal-analysis.json", ended_scan)
        if cpu_fault(ended_scan):
            raise old.KernelEvidenceError("CPU fault in just-ended boot", ended_scan)
        uptime = observe(rec, after, first_uptime, base)
        result.update(observation_seconds=uptime, registered_window_completed=True)
        after_history = rec.adb("boots-after", "journalctl --list-boots --no-pager", 25)[0]
        attribution = evidence.attribute(before, after, before_history, after_history)
        if attribution != "attributed":
            raise old.CaptureError("unexpected boot in final journal history: " + attribution)
        result["attribution"] = attribution
        state = identity(rec, base)
        if state["boot_id"] != after:
            raise old.CaptureError("boot changed before final identity check")
        raw = old.journal(rec, after)
        report = scan(raw, after, base)
        old.write_json(folder / "journal-analysis.json", report)
        result.update(kernel_fault_counts=report["fault_counts"],
                      kernel_suspects=report["suspects"], journal_rows=report["rows"],
                      config_sha256=state["config_sha256"], notes_sha256=state["notes_sha256"],
                      dcc_absent=state["dcc_absent"], systemd_failed_units=state["failed_units"])
        if cpu_fault(report):
            raise old.KernelEvidenceError("CPU fault in complete new journal", report)
        result["transport"] = transport(rec, after)
        final_id = evidence.canonical_boot_id(old.one_line(rec.adb("round-final-boot-id",
            "cat /proc/sys/kernel/random/boot_id")[0]))
        if final_id != after:
            raise old.CaptureError("boot changed after observation")
        result["verdict"] = "cpu_clear"
    except Exception as exc:
        result.update(verdict="cpu_fault" if isinstance(exc, old.KernelEvidenceError) else "inconclusive",
                      error=repr(exc))
        if isinstance(exc, old.KernelEvidenceError):
            result.update(kernel_fault_counts=exc.scan["fault_counts"],
                          kernel_suspects=exc.scan["suspects"])
        old.collect_failure(rec, result.get("after_boot_id"))
    finally:
        result["ended_utc"] = old.now()
        old.write_json(folder / "verdict.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return result


def final():
    ensure_pushed()
    last = json.loads((P / "round-20" / "verdict.json").read_text())
    if last["verdict"] != "cpu_clear":
        raise old.CaptureError("round 20 did not pass")
    if (P / "final-acceptance").exists():
        raise old.CaptureError("final acceptance already exists")
    rec = old.Recorder(P / "final-acceptance")
    verdict = {"started_utc": old.now(), "passed": False}
    old.write_json(rec.folder / "verdict.json", verdict)
    try:
        base = baseline()
        state, history, report, link = capture_status(rec, base, last["after_boot_id"], full=True)
        verdict.update(passed=True, boot_id=state["boot_id"],
                       uptime_seconds=state["uptime_seconds"], transport=link,
                       kernel_fault_counts=report["fault_counts"],
                       kernel_suspects=report["suspects"],
                       partition_hashes=base["partitions"], module_files=len(base["modules"]))
    except Exception as exc:
        verdict["error"] = repr(exc)
        old.collect_failure(rec, last["after_boot_id"])
    finally:
        verdict["ended_utc"] = old.now()
        old.write_json(rec.folder / "verdict.json", verdict)
    print(json.dumps(verdict, indent=2), flush=True)
    return verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["preflight", "round", "final"])
    parser.add_argument("--round", type=int)
    args = parser.parse_args()
    if args.command == "round" and args.round not in range(13, 21):
        parser.error("--round must be 13 through 20")
    try:
        if args.command == "preflight":
            preflight(); return 0
        if args.command == "round":
            return 0 if run_round(args.round)["verdict"] == "cpu_clear" else 2
        return 0 if final()["passed"] else 2
    except Exception as exc:
        print(f"Test250 continuation stopped: {exc!r}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
