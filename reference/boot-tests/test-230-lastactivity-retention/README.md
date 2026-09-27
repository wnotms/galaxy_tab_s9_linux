# Test 230: last-activity snapshot persistence calibration

Status: pre-registered; candidate built and validated, hardware run pending.
Owner requests: “继续进行下一步测试”, then “完成后刷入进行测试”.
This authorizes preparing, flashing and testing the diagnostic candidate.

## Question and limits

This is explicitly narrower than the failed 41-second trace plan: can a bounded
snapshot preserve each CPU's last observed IPI/CSD activity through a normal
reboot into recovery? It does not preserve complete history or justify
missing-event conclusions. It is not a failure-rate series.

Diagnostic patch 0022 records the last of six event kinds per CPU, plus count
and monotonic-fast timestamp. A per-CPU try-claim never waits; nested writers
are counted as dropped. Dumping freezes admission, copies fields with sequence
validation, marks in-flight CPUs invalid, and never requests an IPI or waits
for a target CPU. Printk/console delivery remains best effort and can itself
be delayed; this is not a promise of crash-safe persistence.

Kinds: 0 CSD queue (target/function/CSD), 1 CSD entry (function/CSD), 2 CSD exit,
3 IPI raise (mask/reason pointer), 4 IPI entry (reason pointer), 5 IPI exit.
Addresses are numeric for offline symbolication with the exact diagnostic
vmlinux. Overwrites and nested execution mean counts/last timestamps do not
prove a missing delivery. Monotonic-fast time is not a causal ordering guarantee.

The feature is compiled only with GTS9_DIAGNOSTIC_PATCHES, runtime-gated by
 gts9_lastactivity=1, compatible samsung,gts9wifi and exactly eight CPU IDs.
It registers at early_initcall, emitting a fresh capture ID and READY only after
all probes register. The first RCU stall is the automatic dump trigger; a root
sysfs write is the calibration trigger. Dumping is once per boot and stops
recording. No panic injection, voltage/DT/config change or new detector threshold.

Maximum output is 58 lines (BEGIN, eight CPU headers, 48 events, END), under
20 KiB with maximum event values and 64 modeled prefix bytes per line. This
is below the corrected 393,204-byte trace allowance. Actual printk serialization
and recovered integrity are to be measured in this trial.

## Candidate and preregistered procedure

Build: GTS9_DIAGNOSTIC_PATCHES=0022-gts9-lastactivity.patch USE_CCACHE=1
BUILD_MODULES=0 JOBS=16 KERNEL_OUT_DIR=out/kernel-lastactivity scripts/build-kernel.sh.
Config/DTB/release match production; diagnostic Image differs. The bundle uses
the existing production init_boot ramdisk and the current stall-baseline cmdline
with gts9_lastactivity=1. Bundle validation passed. init_boot and dtbo hashes
match the known device state; only boot/vendor_boot need writing. Generated
vbmeta is NOT to be flashed; existing device vbmeta remains unchanged.

1. Archive Debian identity, then enter TWRP using the validated BCB helper and
   a plain systemctl reboot. Save recovery pstore/dmesg, device/layout identity,
   all five partition hashes and boot/vendor_boot backups.
2. Verify candidate and backups, write only boot/vendor_boot, require full
   partition read-back equality before booting. Commit this preregistration and
   candidate identity before writes. Never rewrite recovery or vbmeta.
3. Boot once. Retain boot ID, cmdline, READY capture ID, runtime watchdog values
   and kernel journal. If a real stall happens first, archive it and stop the
   healthy calibration; never label an automatic next boot clean.
4. On a responsive boot, observe at least 60 seconds, then write 1 to
   /sys/module/gts9_lastactivity/parameters/dump. Fetch and validate the live
   BEGIN/CPU/EVENT/END snapshot. A second dump should be refused; preserve that
   result. No forced panic.
5. Enter TWRP and collect pstore before another Linux boot. Compare all snapshot
   marker lines byte-for-byte with the live copy. Missing/truncated/interleaved
   output fails retention. valid=0 remains invalid evidence even if retained.
6. Archive/hash results before another candidate. Restore boot/vendor_boot
   backups with read-back checks and return to production Debian. Record actual
   final state. Transport loss without positive failure evidence is unattributed
   and may require the owner's physical recovery action.

Three host decoder tests passed: maximum values/byte bound, invalid writer
state, truncation, duplicate/mixed capture and missing events. This does not
establish live probe operation or reboot retention.

## Preflight note

The first check observed the same Debian boot as test-229,
a50ba330-96cb-446f-bccf-a09e8270f0df, uptime 1471.46 s, zero failed units.
The compound shell command ended status 1 because optional recovery-helper
paths did not exist; this was not a failed systemctl or new kernel failure.
Use the repository boot/gts9-debian-to-recovery.sh via sh -s instead.
