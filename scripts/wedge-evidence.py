#!/usr/bin/env python3
"""Offline boot attribution and verdicts for wedge-ssh; never contacts a device."""

import argparse
import hashlib
import json
import pathlib
import re


BOOT_ID = re.compile(r"[0-9a-f]{32}")
WEDGE = re.compile(
    r"rcu:.*(?:detected stalls?|self-detected stall)|soft lockup|"
    r"BUG: workqueue lockup|haven.t responded to the NMI|Kernel panic|"
    r"csd: (?:Detected|Continued) non-responsive"
)
SUSPECT = re.compile(r"frame done timeout|mmc[0-9]+: .*[Tt]imeout|ACTIVE_ONLY|rpmh_write_batch")


def boot_id(value):
    value = value.strip().replace("-", "").lower()
    if not BOOT_ID.fullmatch(value):
        raise ValueError("missing or malformed boot ID")
    return value


def boot_list(text):
    """Parse journalctl --list-boots, rejecting empty/partial/error output."""
    rows = []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 2 or not re.fullmatch(r"-?\d+", fields[0]):
            raise ValueError("malformed journal boot list")
        rows.append((int(fields[0]), boot_id(fields[1])))
    if not rows or rows[-1][0] != 0:
        raise ValueError("boot list has no current boot")
    if len({value for _, value in rows}) != len(rows):
        raise ValueError("duplicate boot IDs")
    if [index for index, _ in rows] != list(range(1 - len(rows), 1)):
        raise ValueError("non-contiguous boot list")
    return [value for _, value in rows]


def select(before_id, before_text, after_text):
    result = {"target_boot_id": None, "extra_boots": None, "reason": ""}
    try:
        anchor = boot_id(before_id)
        before, after = boot_list(before_text), boot_list(after_text)
        if before[-1] != anchor:
            raise ValueError("pre-reboot snapshot raced with another boot")
        if anchor not in after:
            raise ValueError("anchor boot missing after rotation or journal loss")
        offset = after.index(anchor)
        # Old history may have been vacuumed. The retained overlap must agree.
        overlap = after[:offset + 1]
        if before[-len(overlap):] != overlap:
            raise ValueError("journal history changed before the anchor")
        following = after[offset + 1:]
        if not following:
            raise ValueError("no boot after the requested reboot")
        result.update(target_boot_id=following[0], extra_boots=len(following) - 1,
                      current_boot_id=after[-1], reason="first boot after retained anchor")
    except ValueError as exc:
        result["reason"] = str(exc)
    return result


def profile_matches(profile, log):
    lines = [line.partition("Kernel command line: ")[2]
             for line in log.splitlines() if "Kernel command line: " in line]
    if not lines:
        return False
    tokens = " ".join(lines).split()
    values = {}
    for token in tokens:
        key, _, value = token.partition("=")
        values.setdefault(key, []).append(value)
    def exact(key, value):
        return values.get(key) == [value]
    if not exact("panic", "10") or not exact("softlockup_panic", "1"):
        return False
    unknown = " ".join(line for line in log.splitlines()
                       if "Unknown kernel command line parameters" in line)
    if any(token in unknown for token in ("csdlock_debug", "cpuidle.off", "softlockup_panic")):
        return False
    if profile == "csd-lock":
        return exact("csdlock_debug", "1") and "cpuidle.off" not in values
    if profile == "cpuidle-off":
        return exact("cpuidle.off", "1") and "csdlock_debug" not in values
    return profile == "baseline" and not ({"cpuidle.off", "csdlock_debug"} & values.keys())


def classify(selection, capture, log):
    wedge = [line for line in log.splitlines() if WEDGE.search(line)]
    suspect = [line for line in log.splitlines() if SUSPECT.search(line)]
    result = dict(selection, verdict="unattributed", wedge_markers=len(wedge),
                  suspect_markers=len(suspect), first_wedge_line=next(iter(wedge), ""),
                  profile_verified=False)
    if not selection.get("target_boot_id"):
        return result
    if not capture.get("log_ok") or not log.strip():
        result["reason"] = "target journal missing or collection failed"
        return result
    if capture.get("log_boot_id") != selection["target_boot_id"]:
        result["reason"] = "journal boot ID does not match selected target"
        return result
    result["profile_verified"] = profile_matches(capture.get("profile"), log)
    # A positive failure survives a partial observation window or bad profile;
    # profile_verified stays separate so it cannot support an ablation claim.
    if wedge:
        result.update(verdict="wedge", reason="positive failure signature in target journal")
        return result
    if selection["extra_boots"]:
        result["reason"] = "unexpected restart without a captured wedge signature"
        return result
    try:
        current = selection["target_boot_id"]
        stable = (boot_id(capture["sample_start_boot_id"]) == current
                  == boot_id(capture["sample_end_boot_id"]))
        window = float(capture["window_s"])
        uptime = float(capture["uptime_s"])
        stable = stable and window >= 150 and uptime >= window
    except (KeyError, ValueError, TypeError):
        stable = False
    if not capture.get("sample_ok") or not stable or not result["profile_verified"]:
        result["reason"] = "incomplete observation, boot changed, or profile unproven"
        return result
    result.update(verdict="suspect" if suspect else "clean",
                  reason="complete target observation; no wedge signature")
    return result


def select_directory(directory):
    # Even syntactically complete stdout is untrusted if the transport failed.
    # Missing sidecars are supported for manually assembled offline fixtures.
    for name in ("before-id.txt", "boots-before.txt", "boots-after.txt"):
        status = directory / (name + ".status")
        if status.exists() and status.read_text().strip() != "0":
            return {"target_boot_id": None, "extra_boots": None,
                    "reason": f"collection failed: {name}"}
    selection = select((directory / "before-id.txt").read_text(),
                       (directory / "boots-before.txt").read_text(),
                       (directory / "boots-after.txt").read_text())
    return selection


def replay(directory):
    directory = pathlib.Path(directory)
    selection = select_directory(directory)
    capture = json.loads((directory / "capture.json").read_text())
    log = (directory / "klog.txt").read_text(errors="replace")
    result = classify(selection, capture, log)
    result["evidence_sha256"] = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("before-id.txt", "boots-before.txt", "boots-after.txt",
                     "capture.json", "klog.txt", "before-id.txt.status",
                     "boots-before.txt.status", "boots-after.txt.status")
        if (directory / name).exists()
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pick = sub.add_parser("select")
    pick.add_argument("directory", type=pathlib.Path)
    check = sub.add_parser("replay")
    check.add_argument("directory", type=pathlib.Path)
    args = parser.parse_args()
    try:
        if args.command == "select":
            result = select_directory(args.directory)
        else:
            result = replay(args.directory)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"invalid evidence: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
