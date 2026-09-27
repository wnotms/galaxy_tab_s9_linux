# Stall investigation: direction review and offline-first workflow

Updated 2026-09-27 after test-229. This is the current work queue. Historical
test records remain evidence of what was observed and concluded at the time;
the corrections here take precedence over their causal interpretations.

## Direction verdict

The mainline-first port is justified by actual boots into Debian, working
storage and display, and a repeatable CPU non-response signature. There is no
evidence here that abandoning mainline or importing a downstream kernel wholesale
would solve it. Stabilising this foundation before adding more peripherals is
the right priority. Keep the kernel pin, production configuration and hardware
voltages unchanged while investigating.

IPI/CSD response is a useful **observation boundary**, not an established root
cause. GPU-disabled and cpuidle-disabled wedges show those mechanisms are not
necessary for at least those observed failures. They do not prove all failures
share one cause, or that these subsystems can never contribute. The small
cpufreq comparison (2/29 versus 1/29, p=1) is insufficient to establish equivalence
or independence. Do not repeat these ablations without new discriminating evidence.

The problematic direction was methodological: turning sampled state into a
permanent exclusion, starting more boots before validating the detector, and
planning a trace without proving that its useful portion survives reboot.

## Corrections established from the pinned local source

| Previous interpretation | Supported statement |
|---|---|
| `cur_csd == NULL` means outside every IPI handler | `kernel/smp.c::__csd_lock_record()` records current CSD work only. ARM64 `do_handle_IPI()` also handles reschedule, timer, irq_work and backtrace IPIs, and has code before CSD dispatch. NULL does not inspect DAIF or GIC state. |
| Both callbacks are lock-free and cannot spin | `do_nothing()` is trivial, but `kernel/rcu/tree.c::rcu_barrier_handler()` explicitly takes `raw_spin_lock(&rcu_state.barrier_lock)`. That fact alone does not prove it caused this wedge. |
| Case A and every lock dependency are permanently excluded | Repeated NULL observations make a continuously recorded CSD callback less likely at those instants. They do not exclude every execution path, another IRQ, earlier corruption or a shared cause. |
| Two targets failed independently within one second | Two targets had overlapping uncompleted requests. Report time minus wait time estimates when each waiter began waiting; it does not timestamp when the target first failed. Independence is unproven. |
| Unchanged RCU softirq counter proves IRQ masking | It records lack of RCU softirq progress. It is consistent with several forms of starvation or CPU non-progress and does not read interrupt-mask state. |
| `ftrace_dump()` is globally single-shot | `kernel/trace/trace.c` releases `dump_running` at return. It prevents simultaneous dumps. `rcu_ftrace_dump()` in `kernel/rcu/rcu.h` separately permits one invocation per callsite per boot. The dump consumes records and stops tracing, so subsequent dumps may be empty. |
| 8 MiB / 144 KiB/s proves 57 seconds of ring history | The archived 4,408,371 bytes are text output over 30 seconds. Binary ring occupancy, per-CPU imbalance, exact enabled event set and overruns were not archived. `buffer_size_kb` is per CPU. |
| Extra reboot proves CPU wedge | It proves an unexpected restart in retained journal history. Without a positive failure signature its cause is unattributed. |

test-228 remains a real wedge with targets CPU 3/7 and repeated `unresponsive`
reports (Case B). Its raw logs and pre-registered plan are unchanged. The
statement that it establishes the reason for the CPU failure is withdrawn.

## The new runner contract

`scripts/wedge-ssh.sh` archives each invocation in a unique directory and each
round in a separate subdirectory. `scripts/wedge-evidence.py` computes the
verdict from that archive on the host, using the same code for live collection
and offline replay.

1. Save the pre-reboot boot ID and complete journal boot list. Check the live
   profile before each requested reboot. Preserve command stderr and exit status.
   Check runtime `watchdog=1`, `soft_watchdog=1`, `softlockup_panic=1` and `panic=10`:
   Samsung appends `nowatchdog`, so command-line panic tokens alone are insufficient.
   These values establish the preflight boot's state, not a failed target boot's state.
2. From the later journal list, select the first boot after the retained anchor
   **by ID**, never by a mutable relative index or total-count difference. If the
   anchor disappeared, return `unattributed`. Removal of older history is allowed
   only if the retained overlap agrees.
3. Fetch the target journal once, by its immutable ID. All marker counts and
   decisions use that file. CSD non-response is a positive failure signature.
4. Save a boot-ID/uptime/boot-ID sample. A clean verdict requires a stable target,
   a successful nonempty journal, the requested profile in its command line,
   at least the 150-second observation requirement, and no extra recorded boot.
   The first SSH answer after reboot may already belong to a recovery boot.
5. `wedge` means a positive failure signature in the attributed target log;
   `profile_verified` separately states whether it supports the intended profile.
   An unexpected restart alone, a failed capture, missing history or changed
   boot produces `unattributed`. DPU/MMC/RPMh timeout alone gives `suspect`.
   `clean` means no detected wedge within this observation, not stable forever.
6. Stop on the first non-clean result to review evidence. Count suspect and
   unattributed rounds separately; never put them in a clean denominator. A
   stop-on-first-wedge forensic series is not a failure-rate estimate.

The live runner exits 0 for clean completion, 10 for a wedge, 11 for suspect,
12 for unattributed and 1/2 for setup/usage errors. Offline replay exits 0 when
the evidence parses and reports its verdict in JSON; malformed inputs exit 2.

Post-reboot `/proc/interrupts`, `/proc/softirqs` and CSD sysfs values describe the
observer boot, not the wedged target. A pstore file may be stale: it is retained
as supplementary evidence, but does not automatically establish attribution.
Boots that left no persistent journal at all remain a limitation of this SSH
transport. Neither boot-list parsing nor a surviving current boot proves that
such an unrecorded boot did not occur. Missing profile state in an early wedge
also remains unproven, even if the previous boot passed its arming gate.

No power flag runs a **live read-only preflight**, which still contacts the
tablet. During a no-hardware session use only the offline commands below.

```sh
bash scripts/check-stall-offline.sh --focused
# Daily host regression (changed files plus shell syntax):
bash scripts/check-stall-offline.sh
# Full host suite, when broader regression coverage is needed:
bash scripts/check-stall-offline.sh --full
bash scripts/wedge-ssh.sh --replay out/wedge-ssh/PROFILE/RUN/round-N
python3 scripts/prepare-csd-trace.py --output out/csd-trace-next/offline-report.json
```

The check command validates shell files individually: `bash -n scripts/*.sh`
passes the remaining filenames as arguments to the first file and does not
validate every script. Use the focused pass while editing verdict logic, then
changed-file selection for routine changes, or `--core` for broad host regression.
Add artifact/archive checks for their affected inputs;
use the full suite for broad changes and final candidate review. The exact tier
rules and retirement policy are in [HOST_TEST_WORKFLOW.md](HOST_TEST_WORKFLOW.md).
Sanitizer-based host tests need
an environment that permits LeakSanitizer's process inspection; a sandbox denial
is an environment failure, not a driver regression or permission to skip it.

The behavioral tests include the actual test-228 journal plus synthetic boot
histories for lost history, rotation, early recovery, empty logs, transport
failure and mismatched profiles. Shell integration tests substitute a local
mock executable for SSH and a no-op sleep; they perform no device operations.

## Next step: prove trace retention before preparing a hardware candidate

The offline preparation tool emits a hashed source/capability report and a
proposed minimal event set: CSD queue/entry/exit, IPI raise/entry/exit and RCU
stall warning. It checks the archived kernel configuration and available events;
these are capabilities of that recorded kernel, not proof of today's live state.
It deliberately emits no flashable bundle or ready verdict.

There are two independent capacity gates:

* **In-memory coverage:** use `global` clock; record exact event enables/filters,
  each CPU's raw stats, earliest/latest retained timestamps and binary occupancy.
  Cover onset minus 20 seconds through the actual dump trigger. With a nominal
  21-second RCU detector, the planned interval is **at least 41 seconds**, not
  28 seconds, and needs additional margin for delayed detection.
* **Persistent coverage (corrected after test-229):** the DTS requests
  `console-size = <0xe0000>` = 896 KiB, but pinned `fs/pstore/ram.c` rounds it
  **down to 512 KiB**. `ram_core.c` subtracts a 12-byte ARM64 ring header;
  this board has ECC disabled. Reserving 128 KiB for other printk leaves
  **393,204 bytes**, not the previously assumed 786,432 bytes. At the old
  146,945.7 B/s rate this holds only **2.68 seconds** before prefix overhead.
  A 41-second dump at that historical rate needs about 5.75 MiB. Enlarging a
  per-CPU trace ring does not enlarge this sink. The old broad event rate is
  distinct from test-229's measured reduced event set.

After hardware testing is explicitly resumed, first calibrate the reduced event
set on a healthy boot and archive per-CPU statistics and the actual textual dump
size. Omit broad `softirq_*` and `timer:*` initially. If all-CPU output still
cannot fit with room for crash logs, prepare a bounded per-CPU tail capture or a
separately proven persistent sink before any wedge series. Do not change reserved
memory or depend on USB/disk writes from an already wedged machine to bridge the
gap. The recovery chain is a best-effort recovery mechanism, not a guarantee that
a total CPU failure resets successfully.

Only after those gates pass, enable tracing early enough to cover the first
possible failure (an SSH login is too late), retain `trace_clock=global`, and
use one primary RCU trigger. A backstop must account for consumed/disabled tracing.
Verify recovered start/end markers and coverage on every relevant CPU. Missing
`ipi_entry` in a truncated or overwritten trace is **inconclusive**; with complete
coverage it narrows to failure before that tracepoint, not automatically the GIC.
IPI raise and entry also are not a one-to-one request counter: delivery may be
coalesced. Match CPU, function/CSD where available and time ordering.

The original direction review was offline. Hardware work resumed at the owner's
request for [test-229](../reference/boot-tests/test-229-trace-retention-calibration/README.md).
After an unarmed production boot showed CPU 6 non-response, the owner rebooted
to Debian. On that recovered boot the reduced seven-event set retained all
CPU markers over 60 seconds with no overruns, but produced 3,249,434 bytes of
text. The busiest 41-second window alone was 2,213,931 bytes, exceeding the
then-assumed 786,432-byte trace budget before printk overhead. The corrected
budget is 393,204 bytes, making that measured window **5.63 times** too large.
Memory coverage passed for
that healthy workload; persistent capacity failed. Reboot persistence and
early-boot coverage remain untested. No new wedge series is ready.

The offline bounded serialization test is complete:
[replay results](../reference/offline-reviews/20260927-bounded-trace/README.md).
`scripts/bounded-trace-replay.py` verifies the source capture, applies equal
per-CPU byte limits, preserves raw record identities and reports truncation.
With a modeled 32-byte prefix per line and 16 KiB metadata reserve, it emits
382,128 bytes; CPU 0/7 retain only about **2 seconds** of event span. Every CPU
loses part of the requested window. Zero-prefix and 64-byte sensitivity cases
also fail complete coverage. The prefix is a model, not a measured printk bound.
This prototype is host-only and does not establish kernel or reboot behavior.

Do not implement this short tail as though it answers the original 41-second
question. The next diagnostic design must either preserve that interval in a
separately validated sink, or explicitly narrow the question to positive last
observed activity with no missing-event inference. Before a physical trial,
select and implement that design, prove serialization under its byte limit,
then perform a healthy persistence calibration. `orig_cpu` selects the dumping
CPU, not necessarily the stalled target. Ordinary pstore console writes do not
gain the compression available to DMESG records, so enabling a compressor alone
does not solve this console-capacity problem.

The live production image has watchdog, soft_watchdog, softlockup_panic and panic
all zero. Verify runtime arming independently of partition restoration hashes;
the parked stall-baseline bundle has outdated console tokens. Build any future
armed candidate from the current profile and retain its independent identity.
