"""Pure Test250 evidence checks; no device access or diagnostic-profile gates."""

import json
import re


BOOT_ID = re.compile(r"[0-9a-f]{32}")
BOOT_LINE = re.compile(r"^\s*-?\d+\s+([0-9a-f]{32})\s+")
FAILURES = {
    "soft_lockup": re.compile(r"soft lockup|watchdog: BUG: soft lockup", re.I),
    "rcu_stall": re.compile(r"rcu(?:_preempt)?:?\s*(?:INFO:)?\s*(?:self-)?detected stalls|rcu.*stall", re.I),
    "csd_nonresponse": re.compile(r"CSD.*(?:non-responsive|lock timeout|stall)|CPUS still haven't responded", re.I),
    "panic": re.compile(r"Kernel panic|panic - not syncing", re.I),
    "oops_bug": re.compile(r"\bOops:|\bBUG:|Internal error:|\bSError\b", re.I),
    "hung_task": re.compile(r"hung task|blocked for more than \d+ seconds", re.I),
    "workqueue_lockup": re.compile(r"workqueue lockup", re.I),
    "cpu_nonresponse": re.compile(r"CPU\s*#?\s*\d+.*non-responsive|hard LOCKUP", re.I),
}
SUSPECT = re.compile(
    r"Unhandled context fault|\*ERROR\*|(?:mmc\d|ufs|rpmh|dpu).*tim(?:e|ed) out|"
    r"Call trace:|unexpected (?:CPU )?backtrace|\bstall\b|\bnon-responsive\b|rcu:\s*INFO",
    re.I,
)
AUX_WARNING = ("auxiliary aux_bridge.aux_bridge.0: deferred probe pending: "
               "aux_bridge.aux_bridge: failed to acquire drm_bridge")
REGULATOR_WARNING = "regulator: Not disabling unused regulators"
BOOT_REGISTER_WARNING = re.compile(
    r"WARNING: x1-x3 nonzero in violation of boot protocol:\n"
    r"\tx1: 0000000080000000\n\tx2: [0-9a-f]{16}\n"
    r"\tx3: 0000000000000000\nThis indicates a broken bootloader or old kernel")
SMMU_CONTEXT = re.compile(
    r"arm-smmu 15000000.iommu: Unhandled context fault: fsr=0x402, "
    r"iova=(0x[0-9a-f]+), fsynr=(0x620021|0x630021), cbfrsynra=0x1c00, cb=9")
SMMU_FSR = "arm-smmu 15000000.iommu: FSR    = 00000402 [Format=2 TF], SID=0x1c00"
SMMU_SYNDROMES = {
    "arm-smmu 15000000.iommu: FSYNR0 = 00620021 [S1CBNDX=98 PNU PLVL=1]",
    "arm-smmu 15000000.iommu: FSYNR0 = 00630021 [S1CBNDX=99 PNU PLVL=1]",
}


def startup_variant(row, iova_range=(0xb8000000, 0xb8200000)):
    """Narrow classes observed in both accepted Test249 production captures.

    Counts are enforced by inspect_journal. These are existing errors/warnings,
    not a claim that SMMU faults are harmless or repaired.
    """
    message = row["MESSAGE"]
    timestamp = int(row["_SOURCE_BOOTTIME_TIMESTAMP"])
    if int(row.get("PRIORITY", 7)) != 3:
        return None
    if timestamp == 0 and BOOT_REGISTER_WARNING.fullmatch(message):
        return "boot_register_warning"
    if timestamp > 200_000:
        return None
    match = SMMU_CONTEXT.fullmatch(message)
    if match and iova_range[0] <= int(match[1], 16) < iova_range[1]:
        return "smmu_context_fault"
    if message == SMMU_FSR:
        return "smmu_fsr"
    if message in SMMU_SYNDROMES:
        return "smmu_fsynr"
    return None


def canonical_boot_id(value):
    result = value.strip().lower().replace("-", "")
    if not BOOT_ID.fullmatch(result):
        raise ValueError(f"invalid boot ID: {value!r}")
    return result


def boot_list(text):
    if not text.strip():
        raise ValueError("missing journal boot list")
    ids = []
    for line in text.splitlines():
        if line.startswith("IDX ") or not line.strip():
            continue
        match = BOOT_LINE.match(line)
        if not match:
            raise ValueError(f"malformed journal boot-list row: {line[:100]!r}")
        ids.append(match.group(1))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("empty or duplicate journal boot list")
    return ids


def attribute(before_id, after_id, before_text, after_text):
    before_id, after_id = canonical_boot_id(before_id), canonical_boot_id(after_id)
    before, after = boot_list(before_text), boot_list(after_text)
    if before[-1] != before_id:
        return "before_history_mismatch"
    if before_id == after_id:
        return "boot_id_unchanged"
    if before_id not in after:
        return "previous_boot_missing"
    if after[after.index(before_id) + 1:] != [after_id]:
        return "unexpected_boot_or_history"
    if after[-1] != after_id:
        return "after_history_mismatch"
    return "attributed"


def inspect_journal(raw, boot_id, known_priority3=(), *, require_start=True,
                    accepted_startup_variants=False,
                    startup_iova_range=(0xb8000000, 0xb8200000)):
    """Require complete JSON rows with source timestamps and classify each message."""
    if raw is None:
        raise ValueError("missing kernel journal")
    if not raw.strip():
        raise ValueError("empty kernel journal")
    expected = canonical_boot_id(boot_id)
    known = set(known_priority3)
    if accepted_startup_variants:
        # Exact old SMMU/register messages must also obey time/count bounds.
        known = {message for message in known if not (
            message.startswith("arm-smmu 15000000.iommu:") or
            message.startswith("WARNING: x1-x3 nonzero"))}
    variant_counts = {}
    rows, failures, suspects, known_warnings = [], {}, [], []
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON journal row {number}: {exc}") from exc
        if row.get("_BOOT_ID", "").lower() != expected:
            raise ValueError(f"wrong boot ID in journal row {number}")
        if "_SOURCE_BOOTTIME_TIMESTAMP" not in row:
            raise ValueError(f"missing source timestamp in journal row {number}")
        message = row.get("MESSAGE")
        if not isinstance(message, str):
            raise ValueError(f"missing message in journal row {number}")
        rows.append(row)
        try:
            if int(row["_SOURCE_BOOTTIME_TIMESTAMP"]) < 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError(f"invalid source timestamp in journal row {number}")
        variant = startup_variant(row, startup_iova_range) if accepted_startup_variants else None
        if variant:
            variant_counts[variant] = variant_counts.get(variant, 0) + 1
            limit = 1 if variant == "boot_register_warning" else 10
            if variant_counts[variant] <= limit:
                known_warnings.append(message)
                continue
        for name, pattern in FAILURES.items():
            if pattern.search(message):
                failures[name] = failures.get(name, 0) + 1
        accepted_clock_trace = (message == "Call trace:" and
                                any("pc : update_config+0xdc/0xf0" in old.get("MESSAGE", "")
                                    for old in rows[-25:]) and
                                any("rcg didn't update its configuration" in old.get("MESSAGE", "")
                                    for old in rows[-25:]))
        if message in (AUX_WARNING, REGULATOR_WARNING) or accepted_clock_trace:
            known_warnings.append(message)
            continue
        try:
            priority = int(row.get("PRIORITY", 7))
        except (TypeError, ValueError):
            raise ValueError(f"invalid priority in journal row {number}")
        if priority == 3 and message in known:
            known_warnings.append(message)
        elif priority <= 2 or SUSPECT.search(message) or priority == 3:
            suspects.append({"row": number, "priority": priority, "message": message})
    if require_start and not any(row["MESSAGE"].startswith("Linux version ") and
                                 row["_SOURCE_BOOTTIME_TIMESTAMP"] == "0" for row in rows):
        raise ValueError("kernel journal lacks the startup Linux-version record")
    return {"rows": len(rows), "fault_counts": failures, "suspects": suspects,
            "known_warning_count": len(known_warnings),
            "startup_variant_counts": variant_counts,
            "first_source_timestamp": rows[0]["_SOURCE_BOOTTIME_TIMESTAMP"],
            "last_source_timestamp": rows[-1]["_SOURCE_BOOTTIME_TIMESTAMP"]}


def round_verdict(*, attribution, journal, identity_ok, dcc_absent, uptime,
                  adb_ok, ssh_ok, ncm_ok, ncm_initial_failure, failed_units):
    if journal.get("fault_counts"):
        return "failure_observed"
    if attribution != "attributed" or journal.get("suspects") or not identity_ok or not dcc_absent:
        return "suspect"
    if uptime < 150 or not adb_ok or not ssh_ok or not ncm_ok or failed_units:
        return "suspect"
    if ncm_initial_failure:
        return "usb-transient"
    return "clean"


def may_continue(verdict):
    return verdict == "clean"
