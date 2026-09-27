# Test 231: snapshot present after warm reboot, but corrupted

Verdict: **failed integrity gate**. The direct Debian → Debian path recovered
the source snapshot in pstore, but it was not byte-identical. No wedge series
or induced panic was run. The source kernel/cmdline/config/DTS were exactly the
test-230 candidate; the experiment changed only the post-snapshot reboot path.

## Attributed source and observer

* Source boot: d953fd46-3ac7-4176-8c2f-30054158cd27.
* Source capture: 0127f2c4-c55e-4a3a-99c3-52deffd56059.
* Direct observer boot: 85b0f19e-00c9-4281-95dd-1942aacd3273, the immediate next
  boot in the retained journal list, with a different capture ID.

The source runtime watchdog/panic state was 1/1/1/10. At uptime 76.73 seconds
the manual trigger produced 58 complete lines / 48 event cells / 6,245 marker
bytes. All eight CPU snapshots were valid. CPU 0 had two nested writer drops;
other CPUs had zero. This remains last-observed activity, not complete history.
BCB was verified empty, then only systemctl reboot was issued. No TWRP or BCB
write occurred between this snapshot and the observer boot.

The observer's systemd-pstore service did run and archived an 8,818-byte
console-ramoops-0 containing the source capture. Unlike test-230's stale file,
this is new matching-source evidence. Finding the ID initially suggested a
successful transfer, but it was only provisional. Commit e92446b's optimistic
title preceded full validation; the subsequent integrity verdict c7f937e and
this report explicitly reject a successful retention claim.

## Exact integrity result

Of the 58 source marker lines, **50 were exact and eight differed**. Positional
alignment of the consecutive snapshot lines found **18 changed bytes / 26
changed bits**, including CPU/event fields, pointer digits and the END capture
ID/count. One CPU header's `GTS9_LA` prefix itself changed, so searching only
perfect marker prefixes would silently omit it. `retention-verdict.json` retains
the expected bytes, recovered hex and XOR differences. Alignment is solely a
damage measurement, not a repaired or trustworthy replacement record.

Examples: an address digit changed while remaining valid hex; CPU `1` became
non-ASCII 0xf1; END's `records=48` became `recnrds=40`. The raw recovered file
is therefore not UTF-8. It was preserved without normalization. Strict ASCII
marker extraction and the format decoder refused it; missing fields were not
filled in from the live copy.

The original tar/base64 pull and two independent later base64 reads all match
the device-side SHA-256:
e858555240f5cfb08ff12494e117e4e6c671138f52d807061ae647729004a010.
This demonstrates stable corruption in the device's archived pstore file,
rather than a discrepancy introduced by these host transfers. Re-reading the
source boot's journal after reboot still yields exactly the original marker
bytes (SHA-256 be6319720a626d06c2d0531347ee3b46b7832a71cc0f5e969d18a444d27fcfcf).

The first source-journal request used a hyphenated boot ID and journalctl
rejected it. The retry used the normalized 32-digit ID and succeeded; both
attempts are retained. The old compressed dmesg file has the same hash as the
preflight baseline, and even raw-deflate decoding failed. It is stale evidence,
not used for this verdict.

Live ramoops parameters independently confirmed the earlier source correction:
console_size=524288, record_size=131072, pmsg_size=1048576, mem_size=2097152,
ftrace_size=0, ecc=0. The roughly 6 KiB snapshot is not failing this test merely
because it exceeds the corrected console capacity.

## Interpretation and follow-up

A TWRP boot is not required for an integrity failure: this damaged snapshot
came through a direct warm reboot. That does not prove TWRP caused test-230's
absence, nor establish where this corruption occurred. The current evidence
does not separate persistent-RAM writes, reset/firmware/memory retention,
read-back or archival, and does not prove a shared cause with CPU non-response.
Do not infer a voltage, DRAM or CPU root cause from this one observation.

Before another wedge trial, validate the persistent-data path with known
payloads/checksums and explicit integrity reporting. The current ECC setting is
zero; evaluating ramoops ECC within the existing reservation is a possible
separate diagnostic candidate, not a validated fix or permission to move or
enlarge reserved memory. Preserve the raw corrupted sample for comparison.

The host decoder now accepts raw console input without a Unicode traceback but
still rejects malformed snapshot fields. Its optional --reference requires
identical canonical marker SHA-256, catching even structurally valid changed
addresses. Four targeted tests cover this real corrupted sample and synthetic
valid-looking corruption; no full regression was needed. Any subsequent host
build for this checker is separate from the unchanged image used in this trial.

## Rollback

The observed candidate remained responsive at the final pre-rollback check,
with zero failed systemd units. It was then returned to TWRP; recovery evidence
was saved before restoring original boot/vendor_boot. The restore command and
all five final partition hashes are in restore/. Final Debian identity/health
is recorded in final-state/. No recovery, vbmeta, init_boot or dtbo write was
part of either the flash or rollback.


The restored production boot 79815bbb-a96b-40c3-a152-ab958fd57d5d was **not
healthy**: CPU 5 failed to respond, PID 1 waited in cgroup_kn_lock_live, and a
separate systemctl probe timed out (124). The first compound identity command
returned zero from its final sysctl read; that did not validate systemd health.
All four production watchdog/panic controls were zero. The owner confirmed a
log-screen stall and manually returned to TWRP. rollback-stall/ preserves the
live failure; owner-recovery/ preserves recovery logs and confirms the restored
partition hashes again. The read-only rootfs record identifies the same boot.
The tablet is now in TWRP for separately authorized USB ADB userspace work.
Partition restoration passed; a healthy final production boot remains unproven.
