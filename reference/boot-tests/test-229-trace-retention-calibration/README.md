# Test 229: trace-retention calibration

Status: completed. Memory coverage passed for this healthy observation;
the all-CPU text capacity gate failed. No wedge series or dump trigger enabled.

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

## Results (2026-09-27)

The agent unmounted Debian and requested one normal reboot from TWRP. Boot
`6258e141-0345-44f0-8f69-0f5d75498747` reached multi-user at 7.950 s,
then reported an RCU stall on CPU 6 at 29.331 s and failure to answer the
backtrace IPI at 39.332 s. Live journal, dmesg, counters and blocked stacks are
in `blocked-boot/`. CPU 7's responding backtrace includes
`smp_call_function_many_cond -> kick_all_cpus_sync -> arch_jump_label_transform_apply`.
PID 1 was blocked in the cgroup path; getty and workers were also blocked.
The owner's photo at about 242 s is `owner-screen-242s.jpg`. This is positive
CPU non-response evidence, but neither the DPU overflow nor Wi-Fi errors prove
the initiating cause. The exact failing CPU instruction remains unknown.

The restored production image uses `panic=0` and lacks the watchdog-debug
flag. Runtime watchdog, soft_watchdog, softlockup_panic and panic were all zero.
Production partition identity therefore did **not** establish the armed stall
baseline. There was no automatic recovery, and tracing was not armed. This
boot is not an armed-profile trial or a valid negative trace observation.
The owner manually rebooted and reported “重启后debian恢复”; the second Debian
boot is `a50ba330-96cb-446f-bccf-a09e8270f0df`. Do not attribute that reboot to
the agent or count it as spontaneous recovery. The attempted sync did not
establish a completed clean shutdown.

WSL SSH could not reach the device. Windows ADB TCP at 169.254.42.1:5555
provided the live evidence and calibration transport. SSH absence alone was
not the failure verdict. The early health capture timed out at systemctl;
`live/health-timeout.json` records the incomplete capture. The failed live
partition-path lookup is retained with status 1; only the earlier TWRP hashes
are established. No partition was written during this test.

### Healthy calibration

The recovered boot answered systemctl with zero failed units. The script
`calibrate-instance.sh` used one temporary instance, global clock, 1024 KiB
per CPU and the exact seven events in `calibration/set_event.txt`, without
filters. It inserted START/END markers on every CPU using taskset, slept 60 s,
stopped tracing and saved per-CPU stats before reading the buffer. This was
healthy production steady-state, with watchdogs still disabled, not early boot
or a workload under the armed stall profile.

* All 8 CPUs retained both markers; the common interval is **60.006590 s**.
* All per-CPU overrun, commit-overrun, dropped-event and read-event counters
  were zero before the trace read. All **32,730** records match the per-CPU
  entry counts. Maximum reported binary occupancy was 281,448 bytes on CPU 0.
* Latency-format text was **3,249,434 bytes**. The busiest observed 41-second
  window contains **2,213,931 bytes** of record lines alone: **2.82 times** the
  786,432-byte trace budget (896 KiB console minus 128 KiB other logs).
* The text measurement excludes printk prefixes and is not an actual panic
  dump. Additional overhead cannot rescue this failed serialized-capacity gate.
  No actual reboot persistence or early-boot coverage was tested.
* The temporary instance was removed successfully and recorded global trace
  settings were byte-identical before/after. No watchdog threshold changed.

`capacity-analysis.json` is reproducible with `python3 analyze-capture.py`.
The archived trace SHA-256 matches the hash read directly on the tablet.
Direct `adb exec-out tar` unexpectedly exposed a terminal to tar and produced
an error despite transport status 0. The successful retry pipes tar through
base64; extraction and the device-side trace hash establish the payload.
The failed attempts are retained separately, not counted as successful pulls.

At the final observation (uptime 437.99 s), the boot ID was unchanged, CPUs
0–7 were online, systemd was in epoll, and systemctl reported zero failed units.
The retained final kernel journal has no positive RCU-stall, unresponsive-NMI,
soft-lockup or workqueue-lockup signature. This is a bounded observation, not
a stability claim. Debian remains running with the original production profile.

### Next capture design, before another physical trial

Increasing the in-memory ring alone is unnecessary for this observation and
does not fix the persistent sink. Even CPU 7 alone needs 673,836 bytes in its
busiest 41-second window before printk overhead; CPU 0 needs 610,961 bytes.
Selecting just one CPU also drops the sender-side queue/raise evidence, and
previous failures have involved different target CPUs. A fixed CPU choice or
simply switching to `orig_cpu` is not an adequate solution: pinned
`kernel/trace/trace.c::ftrace_dump_one()` selects the **dumping** CPU for that mode,
which need not be the unresponsive CPU.

Prepare an offline prototype of bounded per-CPU tail serialization with an
explicit **total serialized byte ceiling**, including printk overhead and
metadata. Reserve space for boot identity, trigger time, enabled events/filters,
per-CPU first/last times, dropped counts and truncation flags. Replay it against
this complete trace, including CPU 0/7 imbalance, and retain cross-CPU queue
evidence wherever conclusions require it. A clipped tail remains useful positive
evidence but must fail the 41-second completeness gate; it cannot justify an
absence-based IPI conclusion. If complete coverage cannot fit, choose a separately
validated persistent sink or a narrower question, without silently reducing the
required interval or enlarging reserved memory. No such kernel prototype was
installed during this calibration.

Before any later armed-profile boot, rebuild from the current documented stall
baseline and verify runtime watchdog state. The parked stall-baseline bundle
has obsolete serial-console tokens and must not be flashed as though it were
the current profile. The existing production partition hashes identify a
production restoration, not an automatic-recovery configuration.

The live Debian journalctl version also exposed an independent runner bug:
257.13-1~deb13u1 rejects `--no-legend`. Its real boot-list output is retained in
`blocked-boot/journal-boots-compatible.txt` for the compatibility regression.
