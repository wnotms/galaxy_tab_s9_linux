# Kernel source time resolves the apparent microsecond backtrace timeout

Two backtrace requests in the exact archived failure boot
`c1027ef1-e680-425b-b6fc-6d7819800639` waited about ten seconds according to
kernel source timestamps. Their journal header times differ by only 20–21
microseconds. The old CPU_WEDGE_EVIDENCE claim that the timeout itself was
therefore microseconds is withdrawn; no kernel delay workaround follows.

| Target | Kernel source start → end (seconds) | Kernel delta | Journal header delta |
|---|---|---|---|
| CPU 2 | 28.403594 → 38.404773 | 10.001179 s | 21 µs |
| CPU 5 | 38.404776 → 48.405993 | 10.001217 s | 20 µs |

`backtraces.jsonl` contains the four original full JSON entries decoded from
test235's archived manual.journal.gz, without a new device operation. Both
_SOURCE_BOOTTIME_TIMESTAMP and the compatibility _SOURCE_MONOTONIC_TIMESTAMP
have identical kernel times in each record. analysis.json records the source
archive/decompressed/raw-entry hashes, immutable boot ID, exact query, all
arithmetic and primary-source hashes. The original binary journal stays in
its existing archive; no raw evidence was edited.

Systemd v257's [kernel log reader](https://raw.githubusercontent.com/systemd/systemd/v257/src/journal/journald-kmsg.c)
parses the /dev/kmsg timestamp and stores it in both source fields. Its
[short-output renderer](https://raw.githubusercontent.com/systemd/systemd/v257/src/shared/logs-show.c)
explicitly disables using the compatibility source monotonic field because
it is actually CLOCK_BOOTTIME, then falls back to journal header time. This
explains the displayed receipt-time intervals for that implementation; the
four archived entries independently demonstrate the discrepancy.

This measures these requests' source-clock intervals, not every historical
boot or exact CPU failure onset. The time spent waiting for CPU2 also precedes
the CPU5 request: receipt-time adjacency cannot prove simultaneous or
independent failure. A failed backtrace still does not mean the core executed
no instruction or took no interrupt; it does not separate hard masking,
firmware, GIC state or non-progress. These historical builds used ordinary
IPIs, whereas test241 separately calibrated the pseudo-NMI route.

For future duration/order analysis preserve JSON/export source fields with
boot identity, or raw /dev/kmsg/console timestamps with their clock semantics.
Keep rendered journal text for signatures, not precise kernel-event timing.
Do not replace absent source fields with inferred kernel timestamps. Stable
/proc/uptime samples remain the observation-window gate.
