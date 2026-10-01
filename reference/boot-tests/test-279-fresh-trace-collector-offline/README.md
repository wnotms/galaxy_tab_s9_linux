# Test279 — offline fresh-request trace collector qualification

Purpose: qualify an isolated tracefs collector and strict offline timing parser
before any new physical diagnostic. This test runs only on host fixtures. It
does not deploy, contact the tablet, enable tracing, load an observer or request
a conversion. The last recorded device baseline remains restored Test263.

## Frozen inputs

Reuse Test272 provider (`399eb497`), Test276 observer (`7a887eab`), and Test278
timing audit. No kernel/config/DT/rootfs/USB/ADC/deadline change. Preserve fixed
5V<=1.8A / 9V<=1.5A, 4440mV and thermal policy. No PPS, pump ON or current increase.
Active Stage3 remains NOT READY. Reuse unchanged provider build and Test276 full
1481-test/W=1/sparse qualification; this host-only change needs affected tests
and syntax checks, not another kernel build or global test-routing change.

## Collector contract

The future device-side collector only owns a new trace instance and four uniquely
named symbolic probes. It does not load/unload the observer or operate hardware.
Boot clock, runtime symbols, event formats, empty private instance and zero
probe misses are prerequisites. Filter workqueue events by the runtime
`sm5440_poll` address. Save raw trace, formats, per-CPU counters, probe profiles,
boot identity and settings. Never clear a global buffer/event/probe registry.
Bound the collection; stop disables owned tracing, preserves evidence and removes
only owned resources. Setup/collection/cleanup errors are retained and fail closed.

The parser pairs requests by PID and work by pointer, distinguishing older
in-flight workers and missing queue boundaries. Loss, truncation, reversed clock,
probe misses, boot change or incomplete pairing produces UNKNOWN. Worker time is
aggregate execution, not ADC time; a queue inside a request does not prove that
request caused it. Trace overhead precludes uninstrumented timing acceptance.

## Execution and stop policy

Physical rounds: **0**. Mock tracefs mutations only. Refuse fixture collisions,
missing capabilities and unknown inputs. Do not modify/reinterpret Test275/277.
Rollback: not applicable, since Test279 does not change the device.

A future physical test needs an independent committed/pushed registration,
essential identity/rescue/battery/OFF gates and exact Test263 rollback. It may
reuse the sealed Test272/276 pair, with one observer load, first-refusal stop and
bounded trace tail, never a reload/retry or relaxed 100ms deadline. This document
does not register or execute that physical test.
