# test-058 — P0: GPIO10 kept low until the driver releases the rail

- started: 2026-09-22T07:40:00Z
- source commit: `e2db2ed`
- images: `boot.img 417cd29c…`, `vendor_boot.img b8f2d5ed…` (both carry the changed
  DTB); `init_boot.img 12b77d17…`, `dtbo.img c17418be…` unchanged
- authorization: the owner's P0 direction in this round; standing device-test
  authorization recorded for tests 046-057

## Two possibilities this separates

(a) the application never runs because the MCU is powered before its boot pins
are driven — `pogo_supply`'s `output-high` is applied at the fixed regulator's
probe, before the pogo driver applies its own pin states, so the STM32 came up
with SWCLK (BOOT0) undriven; or (b) the power-on order is irrelevant.

Change, one hypothesis only: `pogo_supply` is `output-low`, so gpio10 cannot
power the MCU before the driver enables the rail, and the first bring-up is the
minimum stock performs here — SWCLK low, **NRST untouched**, rail on, then a
read-only `CHECK_VERSION` poll for up to 60 s with no pin changes, no `0x51`
access and no GO. The bus-silence experiment from the previous commit is
reverted.

## Result — (b), the power-on order is not the cause

```
[    4.093424] samsung-pogo-keyboard 5-002a: MCU rail on with BOOT0 low
[    4.150393] samsung-pogo-keyboard 5-002a: waiting up to 60000 ms for the MCU application
[   67.965781] samsung-pogo-keyboard 5-002a: no answer from the MCU application after 60000 ms (-6)
[   68.037051] samsung-pogo-keyboard 5-002a: MCU application did not answer; entering its bootloader
[   68.172986] samsung-pogo-keyboard 5-002a: MCU bootloader took the 0xFF sync
[   68.185817] samsung-pogo-keyboard 5-002a: MCU bootloader version 0x12
[   68.198333] samsung-pogo-keyboard 5-002a: MCU IC version 00340034
[   68.241627] samsung-pogo-keyboard 5-002a: MCU option bytes 0xfefffeaa: RDP 0xaa, bit 24 clear
[   68.424361] samsung-pogo-keyboard 5-002a: after the disconnected reset: application -6, bootloader -6, connect 1
```

The rail came up with BOOT0 low, sixty seconds of read-only polling changed
nothing on any pin, and `0x2a` stayed silent while the bootloader answered on the
first try. The power-on ordering is not the cause, and the answer is not on the
STM32 side at all: with SWCLK low, the rail released and NRST left alone, the
part behaves exactly as it did when the rail was powered early.

## GENI quirk search (P1/P2) — the consumer is not in the official source

`geni-quirk-source-search.txt`: neither `samsung,reset-before-trans` nor
`samsung,stop-after-trans` appears in any file of the official release — not in
`common/drivers/i2c/busses/i2c-qcom-geni.c` (747 lines), not in
`msm-kernel/drivers/i2c/busses/i2c-qcom-geni.c` (747), not in Qualcomm's
downstream `msm-kernel/drivers/i2c/busses/i2c-msm-geni.c` (2993), not in
`qcom-geni-se.c`, and not in the controller's own binding. So the exact
register-level semantics the plan asks for cannot be recovered from this source:
the consumer is not shipped (proprietary), or the properties are inert on this
build. Reusing the retired `geni_se_rearm()` patch would still be a guess.

The same binding does document one measurable difference:

```
 - qcom,clk-freq-out : Desired I2C bus clock frequency in Hz.
   When missing default to 400000Hz.
```

The official X710 pogo node sets `samsung,reset-before-trans` and
`samsung,stop-after-trans` but **not** `qcom,clk-freq-out`, so stock runs that
serial engine at 400 kHz, while this port's DTS sets `clock-frequency =
<100000>` on the same controller. That is a one-line, DT-only difference between
a configuration that works and one that does not, and it is test 059.
