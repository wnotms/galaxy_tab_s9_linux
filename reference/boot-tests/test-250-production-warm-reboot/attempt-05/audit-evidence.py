#!/usr/bin/env python3
"""Replay stopped Test250 attempt 05 from saved files; no device access."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as runner

runner.P = HERE
base = runner.baseline()


def read(path):
    return path.read_bytes().decode("utf-8", errors="replace").replace("\r", "")


def data(path):
    return json.loads(read(path))


def state(folder, boot, full=False, prefix=""):
    report = data(folder / (prefix + "production-state.json"))
    assert report["boot_id"] == boot and report["identity_ok"]
    assert report["dcc_absent"] and report["profile_ok"] and not report["failed_units"]
    assert report["config_sha256"] == base["config_sha256"]
    assert report["notes_sha256"] == base["notes_sha256"]
    assert report["bluetooth_health"]["healthy"]
    assert runner.evidence.canonical_boot_id(read(folder / (prefix + "boot-id-confirm.txt"))) == boot
    assert read(folder / (prefix + "dcc-state.txt")).splitlines() == [
        "dev=absent", "sysfs=absent", "getty=inactive", "symbol="]
    assert read(folder / (prefix + "cmdline.txt")).split() == read(HERE / "preflight/cmdline.txt").split()
    if full:
        assert report["partitions_modules_checked"]
        assert runner.parse_hashes(read(folder / "partitions.txt"), "/dev/disk/by-partlabel/") == base["partitions"]
        assert runner.parse_hashes(read(folder / "module-hashes.txt"), runner.MODULE_ROOT + "/") == base["modules"]
        assert read(folder / "module-backups.txt").strip() == "backups_absent"
        assert hashlib.sha256(read(folder / "embedded-config.txt").encode()).hexdigest() == base["config_sha256"]
        assert hashlib.sha256((folder / "kernel-notes.bin").read_bytes()).hexdigest() == base["notes_sha256"]


def transport(folder, prefix=""):
    report = data(folder / (prefix + "transport.json"))
    assert all(report[k] for k in ("adb_ok", "ssh_ok", "ncm_banner_ok", "ncm_source_bound"))
    assert not report["ncm_initial_failure"] and not report["code43"]
    assert runner.bound_banner_ok(read(folder / (prefix + "windows-ssh-banner-0.txt")))
    assert not runner.has_code43(read(folder / (prefix + "windows-usb-state.txt")))


summary = data(HERE / "summary.json")
assert summary["registered_rounds"] == 20
assert summary["attempted_rounds"] == 13 and summary["fully_observed_rounds"] == 12
assert summary["clean_rounds"] == 12 and summary["first_non_clean_round"] == 13
assert summary["final_verdict"] == "stopped_on_first_non_clean"
assert summary["ordinary_reboot_commands"] == 12 and not summary["final_acceptance_performed"]
assert not (HERE / "round-14").exists() and not (HERE / "final-acceptance").exists()
assert data(HERE / "policy.json")["maximum_count"] == 2

pre = data(HERE / "preflight/summary.json")
assert pre["verdict"] == "accepted_production" and pre["module_files"] == 181
boot = pre["boot_id"]
state(HERE / "preflight", boot, full=True)
transport(HERE / "preflight")
chain, rounds = [boot], []
for index in range(1, 13):
    folder = HERE / f"round-{index:02d}"
    saved = data(folder / "verdict.json")
    assert saved == summary["rounds"][index - 1] and saved["verdict"] == "clean"
    assert saved["round"] == index and saved["before_boot_id"] == boot
    after = saved["after_boot_id"]
    assert after not in chain and saved["registered_window_completed"]
    assert saved["observation_seconds"] >= 150
    assert runner.evidence.canonical_boot_id(read(folder / "before-boot-id.txt")) == boot
    assert runner.evidence.canonical_boot_id(read(folder / "after-boot-id.txt")) == after
    before_history = read(folder / "boots-before.txt")
    for filename in ("boots-after-initial.txt", "boots-after.txt"):
        assert runner.evidence.attribute(boot, after, before_history, read(folder / filename)) == "attributed"
    state(folder, boot, prefix="before-")
    transport(folder, prefix="before-")
    request = data(folder / "reboot-request.command.json")
    assert request["argv"] == [runner.ADB, "-s", runner.SERIAL, "shell", "systemctl reboot"]
    for name in ("before-kernel-journal-json.txt", "ended-target-kernel-journal-json.txt"):
        scan = runner.inspect(read(folder / name), boot, base)
        assert not scan["fault_counts"] and not scan["suspects"]
    scan = runner.inspect(read(folder / "kernel-journal-json.txt"), after, base)
    assert not scan["fault_counts"] and not scan["suspects"]
    assert scan["qca_baudrate_warning"]["state"] in ("accepted", "absent")
    follow = data(folder / "kernel-follow.command.json")
    assert follow["registered_window_completed"] and follow["host_stopped_at_window_end"]
    assert not follow["host_stopped_on_non_clean"]
    follow_scan = runner.inspect(read(folder / "kernel-follow.jsonl"), after, base)
    assert not follow_scan["fault_counts"] and not follow_scan["suspects"]
    progress = data(folder / "observation-progress.json")
    assert progress["boot_id"] == after and progress["registered_window_completed"]
    assert progress["last_successful_poll_uptime_seconds"] == saved["observation_seconds"]
    state(folder, after)
    transport(folder)
    assert runner.evidence.round_verdict(
        attribution="attributed", journal=scan, identity_ok=True, dcc_absent=True,
        uptime=saved["observation_seconds"], adb_ok=True, ssh_ok=True, ncm_ok=True,
        ncm_initial_failure=False, failed_units=[]) == "clean"
    rounds.append({"round": index, "before_boot_id": boot, "after_boot_id": after,
                   "observation_seconds": saved["observation_seconds"],
                   "qca_events": scan["qca_baudrate_warning"]["event_count"],
                   "kernel_fault_counts": scan["fault_counts"], "verdict": "clean"})
    chain.append(after)
    boot = after

stopped = HERE / "round-13"
last = data(stopped / "verdict.json")
assert last == summary["rounds"][12] and last["verdict"] == "suspect"
assert last["before_boot_id"] == boot and last["after_boot_id"] is None
assert not last["reboot_requested"] and not last["registered_window_completed"]
assert not (stopped / "reboot-request.command.json").exists()
assert runner.evidence.canonical_boot_id(read(stopped / "before-boot-id.txt")) == boot
state(stopped, boot, prefix="before-")
assert runner.evidence.boot_list(read(stopped / "boots-before.txt"))[-1] == boot
source_scan = runner.inspect(read(stopped / "before-kernel-journal-json.txt"), boot, base)
assert not source_scan["fault_counts"] and not source_scan["suspects"]
probe = data(stopped / "before-windows-ssh-banner-0.command.json")
assert probe["status"] == "timeout"
assert (stopped / "before-windows-ssh-banner-0.txt").stat().st_size == 0
assert not runner.has_code43(read(stopped / "before-windows-usb-state.txt"))
post = stopped / "post-stop"
post_report = data(post / "summary.json")
assert post_report["verdict"] == "captured_same_boot"
assert post_report["boot_history_last_id"] == boot
state(post, boot, full=True)
transport(post)
assert not post_report["kernel_scan"]["fault_counts"] and not post_report["kernel_scan"]["suspects"]
repeat = data(post / "host-probe-review/summary.json")
assert len(repeat["observations"]) == 3
assert all(row["valid_bound_banner"] for row in repeat["observations"])

seals = {}
for folder in (HERE.parent, HERE.parent / "attempt-02", HERE.parent / "attempt-03",
               HERE.parent / "post-attempt03-analysis", HERE.parent / "attempt-04", HERE / "preflight"):
    manifest = data(folder / "SHA256.json")
    for name, meta in manifest.items():
        content = (folder / name).read_bytes()
        assert len(content) == meta["bytes"] and hashlib.sha256(content).hexdigest() == meta["sha256"]
    seals[str(folder.relative_to(ROOT))] = len(manifest)

result = {"executed": True, "passed": True, "device_access": False,
          "boot_chain": chain, "ordinary_reboot_requests_verified": 12,
          "rounds": rounds, "first_non_clean_round": 13,
          "first_non_clean_condition": "host_source_bound_banner_probe_timeout",
          "round13_reboot_issued": False, "post_stop_same_boot_verified": True,
          "initial_and_post_stop_full_identity_verified": True,
          "production_module_files": len(base["modules"]),
          "previous_evidence_seals_verified": seals,
          "final_acceptance_performed": False, "registered_goal_completed": False}
(HERE / "EVIDENCE_AUDIT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2))
