#!/usr/bin/env python3
"""Offline replay of this stopped attempt's raw captures; never access a device."""

import hashlib
import json
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import production_reboot_stability as runner

runner.P = P
base = runner.baseline()


def read(folder, name):
    if "windows-usb" in name:
        # Windows localized PnP output is retained in its original OEM encoding.
        return (folder / name).read_bytes().decode("utf-8", errors="replace")
    return (folder / name).read_text()


def load(folder, name):
    return json.loads(read(folder, name))


def check_state(folder, prefix, expected_boot, full=False):
    state = load(folder, prefix + "production-state.json")
    assert state["boot_id"] == expected_boot
    assert state["identity_ok"] and state["dcc_absent"] and state["profile_ok"]
    assert state["config_sha256"] == base["config_sha256"]
    assert state["notes_sha256"] == base["notes_sha256"]
    assert not state["failed_units"]
    assert runner.evidence.canonical_boot_id(read(folder, prefix + "boot-id-confirm.txt")) == expected_boot
    assert read(folder, prefix + "dcc-state.txt").splitlines() == [
        "dev=absent", "sysfs=absent", "getty=inactive", "symbol="]
    assert not read(folder, prefix + "systemd-failed.txt").strip()
    assert runner.parse_bluetooth_health(read(folder, prefix + "bluetooth-state.txt"), expected_boot)["healthy"]
    assert read(folder, prefix + "cmdline.txt").split() == read(P / "preflight", "cmdline.txt").split()
    if full:
        assert state["partitions_modules_checked"]
        assert runner.parse_hashes(read(folder, "partitions.txt"), "/dev/disk/by-partlabel/") == base["partitions"]
        assert runner.parse_hashes(read(folder, "module-hashes.txt"), runner.MODULE_ROOT + "/") == base["modules"]
        assert read(folder, "module-backups.txt").strip() == "backups_absent"
        # Captured ADB bytes retain CRLF; read_text normalizes the transport wrapper.
        config = read(folder, "embedded-config.txt").encode()
        assert hashlib.sha256(config).hexdigest() == base["config_sha256"]
        assert hashlib.sha256((folder / "kernel-notes.bin").read_bytes()).hexdigest() == base["notes_sha256"]


def check_transport(folder, prefix=""):
    state = load(folder, prefix + "transport.json")
    assert state["adb_ok"] and state["ssh_ok"] and state["ncm_banner_ok"]
    assert state["ncm_source_bound"] and not state["ncm_initial_failure"] and not state["code43"]
    assert runner.bound_banner_ok(read(folder, prefix + "windows-ssh-banner-0.txt"))
    assert not runner.has_code43(read(folder, prefix + "windows-usb-state.txt"))


summary = load(P, "summary.json")
assert summary["registered_rounds"] == 20
assert summary["attempted_rounds"] == 5 and summary["clean_rounds"] == 4
assert summary["fully_observed_rounds"] == 4 and summary["first_non_clean_round"] == 5
assert summary["final_verdict"] == "stopped_on_first_non_clean"
assert not summary["registered_goal_completed"] and not summary["final_acceptance_performed"]
assert not (P / "round-06").exists() and not (P / "final-acceptance").exists()
previous = load(P / "preflight", "summary.json")["boot_id"]
check_state(P / "preflight", "", previous, full=True)
check_transport(P / "preflight")
chain, rounds = [previous], []
required = ["before-boot-id.txt", "after-boot-id.txt", "boots-before.txt", "boots-after.txt",
            "uname.txt", "cmdline.txt", "uptime.txt", "kernel-journal.txt", "kernel-journal-json.txt",
            "systemd-failed.txt", "dcc-state.txt", "adb-state.txt", "ssh-state.txt", "usb-state.txt", "verdict.json"]
for index, saved in enumerate(summary["rounds"], 1):
    folder = P / f"round-{index:02d}"
    verdict = load(folder, "verdict.json")
    assert verdict == saved
    assert all((folder / name).exists() for name in required)
    assert verdict["before_boot_id"] == previous
    after = verdict["after_boot_id"]
    assert after not in chain
    assert runner.evidence.canonical_boot_id(read(folder, "before-boot-id.txt")) == previous
    assert runner.evidence.canonical_boot_id(read(folder, "after-boot-id.txt")) == after
    for name in ["boots-after-initial.txt", "boots-after.txt"]:
        assert runner.evidence.attribute(previous, after, read(folder, "boots-before.txt"), read(folder, name)) == "attributed"
    check_state(folder, "before-", previous)
    check_transport(folder, "before-")
    request = load(folder, "reboot-request.command.json")
    assert request["argv"] == [runner.ADB, "-s", runner.SERIAL, "shell", "systemctl reboot"]
    assert request["status"] == 0
    for name in ["before-kernel-journal-json.txt", "ended-target-kernel-journal-json.txt"]:
        scan = runner.inspect(read(folder, name), previous, base)
        assert not scan["fault_counts"] and not scan["suspects"]
    scan = runner.inspect(read(folder, "kernel-journal-json.txt"), after, base)
    assert not scan["fault_counts"]
    progress = load(folder, "observation-progress.json")
    assert progress["boot_id"] == after
    assert progress["last_successful_poll_uptime_seconds"] == verdict["observation_seconds"]
    health_times = []
    for poll in sorted(folder.glob("health-poll-*.txt")):
        lines = poll.read_text().splitlines()
        assert runner.evidence.canonical_boot_id(lines[0]) == after
        health_times.append(float(lines[1].split()[0]))
    assert health_times == sorted(health_times)
    assert health_times[-1] == verdict["observation_seconds"]
    follow = load(folder, "kernel-follow.command.json")
    follow_scan = runner.inspect(read(folder, "kernel-follow.jsonl"), after, base, health_times[-1])
    assert not follow_scan["fault_counts"]
    assert follow["status"] == -15  # deliberate host termination, documented below
    if index <= 4:
        assert verdict["verdict"] == "clean" and verdict["observation_seconds"] >= 150
        assert verdict["registered_window_completed"] and follow["host_stopped_at_window_end"]
        assert not follow["host_stopped_on_non_clean"] and not scan["suspects"]
        check_state(folder, "", after)
        check_transport(folder)
        assert runner.evidence.round_verdict(
            attribution="attributed", journal=scan, identity_ok=True, dcc_absent=True,
            uptime=health_times[-1], adb_ok=True, ssh_ok=True, ncm_ok=True,
            ncm_initial_failure=False, failed_units=[]) == "clean"
    else:
        assert verdict["verdict"] == "suspect" and not verdict["registered_window_completed"]
        assert verdict["observation_seconds"] == 21.37 and follow["host_stopped_on_non_clean"]
        assert not follow["host_stopped_at_window_end"]
        assert scan["qca_baudrate_warning"]["event_count"] == 2 and len(scan["suspects"]) == 2
        assert all(row["message"] == runner.evidence.QCA_BAUDRATE_EVENT for row in scan["suspects"])
        check_state(folder / "post-stop", "", after, full=True)
        check_transport(folder / "post-stop")
        for alias in load(folder, "POST_STOP_ALIASES.json")["aliases"]:
            content = (folder / alias["source"]).read_bytes()
            assert (folder / alias["alias"]).read_bytes() == content
            assert len(content) == alias["bytes"] and hashlib.sha256(content).hexdigest() == alias["sha256"]
    rounds.append({"round": index, "before_boot_id": previous, "after_boot_id": after,
                   "observation_seconds": health_times[-1], "health_polls": len(health_times),
                   "source_and_target_attributed": True, "fault_counts": scan["fault_counts"],
                   "qca_events": scan["qca_baudrate_warning"]["event_count"], "verdict": verdict["verdict"]})
    chain.append(after)
    previous = after

cycle_review = load(P / "round-05/post-stop", "setup-cycle-review.json")
assert len(cycle_review["samples"]) == 8
for sample in cycle_review["samples"]:
    raw = (ROOT / sample["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == sample["sha256"]
    rows = [json.loads(line) for line in raw.decode().splitlines()]
    assert all(row["_BOOT_ID"] == sample["boot_id"] for row in rows)
    starts = [int(row["_SOURCE_BOOTTIME_TIMESTAMP"]) / 1e6 for row in rows
              if row["MESSAGE"] == "Bluetooth: hci0: setting up wcn6855"]
    assert starts == [cycle["start_source_seconds"] for cycle in sample["cycles"]]
    for cycle in sample["cycles"]:
        assert cycle["start_source_seconds"] < cycle["completed_source_seconds"]
        assert all(cycle["start_source_seconds"] < event["source_seconds"] < cycle["completed_source_seconds"]
                   for event in cycle["events"])
proposal = load(P / "round-05/post-stop", "classification-proposal.json")
assert proposal["status"].startswith("unapproved") and proposal["production_changes"] is False
assert load(P, "policy.json")["maximum_count"] == 1

seals = {}
for folder in [P.parent, P.parent / "attempt-02", P.parent / "attempt-03",
               P.parent / "post-attempt03-analysis", P / "preflight"]:
    manifest = load(folder, "SHA256.json")
    for name, meta in manifest.items():
        content = (folder / name).read_bytes()
        assert len(content) == meta["bytes"] and hashlib.sha256(content).hexdigest() == meta["sha256"]
    seals[str(folder.relative_to(ROOT))] = len(manifest)

result = {"executed": True, "passed": True, "device_access": False,
          "command": "python3 reference/boot-tests/test-250-production-warm-reboot/attempt-04/audit-evidence.py",
          "boot_chain": chain, "ordinary_reboot_requests_verified": 5, "rounds": rounds,
          "initial_and_post_stop_full_identity_verified": True, "production_module_files": len(base["modules"]),
          "setup_cycle_comparison_raw_hashes_verified": 8, "approved_count_unchanged": 1,
          "previous_evidence_seals_verified": seals, "registered_goal_completed": False,
          "first_non_clean_round": 5, "no_sixth_round_or_final_acceptance": True}
(P / "EVIDENCE_AUDIT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2))
