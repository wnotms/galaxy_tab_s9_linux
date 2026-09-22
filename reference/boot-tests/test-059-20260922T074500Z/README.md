# test-059 — the pogo bus at 400 kHz, stock's rate

- started: 2026-09-22T07:45:00Z
- source commit: `d65975e`
- images: `boot.img e699cc5c…`, `vendor_boot.img 8d76f912…`;
  `init_boot.img 12b77d17…`, `dtbo.img c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-058

## Hypothesis

The stock kernel runs this serial engine at 400 kHz: the downstream controller
binding documents `qcom,clk-freq-out` as "when missing default to 400000Hz", and
Samsung's node for this keyboard sets its two `samsung,*` quirks but not that
property, while this port asked for 100 kHz. The STM32's system bootloader
answers at either rate, but its application interface may be timing-sensitive —
which is what a vendor that adds reset-before-trans and stop-after-trans to this
one bus suggests. This separates "the application never runs" from "the
application runs but does not answer the mainline controller at 100 kHz".

Change: one line, DT only — `clock-frequency = <400000>` on `&i2c15`. No driver
change, no bootloader involvement, no reset.

## Result — disproved

```
[    3.123939] MCU rail on with BOOT0 low
[    3.127189] waiting up to 60000 ms for the MCU application
[   66.574550] i2c-5 answers at: (nothing)
[   66.753208] MCU IC version 00340034
[   66.787488] MCU option bytes 0xfefffeaa: RDP 0xaa, bit 24 clear
[   66.972493] after the disconnected reset: application -6, bootloader -6, connect 1
[   97.003194] application after bootloader start: -6 after 30016 ms without reset (no version response)
[   97.017725] five seconds later: application -6, bootloader -6, connect 0
[   97.073071] waiting up to 60000 ms for the MCU application
```

Sixty seconds of read-only polling at 400 kHz found nothing at any address, and
the bootloader answered first try at the same rate. The bus rate is therefore not
what keeps the application silent.

## Conclusion and next step

Two of the plan's stages are now closed by measurement (P0 power-on order, and
the bus rate), and P1/P2 cannot be answered from the official source at all:
neither `samsung,reset-before-trans` nor `samsung,stop-after-trans` is consumed
anywhere in it, so the register-level semantics the plan asks for are not
recoverable there (see test 058's `geni-quirk-source-search.txt`).

What is left is P3: prove the *order* of the transitions at boot with timestamps
rather than guessing — TLMM probe, `pogo_supply` apply, fixed-regulator probe,
keyboard@2a probe, SWCLK/NRST request, rail enable, first I2C transaction — and
compare each with the stock kernel's own timestamps from the same device. The
mainline runtime state is already correct (test 055), so only the transition
order can still differ.
