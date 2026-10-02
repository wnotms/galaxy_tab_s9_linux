# Test295 — startup paired-voltage diagnostic

Offline implementation followed by separately registered ONE physical boot.
Purpose: compare SM5440 OFF-mode startup VBAT with nearby SM5714 live SRAM
voltage, including read timestamps. No PPS, pump ON, current increase, ADC
sequence/threshold/deadline changes. Existing startup refusal stays latched.
Design: docs/SM5440_STARTUP_PAIRED_VOLTAGE.md.

Affected SM5440 suites:208 tests PASS,10 new actual-C/helper/scope cases;
8.218 seconds. No routine full regression: unchanged qualification reused from
Test294; no routing/build integration changes. Candidate build and separate
physical registration pending. No device mutation yet.
