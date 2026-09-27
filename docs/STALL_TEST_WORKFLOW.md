# Stall investigation: direction review and offline-first workflow

Updated 2026-09-27 after test-231. This is the current work queue. Historical
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

## Test-230: bounded positive-activity instrument

The owner explicitly requested flashing after preparation. The opt-in
`0022-gts9-lastactivity.patch` and `boot/cmdline.lastactivity.example.txt` were
built, validated and physically tested. The question was deliberately narrowed
to last observed IPI/CSD activity, with overwrite/nested-drop limitations; no
41-second or missing-event claim is supported. A manual snapshot retained 48
cells across eight valid CPUs, 58 lines and 6,245 marker bytes. READY appeared
at 0.103705 s; the runtime watchdog state was verified as 1/1/1/10. Automatic
RCU-triggered capture was not exercised. The host decoder validates identity,
completeness of the snapshot format and invalid writer states separately.

[The trial result](../reference/boot-tests/test-230-lastactivity-retention/RESULTS.md)
records a failed persistence gate through Debian → TWRP → restored Debian:
no matching pstore was exposed, and disk archives were demonstrably old.
Production partitions were restored with matching hashes. The failure does
not establish which boot stage lost or failed to expose the data.

Next use the same candidate for one healthy **direct Debian → Debian** warm
reboot, with no TWRP between the snapshot and retrieval. This tests the ordinary
reboot path separately. Attribute the saved snapshot by its capture ID and
record the new observer boot independently. Do not induce/repeat wedges before
that persistence gate passes, and do not replace missing pstore with a healthy
journal copy as proof of crash retention.

## Test-231: direct warm reboot exposed data corruption

The same candidate's healthy snapshot reached pstore after a direct Debian
warm reboot, but failed exact integrity checks: 50 of 58 marker lines match;
eight contain 18 changed bytes / 26 changed bits. The END capture ID/count and
some event/CPU fields changed. Two repeat reads match the device-side file hash;
the original boot's journal still matches the live snapshot exactly. Actual
console_size=524288 and ecc=0 were confirmed. See
[test-231 results](../reference/boot-tests/test-231-lastactivity-direct-reboot/RESULTS.md).

Finding a capture ID or passing a format parser is insufficient. Use
`lastactivity-evidence.py RECOVERED --capture-id ID --reference LIVE` to require
identical canonical marker bytes; corrupted fields that remain valid hex also
must fail. Non-UTF8 raw pstore data stays preserved, not silently repaired.

The integrity gate remains closed. A TWRP boot is not required for this failure,
but the responsible component and any connection to the CPU wedge are unknown.
Next test known payload/checksum retention and assess a separate ramoops ECC
candidate within the existing reservation. Do not enlarge/move memory, adjust
voltages, or start wedge series based on a corrupted snapshot.

Test-231 rollback restored all production partition hashes, but boot
79815bbb-a96b-40c3-a152-ab958fd57d5d then wedged on CPU 5 with PID 1 blocked
and systemctl timing out. The owner returned to TWRP; recovery evidence is
archived. Image integrity passed; healthy rollback boot did not. USB ADB is
now being prepared at the owner's request while preserving the NCM/SSH path.

## Tests 232–234: transport works; retention remains corrupt

Test-232 completed USB ADB alongside NCM/SSH. Preserve the independent ep0
holder, no_disconnect and bound-gadget adbd restart guard; never rebuild the
live gadget to recover ADB at the expense of SSH.

Test-233's known 33,005-byte binary PMSG returned with 464 changed bytes / 542
bits after a direct reboot. Test-234 added only an opt-in root-readable view
of the existing PMSG RAM mapping. Three full live reads proved exact bytes,
including the last read at source uptime 282 seconds. The next boot's archived
record instead contains 251 changed bytes / 293 bits; two pulls and the device
hash agree. This narrows the damage interval to after the last live read and
before the observer's archive reads. It does not identify firmware, RAM, pstore
processing or a CPU-wedge root cause. Both tests used ECC=0.

The probe tool requires a regenerated valid reference and one exact full
occurrence. A surviving header only enables damage measurement, never acceptance.
Its raw-ring mode is for the pinned ARM64 **ECC=0** layout only. Do not apply it
unchanged to an ECC-enabled ring. A healthy reboot integrity pass alone would
not prove crash-triggered capture or retention, and does not open a wedge series.

Test-234 observer `4c78d2cc-7ed8-4a33-be1c-05c2345f77c5` subsequently stopped
answering systemctl and ADB. After owner manual reboot into Debian, its journal
fetched by immutable boot ID confirms CPU 5 non-response and RCU/workqueue
stalls. The responsive CPU 7 idle stack is not CPU 5's missing stack. Recovery
via BCB then reached TWRP; original boot/vendor_boot restoration and all five
hashes passed. Production boot e1ae1723-f52f-4493-9088-6df9a58a46cc stayed
responsive beyond 151 seconds without a detected CPU stall. See
[test-234 results](../reference/boot-tests/test-234-live-pmsg-readback/RESULTS.md).

After recovery, assess an isolated ECC diagnostic within the existing reserved
region. Pinned ram_core.c uses 128-byte Reed–Solomon blocks. ECC=16 can correct
at most eight erroneous symbols per block, less than test-233's worst observed
18 changed payload bytes. ECC=64 is a candidate, not a demonstrated remedy:
parity can also corrupt and the altered layout changes data capacity. Record
actual corrected bytes/unrecoverable blocks and require exact recovered source
bytes. Keep source/observer ECC layout identical; first boot after a layout
change may report errors for incompatible old data. Do not resize/move memory,
adjust voltages or accept corrected-looking CPU fields without integrity proof.


## Test-235: PMSG ECC success, console eligibility still needs validation

The same reserved region with ECC=64 recovered an exact identified 33,005-byte
PMSG after a direct warm reboot: 246 corrected bytes, zero unrecoverable
blocks. Device hashes, repeated TWRP reads and the original observer journal's
binary FILE field agree. The original console file was also recovered from
that journal after later boots replaced its disk copy; its raw hash matches.
The level-6 markers were filtered by loglevel=4 before console delivery, so
that console probe is invalid. Use level 0 (the existing lastactivity pr_emerg
format), not another information-level marker. Do not replace an integrity
comparison with a correction notice or a matching format parser alone.

PMSG success does not prove console or crash-triggered retention, and ECC did
not fix CPU stalls. One manual recovery boot showed CPUs 2/5 failing backtrace
IPIs. Following verified original-image restoration, a later production boot
showed CPU 5 non-response while ADB and systemctl still answered. A responsive
shell or zero failed systemd units is insufficient for a healthy verdict.
See [test-235 results](../reference/boot-tests/test-235-ecc-retention/RESULTS.md).

Test-236 combines the existing lastactivity and ECC patches using the previously
tested diagnostic profile. First calibrate a manual source snapshot against
recovered bytes, including source identity, all CPU validity records and ECC
status. If that passes, automatic crash-triggered capture still needs separate
validation. No repeated wedge series before those gates. For offline journal
retrieval include .journal~ files; system.journal alone can contain only the
latest recovery boot. Save the original raw FILE field, not a rendered or
repaired substitute, and compare its original device hash when available.


## Test-236: actual lastactivity console bytes survive with ECC

The combined existing lastactivity/ECC64 diagnostic produced a manually
triggered snapshot after at least 150 responsive seconds: eight valid CPU
records, 48 event cells, 58 marker lines / 6,294 canonical bytes. After a
normal direct reboot, the immediately next retained boot yielded identical
canonical source bytes. Two raw pulls and the device hash agree; ECC reports
135 corrected bytes and zero unrecoverable blocks. Runtime watchdog arming
was independently checked; pr_emerg level 0 is admitted by console threshold 4.
See [test-236 results](../reference/boot-tests/test-236-lastactivity-ecc/RESULTS.md).

Journal ingestion can lag a successful dump write. Preserve incomplete initial
fetches, then retrieve the same snapshot until a bounded completeness check
passes; never trigger it again to fill a partial host capture. In this trial,
the later complete journal copy and rejected second dump are both archived.

Normal-reboot integrity for the actual console snapshot is demonstrated.
Automatic RCU-triggered capture and crash-path retention remain separate gates;
there was no forced panic or wedge series. Keep source/capture IDs independent
from observer IDs and never turn this manual-snapshot result into a CPU fix or
missing-event conclusion. Original images were restored after this trial.
