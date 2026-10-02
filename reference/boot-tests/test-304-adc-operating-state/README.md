# Test304 — read-only SM5440 operating-state evidence

Purpose: inspect actual stable control registers before proposing an ADC
operating-condition change. This is evidence collection on the retained
Test299/Test300 boot, not a new charging or PPS acceptance.

Boot: `57535bed-a626-48d0-aaaa-3071ac8332e5`; kernel notes and embedded
configuration still match the accepted installation. No reboot, flash, register
write, fault clearing, conversion request, PPS request or pump activation.

`device-read.py` is the exact remote program used via ADB stdin. It first
requires the expected boot and regmap `range` of exactly `0-2b`. In the pinned
mainline regmap implementation this builds the software offset cache without
reading hardware. Each subsequent seek/read requests exactly one seven-byte
register row, verifies the returned address/value format and uses `O_RDONLY`.
The buffer-length check precedes `regmap_read()`, so the next register is not
read. All selected addresses are stable control/identity registers; none is
INT1..4. A full `cat registers` would consume interrupt latches and was avoided.
Before/after CNTL5 reads verify observed mode OFF. Sequential control reads are
not an atomic snapshot or proof of continuous hardware state.

Raw register rows, clock timestamps, cached passive snapshot, complete current
kernel journal JSON, endpoint battery state, source hashes and vendor excerpts
are retained. The initial state command used an incorrect passive snapshot
path; its error is retained. A separate `set -e` collection used the exact
source-derived `sm5440-0-0063` path successfully. Shell exit zero alone was not
treated as proof of every subcommand succeeding.

Host tests/build: `executed: false`; no kernel, configuration, DTS, build or
routing inputs changed. Existing qualifications are not a new regression run.
See [RESULTS.md](RESULTS.md) for interpretation and remaining unknowns.
