# Test 229: trace-retention calibration

Status: pre-registered, recovery preflight complete; calibration pending.

The owner reconnected the SM-X710 in TWRP and requested continuation of the
unfinished work. This resumes the trace-retention gate in
`docs/STALL_TEST_WORKFLOW.md`, following the offline workflow/test improvements.

## Starting identity

ADB serial R52X10045LT, model SM-X710, device gts9wifi, TWRP 3.7.1_12-gts9wifi.
Recovery boot ID: `5b07a0f6-4c26-4d85-b31f-c5a4fad950b6`; battery 88%.
The five boot-chain partition sizes and SHA-256 values match the pre-test-228
production state, including vbmeta. No partition rewrite is needed for this step.
See `preflight/partition-hashes.txt` for exact values.

Recovery `/sys/fs/pstore` is empty. Recovery dmesg and `/proc/last_kmsg` were
saved before reboot; neither is automatically mainline failure evidence. In
particular sec_log/bootloader content must not be used to infer a Linux failure.
Previously collected pstore files from the Debian filesystem are labelled
`previous-*`; they are not attributed to this new boot or this test.

The Debian microSD was mounted `ro,noload` for inspection only. Its last recorded
mainline boot is `29c30043-e4ac-472c-a2e6-205b2ecf34c2`, reaching multi-user at
7.78 seconds with no recorded stage failure. An old watchdog report is not proof
of today's runtime detector state; check sysctls again after the next boot.

## Planned next actions and decision rule

1. Unmount the read-only Debian filesystem and boot the existing production
   image normally. Archive boot ID, command line, runtime watchdog state, current
   trace configuration and kernel journal. Do not start a reboot/wedge series.
2. On a responsive boot, use a separate temporary trace instance with the seven
   proposed CSD/IPI/RCU-stall events, `global` clock and fixed per-CPU buffers.
   Record exact event/filter settings, boundary markers and per-CPU stats before
   consuming any data. Measure at least 41 seconds with margin (target 60 s).
3. Archive the actual text and CPU coverage. Reject memory coverage if records
   overrun or the interval/markers cannot be established. Compare text volume,
   including allowance for printk prefixes and other crash messages, with the
   896 KiB console (reserve at least 128 KiB).
4. A fit is only a capacity result for the observed workload. Early-boot coverage
   and actual recovered dump integrity need separate validation. An SSH-armed
   steady-state trace cannot establish coverage of the known early failure.
   If it does not fit, stop before enabling a dump trigger or another wedge
   series and prepare a bounded capture strategy from the measurement.
5. Remove temporary tracing and restore its prior state. Record final device
   state. No kernel pin, DTB, voltage, partition layout or watchdog threshold
   change is part of this calibration. Do not intentionally induce a panic.

The pre-run decision rule above will remain intact; append results separately.
