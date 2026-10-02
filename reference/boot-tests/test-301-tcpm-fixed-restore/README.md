# Test301 — standard TCPM fixed restoration, offline qualification

Purpose: fix capability/active-mode classification and implement a kernel-only
standard ONLINE=1 restoration prerequisite, retaining fixed-only actual Requests.
Source baseline: c23c48c4, currently retained Test299/Test300 device source9173df11.
Linux pin a13c140cc289c0b7b3770bce5b3ad42ab35074aa (7.2-rc3).

No device operation, flash, reboot, rootfs change, PPS activation, pump ON or
current increase is registered here. No live coordinator consumer is installed.
See docs/SM5714_TCPM_FIXED_RESTORE.md for API preconditions/limits and the separate
future physical purpose. Preserve Test300 retained fix and all rollback evidence.

Coverage: actual runtime/provider C with real pthread mutexes and faulted standard
properties/setter; actual companion C lease check with no I2C; affected SM5714
policy/transport/safety tests. One incremental ARM64 Image/DT/modules build, W=1
and sparse on changed objects, exact Test299 config/DT comparison, protected-file
and paired 181-file audit. Reuse unchanged full-suite qualification; no Actions.

Stop qualification on build/test/config/DT/protected identity failure. No failed
mock or successful mock is hardware proof. Active Stage3 remains NOT READY.
