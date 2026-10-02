# Test294 — SM5714 switching ownership, offline

Purpose: implement the missing leased switching-path inhibition backend for
future SM5714/SM5440 handoff without activating PPS or direct charging.
Design: docs/SM5714_SWITCHING_OWNERSHIP.md, written before source edits.
Starting revision: 706811f9, test branch, clean tree.

No physical rounds or device mutations are registered. Preserve fixed-PD,
4440mV/thermal/fault/suspend limits, HVC_DCC=n, Linux 7.2-rc3, Test254 userspace
configuration and USB/ADB/NCM behavior. Actual-C tests, one candidate build,
full host regression, config/DT/protected-file audit are planned. Build directory
will be independent; obsolete 269 intermediates were removed by cleanup.

Current production hardware state was last verified by Test292; Test293's
startup VBAT refusal is not repaired or waived by this change. No hardware
acceptance may be inferred from offline results.
