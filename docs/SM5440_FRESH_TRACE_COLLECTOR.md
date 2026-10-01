# Fresh-request tracing collector — offline qualified, not deployed

Test279 implements `collector.py`, `analyse.py` and local `host_tests.py` under
`reference/boot-tests/test-279-fresh-trace-collector-offline/`. It runs **zero
device commands**. The last verified device remains restored Test263 from277.
The four timeout branches identified by Test278 remain unresolved.

## Reuse and source audit

The collector is intended for the existing sealed Test272 kernel and corrected
Test276 observer. Their hardware code, config, DT, ADC settings and100ms deadline
are unchanged. Test276's1481-test/W=1/sparse qualification is reused, not rerun.
Seven tracing source/documentation files were compared byte-for-byte with Linux
pin `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`; hashes are recorded in
`validation/tracing-source-audit.json`. Historical CSD/ramoops capture scripts
are not imported: their CPU/profile/retention assumptions do not fit this test.

Linux's actual workqueue events expose `work` and `function` pointers. The three
queue/start/end events are filtered using runtime `sm5440_poll` kallsyms, not an
ELF address. Four symbolic entry/return probes cover the request and poll; only
the request return captures `$retval:s32`. No guessed instruction offset,
structure dereference, regmap probe or new I2C read is used. The inlined
`sm5440_sample_once` is not probed. No function-graph dependency is introduced.

## Ownership and bounded collection

Each session creates an exclusive `gts9t279_<random token>` trace instance and
uniquely named dynamic probe events. Probe definitions are necessarily global,
but only that private instance enables them. The collector appends commands to
`kprobe_events`; it never clears the registry or a global buffer. Existing events,
clocks, filters, buffers and probes are not modified.

New instances can default to recording on and inherit formatting options.
Immediately stop the new instance, normalize its textual formatting, select
`boot`, disable overwrite and allocate256KiB per CPU. Reject missing/ambiguous
symbols, missing clock, incompatible formats, wrong filter readback, inherited
enabled events, nonempty initial counters or initial probe hits. Save ownership
before event setup. `ready.txt` is emitted only after setup succeeds and recording
starts. A future coordinator must also check that the collector process is still
alive and has not finalized; the persisted ready file is not a live health gate.

The collector never loads or unloads an observer, requests ADC data, accesses a
charger or invokes ADB/reboot/flash. A separately registered coordinator owns
those operations. It ends collection by writing `observer-terminal` to `STOP`;
the collector has a maximum35s deadline, no retry. SIGINT/SIGHUP/SIGTERM unwind
through evidence preservation and owned-resource cleanup. Stop recording and
disable events before copying hit counters. Preserve raw trace even if a counter
or profile read fails. Cleanup tries every owned resource and records failures.
SIGKILL, kernel failure or power loss cannot run Python cleanup: a future physical
runner must retain the ownership file and inspect named resources before any
further test. Do not delete unknown resources or assume cleanup succeeded.

## Evidence and meaning

Preserve raw trace, event formats/filters, selected clock/options, runtime
kallsyms, enabled events, per-CPU before/after counters, probe profiles, boot IDs,
probe registry snapshots and hashed manifest. Read static `trace`, never consume
`trace_pipe`. The parser validates the seal, same boot, zero overflow/drop/read
counts, CPU inventory, record counts and complete probe-hit representation.
Missing/truncated/reversed/mismatched evidence, missed probes, incomplete pairs,
cleanup failure or a call after first refusal produces UNKNOWN.

Requests pair by PID; workqueue records pair by work pointer/PID and enclosing
poll probes. A captured start without its earlier queue can retain aggregate
worker time, but its queue delay is null and queue coverage explicitly incomplete.
Old in-flight work is distinguished from a queue made during the request.
Temporal overlap does **not** establish a causal request-to-worker assignment.
No inferred zero delay, guessed timeout branch or absolute jiffies conversion.

The resulting times are entry-to-return, queue-to-start and aggregate worker
execution. Worker execution includes locks, scheduling, I2C and ADC-ready waits;
it is not ADC conversion time. Tracing overhead prevents uninstrumented timing
acceptance. Even a request returning0 does not grant ADC/hardware/charging
acceptance. `validation/synthetic-capture/` and its report are clearly marked
mock fixtures, not new device evidence.

## Next physical registration, not executed by Test279

1. Register one passive trace attempt using the sealed272/276 pair, preserve
   Test263 rollback and push before any device write. Essential identity, rescue,
   battery, Sink/Device/SDP500, fault0 and pump-OFF gates still apply.
2. Confirm Python3 and actual tracefs availability once; missing support stops
   preparation without another kernel build/config change or boot retry.
3. Start the collector, check live readiness, load the corrected observer once.
   Preserve cached observer result; first refusal ends acquisition. No reload.
4. A pre-registered short tail may capture the already running worker's end;
   it is not another fresh call. Stop with the marker within35s. Incomplete tail
   stays UNKNOWN; do not extend repeatedly until a desired answer appears.
5. Save raw evidence, verify named cleanup, safely unload and assess same-boot
   endpoint separately, then restore exact263 under that registration.

No physical runner/registration is executed here. No increase in current,
relaxation of100ms, change of average32/channel0xdf/12x25ms polling, PPS or pump
ON. Active Stage3 remains NOT READY. If queue/worker attribution still leaves
the ADC/I2C distinction unresolved, design a separate minimal timestamp change
instead of claiming this collector can see an inlined phase.
