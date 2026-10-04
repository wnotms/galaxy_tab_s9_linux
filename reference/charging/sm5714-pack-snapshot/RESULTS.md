# Native pack producer and OFF-only consumer — offline qualification

The actual battery driver now acquires gauge SOC/VBAT/signed current and one
real IIO pack thermistor reading under a lifetime pin. It checks native
acquisition time, live attach/presence/health before/after, saturating state
generation, PM/rebind and the exact switching lease. Every error zeros output.
Gauge window operations use sram_lock; core registry/charger locks are not held
across IIO/gauge reads. Unpublication drains readers and synchronizes with the
last put's wakeup before managed resources disappear.

Samsung X710 psy_chg_get_present() identifies battery absence from STATUS2[2].
The API and public battery PRESENT now use that predicate instead of returning
constant 1; I2C failure propagates. The existing OFF-only session consumes the
real native bundle and checks receipt identity/lease/attachment/charge grant.
Its SOC 5–<80%, VBAT 3.5–<4.3V and pack 20–<38C thresholds are unchanged.

- 162 affected actual-C/pthread tests PASS, no skips, 5.774s. Includes 19 real
  pack-provider tests and the existing safety/lease/PM/TCPC/session coverage.
- Final normal ARM64 Image.gz/DT/modules build PASS, 64.202s, same Linux7.2-rc3
  pin/toolchain/shared ccache and reusable build tree. Earlier build before
  final consumer checks is retained separately and is not final qualification.
- Actual battery and OFF-session objects W1/sparse PASS, 7.260s, no changed-driver
  warning. Known upstream vDSO getrandom declaration warning retained.
- Exact 14 hardware-policy/conversion/temperature functions unchanged. No
  current/float/thermal/watchdog programming changes, SM5440 untouched, DCC off.
- DTB byte-identical to accepted311. No DTS/config/rootfs/USB/adbd source change.
  This existing offline profile enables X710_CHARGING_POLICY=y and removes the
  incompatible SM5440_ADC_CONDITION_TEST symbol (`depends on !policy`). Exact
  config diffs vs accepted311 and Test316 retained; Docker/UPower gates pass.
- 136 other kernel/rootfs/build sources and 15 prior formal artifacts unchanged.
- 181 exact paired archive files. 167 `.ko` files differ only in .BTF sections;
  executable/data/version sections unchanged. Three builtin metadata files
  change with the intentionally linked offline policy/session. Use new pairing.
- Native pack API, native PPS observer and actual OFF-roundtrip API/export are
  present in linked vmlinux. No automatic caller, PPS request or pump ON was run.

Failed fixture extraction, PM stimulus and initial config-delta assumptions are
retained and explained in development-corrections.json; no old test was removed,
skipped or weakened to claim success. Full/Actions executed:false under latest
owner affected-only scope. No device command, flash, reboot or charging write in
this turn; prior accepted311 observation is reused as historical state only.

The 500ms bundle bracket records the oldest native acquisition, not an internal
fuel-gauge conversion timestamp or a hard execution deadline. Consumers check
freshness after return; IIO/driver scheduling can delay delivery. Native facts
are not physical ADC calibration/current/cutoff/OCP proof. Test317's 128–130ms
ADC diagnostic brackets remain insufficient for 100ms active qualification.
The real live worker/adapter, physical protection acceptance and native refresh/
fallback/PM tests remain before pump/current escalation. No physical test is
registered by this offline qualification; full charging port **NOT READY**.
