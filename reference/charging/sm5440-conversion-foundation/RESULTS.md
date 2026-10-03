# SM5440 bounded conversion foundation

Implemented the actual uncached-regmap begin/advance/cancel converter operation,
with X710 vendor 20 ms disabled rearm, one-shot AVG32/channel selection, new
completion provenance, mode/live fault verification and original-control cleanup.
No internal sleep or mutex; no old completion/cache publication as fresh. Native
BOOTTIME and connection generation bound the entire request to the unchanged
100 ms software deadline, including cleanup. Zero initialized request disabled.

60 affected actual-C host tests PASS in 0.825 s, no failures/errors/skips.
Coverage includes every single bus error in OFF and running mode, uncertain and
dropped writes, persistent I2C loss/unknown ADC-OFF, cancellation, old READY,
clock regression, transfer deadline, same-ms polling bound, all live/latched
hardware faults, register drift, and exact microvolt/625 uA preservation.
Initial tests failed on treating latch absence as lost VBUSPOK and an incorrect
expectation that a failed disable write always proves ADC OFF. Corrected live
versus latch decoding and explicit unknown-cleanup assertions; original failed
output is retained, not relabelled PASS.

ARM64 single unlinked object W=1/sparse PASS in 4.520 s.
No changed-helper warning; unrelated upstream vDSO declaration warning retained.
Six existing provider hashes, all 98 Test317 sealed inputs and nine formal
candidate/rollback artifacts remain exact. Config and DTB differences empty.
No Image/module relink, Kbuild hook, source/profile change in installed Test317,
full host run, Actions, device command, PPS request, pump ON or charging change.

This is a software measurement transport foundation, not calibrated ADC or
hardware-current-cutoff acceptance. Vendor schedules an ADC worker at 200 ms;
neither it nor Fedora continuous AVG32 proves our 100 ms requirement. No
software-OCP flag is granted. Live integration, native sampling/independent
calibration/current/cutoff qualification and direct-charge/PM physical tests
remain required. Test317 device availability/rollback stays independently
recorded; this offline work does not complete that physical test.

See docs/SM5440_BOUNDED_ADC_TRANSACTION.md, source-audit.json and raw logs.
