# test-062 — the first line-level diagnostic printed nothing (superseded by 063)

- started: 2026-09-22T08:20:00Z
- source commit: `1721ac8` (patch 0008 v1: `geni_i2c_err_misc()` logged at info)
- images: `boot.img edba6aaf…`; init_boot/vendor_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-061

## What it tested

Whether the `-ENXIO` behind every failed transfer is a real address NACK (idle
bus) or a bus that something is holding down: raise mainline's existing
`SE_GENI_IOS` read in `geni_i2c_err_misc()` from `dev_dbg` to `dev_info`.

## Result — no output, and the reason is itself the finding

The candidate booted, the poll failed as usual, and `dmesg` contained no
`geni_ios` line at all. Reading `geni_i2c_err()` explains it: the helper that
reads `SE_GENI_IOS` is called only from the `default:` branch, while NACK and
GENI_TIMEOUT — the only two failures this board produces — log at `dev_dbg` and
skip it entirely. Patch 0008 v2 (`03ccc25`, test 063) raised that path too, and
the measurement then showed `geni_ios:0x7`, an idle bus and a real NACK.
