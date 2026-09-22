# test-063 — the NACK is real: the bus is idle and the MCU does not answer

- started: 2026-09-22T08:25:00Z
- source commit: `03ccc25` (patch 0008 v2)
- images: `boot.img b1dd9917…`; `vendor_boot 8d76f912…`, `init_boot 12b77d17…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-062

## What this separates

Every failed transfer in this bring-up reported a bare `-ENXIO`, which can mean
either "the slave did not acknowledge its address" or "a bus line is not idle".
The stock kernel's own driver on this bus (`i2c-msm-geni.c`,
`CONFIG_I2C_MSM_GENI`) separates them by reading `SE_GENI_IOS` before every
transfer and returning `-ENXIO` when SCL and SDA are not both high. Mainline
reads the same register, but `geni_i2c_err()` calls `geni_i2c_err_misc()` only
from its `default:` branch — NACK and GENI_TIMEOUT log at `dev_dbg` and skip it —
which is why test 062's first diagnostic printed nothing at all: the two cases
this board hits are exactly the two that print nothing.

Patch 0008 now logs the NACK/timeout message at info level and calls
`geni_i2c_err_misc()` for it. No functional change: no register writes, no new
checks, error codes and recovery path untouched.

## Result — an idle bus and a real NACK

```
[   57.856940] geni_i2c 89c000.i2c: NACK: slv unresponsive, check its power/reset-ln
[   57.876776] geni_i2c 89c000.i2c: m_cmd:0x8005400, geni_status:0x0, geni_ios:0x7 (scl/sda high, idle bus)
[   58.178153] geni_i2c 89c000.i2c: NACK: slv unresponsive, check its power/reset-ln
[   58.197998] geni_i2c 89c000.i2c: m_cmd:0x8005400, geni_status:0x0, geni_ios:0x7 (scl/sda high, idle bus)
... (every retry in the poll window, same two lines)
```

`geni_ios` is `0x7`: both SDA and SCL are high, i.e. the bus is **idle and
healthy**, and the controller is reporting a genuine address NACK. So:

- nothing is holding the bus down (not the MCU in reset, not an unpowered part);
- the port's `-ENXIO` has always been a real NACK, as assumed;
- the STM32 is powered, its bootloader answers at `0x51` on this very controller,
  and it simply does not acknowledge `0x2a`.

This closes the last host-side branch. Together with test 061 (no announce
interrupt and the connect line not driven while the bus is silent) and every
earlier measurement, the fault is now pinned to the MCU's own state: under
mainline the application interface is not being served, while under the stock
kernel it answers on the same hardware within seconds.

## Correction to test 061's wording

Test 061's README says the application "is not running"; the evidence it
collected only shows that it does not announce itself while unpolled, because
stock's byte log shows the MCU announcing *after* the driver's first reads
(test 055). The precise statement the data supports is: the application **does
not serve `0x2a`**, and this test shows that is a real NACK on an idle bus.

## Next step

The remaining host-side difference class is the power/clock state of everything
that feeds the keyboard connector, which the stock kernel sets up and mainline
may not: compare the stock kernel's own `regulator_summary` (already archived in
`test-045-20260922T004902Z/twrp-regulator-summary.txt`) with mainline's
`/sys/kernel/debug/regulator/regulator_summary` for the rails the keyboard cover
consumes, and check the pogo connector's level-shifter/boost supplies rather than
only gpio10.
