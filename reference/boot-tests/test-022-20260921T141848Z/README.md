# Test 022 — program the PTN3222 redriver (2026-09-21T14:18:48Z)

The high-speed USB path runs through an NXP PTN3222 redriver on i2c, and no
upstream driver programs it: the generic one enables the supplies and releases
reset, then stops.  This run adds a patch that reads the board DT's
`qcom,param-override-seq` and writes each (value, register) pair over the same
i2c regmap after the documented post-reset interval.

Artifacts: `boot aac25c70…` (PTN3222 patch, no eUSB2 patch), `init_boot
50725fa1…` (RTC diagnostics), `vendor_boot 139e0f5d…`.

## Result: the port opens now, but the data path still fails

- The gadget enumerated again on the host (14:20:49Z, `VID_0525&PID_A4A7` /
  `GTS9WIFI-0001`) and Windows created COM17.
- Unlike test 020, COM17 **opened**, and the monitor read it for 90 seconds -
  but not a single byte arrived, and then the read failed with the same "device
  not functioning" error.  So the patch changed behaviour (the port used to
  refuse to open at all) without making the link usable.
- The report reached the card (checksum-verified) and shows the gadget bound to
  `a600000.usb` with `/dev/ttyGS0` present.
- The PTN3222 is wired as the eUSB2 PHY's supplier and its supplies are enabled
  (`7-004f-vdd3v3 11mA`, `7-004f-vdd1v8 55mA` in the regulator summary), so the
  driver's init ran - but its "applied N register overrides" line never
  appeared, which says the override cells were not read.

## Superseded

The tablet did not power off by itself: the proof was armed *after* the
gadget's infinite shell loop, i.e. never.  That is fixed for test 023, and the
probe log added to the PTN3222 patch for test 024 reports how many override
cells the driver actually sees.
