#!/usr/bin/env python3
"""Offline replay of the 12 + 8 Test250 CPU-focused reboot chain."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import production_cpu_reboot_continuation as continuation
import production_reboot_stability as old
import production_stability_evidence as evidence


def data(path):
    return json.loads(path.read_text(errors="replace"))


def read(path):
    return path.read_text(errors="replace").replace("\r", "")


def seal(folder):
    rows = read(folder / "SHA256SUMS").splitlines()
    checked = set()
    for row in rows:
        digest, name = row.split("  ", 1)
        path = folder / name
        assert name not in checked and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        checked.add(name)
    present = {str(path.relative_to(folder)) for path in folder.rglob("*")
               if path.is_file() and path.name != "SHA256SUMS"}
    assert checked == present
    return len(checked)


def state(folder, boot, base, prefix="", full=False):
    report = data(folder / (prefix + "production-state.json"))
    assert report["boot_id"] == boot and report["identity_ok"]
    assert report["dcc_absent"] and report["profile_ok"] and not report["failed_units"]
    assert report["config_sha256"] == base["config_sha256"]
    assert report["notes_sha256"] == base["notes_sha256"]
    assert evidence.canonical_boot_id(read(folder / (prefix + "boot-id-confirm.txt"))) == boot
    assert read(folder / (prefix + "dcc-state.txt")).splitlines() == [
        "dev=absent", "sysfs=absent", "getty=inactive", "symbol="]
    if full:
        assert report["partitions_modules_checked"]
        assert old.parse_hashes(read(folder / "partitions.txt"),
                                "/dev/disk/by-partlabel/") == base["partitions"]
        assert old.parse_hashes(read(folder / "module-hashes.txt"),
                                old.MODULE_ROOT + "/") == base["modules"]
        assert read(folder / "module-backups.txt").strip() == "backups_absent"
        assert hashlib.sha256(read(folder / "embedded-config.txt").encode()).hexdigest() == base["config_sha256"]
        assert hashlib.sha256((folder / "kernel-notes.bin").read_bytes()).hexdigest() == base["notes_sha256"]


base = continuation.baseline()
old_summary = data(continuation.ATTEMPT / "summary.json")
assert old_summary["clean_rounds"] == 12
assert old_summary["final_verdict"] == "stopped_on_first_non_clean"
assert not old_summary["round13_reboot_issued"]
assert data(continuation.ATTEMPT / "EVIDENCE_AUDIT.json")["passed"]
old_manifest = data(continuation.ATTEMPT / "SHA256.json")
for name, meta in old_manifest.items():
    blob = (continuation.ATTEMPT / name).read_bytes()
    assert len(blob) == meta["bytes"] and hashlib.sha256(blob).hexdigest() == meta["sha256"]

pre = data(HERE / "preflight/summary.json")
assert pre["verdict"] == "accepted" and pre["source_boot_id"] == continuation.SOURCE_BOOT
assert pre["module_files"] == len(base["modules"]) == 181
state(HERE / "preflight", continuation.SOURCE_BOOT, base, full=True)
assert not continuation.cpu_fault(continuation.scan(
    read(HERE / "preflight/kernel-journal-json.txt"), continuation.SOURCE_BOOT, base))
assert evidence.boot_list(read(HERE / "preflight/boots.txt"))[-1] == continuation.SOURCE_BOOT

seals = {"preflight": seal(HERE / "preflight")}
chain = [old_summary["rounds"][0]["before_boot_id"]]
rounds = []
for saved in old_summary["rounds"][:12]:
    assert saved["verdict"] == "clean" and saved["registered_window_completed"]
    assert saved["before_boot_id"] == chain[-1]
    assert saved["observation_seconds"] >= 150 and not saved["kernel_fault_counts"]
    chain.append(saved["after_boot_id"])
    rounds.append({"round": saved["round"], "source": "attempt-05",
                   "before_boot_id": saved["before_boot_id"],
                   "after_boot_id": saved["after_boot_id"],
                   "observation_seconds": saved["observation_seconds"],
                   "kernel_fault_counts": saved["kernel_fault_counts"],
                   "adb_state": saved["transport"]["adb_ok"],
                   "ssh_ncm_state": saved["transport"]["ssh_ok"] and saved["transport"]["ncm_banner_ok"],
                   "verdict": "clean_under_original_policy"})
assert chain[-1] == continuation.SOURCE_BOOT
assert old_summary["rounds"][12]["after_boot_id"] is None
assert not (continuation.ATTEMPT / "round-13/reboot-request.command.json").exists()

for number in range(13, 21):
    folder = HERE / f"round-{number:02d}"
    seals[folder.name] = seal(folder)
    saved = data(folder / "verdict.json")
    before, after = saved["before_boot_id"], saved["after_boot_id"]
    assert saved["round"] == number and saved["verdict"] == "cpu_clear"
    assert before == chain[-1] and after not in chain and saved["registered_window_completed"]
    assert saved["observation_seconds"] >= 150 and saved["first_adb_uptime_seconds"] <= 60
    assert evidence.canonical_boot_id(read(folder / "after-boot-id.txt")) == after
    before_history = read(folder / "boots-before.txt")
    for name in ("boots-after-initial.txt", "boots-after.txt"):
        assert evidence.attribute(before, after, before_history, read(folder / name)) == "attributed"
    request = data(folder / "reboot-request.command.json")
    assert request["argv"] == [old.ADB, "-s", old.SERIAL, "shell", "systemctl reboot"]
    state(folder, before, base, prefix="before-")
    state(folder, after, base)
    for name, boot in (("before-kernel-journal-json.txt", before),
                       ("ended-target-kernel-journal-json.txt", before),
                       ("kernel-journal-json.txt", after),
                       ("kernel-follow.jsonl", after)):
        assert not continuation.cpu_fault(continuation.scan(read(folder / name), boot, base))
    follow = data(folder / "kernel-follow.command.json")
    assert follow["registered_window_completed"] and follow["host_stopped_at_window_end"]
    progress = data(folder / "observation-progress.json")
    assert progress["boot_id"] == after and progress["registered_window_completed"]
    assert progress["last_successful_poll_uptime_seconds"] == saved["observation_seconds"]
    assert not saved["kernel_fault_counts"]
    chain.append(after)
    rounds.append({"round": number, "source": "continuation-cpu-13-20",
                   "before_boot_id": before, "after_boot_id": after,
                   "observation_seconds": saved["observation_seconds"],
                   "kernel_fault_counts": saved["kernel_fault_counts"],
                   "kernel_suspects": saved["kernel_suspects"],
                   "adb_state": saved["transport"]["adb_ok"],
                   "ssh_ncm_state": saved["transport"]["ssh_ok"] and saved["transport"]["ncm_banner_ok"],
                   "source_transport": saved["source_transport"],
                   "new_boot_transport": saved["transport"],
                   "verdict": "cpu_clear_under_revised_policy"})

assert len(rounds) == 20 and len(set(chain)) == 21
final = data(HERE / "final-acceptance/verdict.json")
assert final["passed"] and final["boot_id"] == chain[-1]
assert final["partition_hashes"] == base["partitions"] and final["module_files"] == 181
state(HERE / "final-acceptance", chain[-1], base, full=True)
assert not continuation.cpu_fault(continuation.scan(
    read(HERE / "final-acceptance/kernel-journal-json.txt"), chain[-1], base))
assert evidence.boot_list(read(HERE / "final-acceptance/boots.txt"))[-1] == chain[-1]
seals["final-acceptance"] = seal(HERE / "final-acceptance")

audit = {"executed": True, "passed": True, "device_access": False,
         "old_attempt_stopped_unchanged": True,
         "old_attempt_manifest_files_verified": len(old_manifest),
         "continuation_sealed_files_verified": seals,
         "boot_chain": chain, "ordinary_reboot_requests_verified": 20,
         "fully_observed_rounds": 20, "minimum_observation_seconds": 150,
         "production_module_files": len(base["modules"]),
         "final_full_identity_verified": True}
(HERE / "EVIDENCE_AUDIT.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

summary = {"registered_rounds": 20, "completed_rounds": 20,
           "clean_rounds_under_original_strict_policy": 12,
           "cpu_clear_rounds_under_revised_policy": 8,
           "cumulative_attributed_cpu_clear_rounds": 20,
           "first_non_clean_round_under_original_policy": 13,
           "first_cpu_non_clear_round": None, "rounds": rounds,
           "minimum_observation_seconds": 150,
           "kernel_config_sha256": base["config_sha256"],
           "kernel_notes_sha256": base["notes_sha256"],
           "test249_manifest_sha256": base["test249_manifest_sha256"],
           "dcc_absent": True, "production_unchanged": True,
           "kernel_fault_counts": {}, "final_acceptance": final,
           "final_verdict": "20_attributed_cpu_clear_warm_reboots_under_revised_scope",
           "not_original_strict_20_clean": True}
(HERE / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps({"passed": True, "rounds": len(rounds), "last_boot": chain[-1],
                  "sealed_file_counts": seals}, indent=2))
