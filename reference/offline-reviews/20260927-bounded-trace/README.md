# Bounded trace replay and ramoops capacity correction

Owner request: “继续进行下一步测试”. This is the next offline retention test,
using the complete test-229 capture. No device was contacted, rebooted or flashed.
Source base: bfafd38; no kernel, configuration, DTS or voltage changes.

## Result

Equal per-CPU text tails fit the corrected byte ceiling, but **fail the original
41-second coverage requirement**. They are not a ready hardware candidate.

The previous 896 KiB capacity assumption was wrong. In the pinned kernel:

* `fs/pstore/ram.c:767` rounds console_size down to a power of two, so the
  board's 0xe0000 request becomes 0x80000 = 524,288 bytes.
* `fs/pstore/ram_core.c:32` defines the persistent ring header as uint32_t,
  atomic_t, atomic_t; `include/linux/types.h` defines atomic_t with one int.
  On ARM64 this header is 12 bytes, subtracted in ram_core.c:521.
* The board declares no ECC property; test-229's boot journal reports ecc: 0.
* Payload is therefore 524,276 bytes. Reserving 131,072 bytes for other logs
  leaves **393,204 bytes** for trace serialization.

The source report hashes both ramoops files and the DTS. It also checks the
rounding/subtraction code and the absence of a board ECC property. This is
pinned-source analysis, not a new measurement of recovered persistent contents.
The test-229 raw capture, preregistration and original analysis are unchanged;
this report supersedes their capacity assumption. Its busiest 41-second window
of 2,213,931 bytes is **5.63 times** the corrected trace budget before prefixes.
The old broad trace rate would retain only 2.68 seconds, rather than 5.35.

## Prototype and sensitivity test

Run `python3 scripts/bounded-trace-replay.py --output out/new-tail-replay`.
The output directory must not exist. The tool verifies the trace against its
device hash, stable boot identity, global clock, exact event/filter set, per-CPU
markers, entry counts and zero loss/read counters before using it as a fixture.
It anchors a 41-second window at the earliest CPU END marker, retains each CPU's
contiguous newest records, reserves 16 KiB for metadata, and divides the remaining
budget equally. It does not reallocate quiet CPUs' unused quota or skip oversized
records to substitute older events. Raw sender queue/raise records remain in
scope; truncated cross-CPU evidence is always inconclusive for missing events.

The `~` bytes preceding each line model prefix overhead. They are deliberately
synthetic, not recovered printk. The actual generated file, including metadata
and prefixes, is checked against the budget. This host serializer does not
implement kernel allocation, crash-safe locking, printk line limits or a trigger.

| Assumed prefix per line | Serialized bytes | CPU 0 event span | CPU 7 event span | Complete 41 seconds |
|---|---:|---:|---:|---|
| 0 bytes | 382,251 | 2.591 s | 2.794 s | No |
| 32 bytes | 382,128 | 1.979 s | 2.002 s | No |
| 64 bytes | 381,907 | 1.431 s | 1.559 s | No |

Every CPU loses records inside the requested window in all three cases. Event
span is first-to-last retained timestamp, not proof of activity throughout that
span. The embedded metadata includes source identity/settings, source loss
counters, simulated trigger/cutoff, per-CPU truncation and exact kept counts.
All reports keep `ready_for_wedge_series=false`, including a large-budget test
that preserves every record: serialization alone is not persistence validation.

## Validation and next decision

`PYTHONPATH=tests python3 -m unittest test_bounded_trace_replay -v` passed all
**7 tests in 0.369 s**. Coverage includes real trace replay, full preservation
with sufficient space, uneven CPU activity, equal timestamps across the cutoff,
oversized records, corrupt/filtered/lost source evidence, invalid budgets and
ramoops rounding across the reserve boundary. Only this affected test module
was executed; no full regression or suite-routing change was needed.

Individual shell syntax checks passed. A ccache build with BUILD_MODULES=0,
JOBS=16 and isolated KERNEL_OUT_DIR=out/kernel-bounded-trace completed; config,
DTB and release match production byte-for-byte. The new host image's hash is
archived separately; it was not installed. Source feasibility checks passed.

Do not spend another boot testing this tail as a complete 41-second instrument.
The next design must either provide another proven persistent sink or explicitly
ask a narrower question about positive last-seen CPU activity. Any narrowed
instrument must avoid absence-based conclusions and first pass a healthy
reboot/persistence test before an induced or repeated wedge series. Ordinary
console writes in fs/pstore/platform.c go directly to the backend; the existing
compression/decompression path applies to PSTORE_TYPE_DMESG, not console records.
Turning on pstore compression therefore does not make this console hold the
full trace. Reserved-memory layout and the running tablet remain untouched.
