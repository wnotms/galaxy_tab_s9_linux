# test-074 — nothing on the bus acknowledges, at any address

- started: 2026-09-22T09:40:00Z
- source commit: `4ae7b7c`
- images: `boot.img 3b8eb80d…` (mainline port); `vendor_boot 3ec6c8d1…` (bias
  change), `init_boot aed8f3c5…` (with firmware), `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-073

## A diagnostic that had to be fixed first

Every "`i2c-5 answers at: (nothing)`" this project has printed was meaningless:
the scan used SMBus QUICK, and this controller's functionality mask is
`I2C_FUNC_SMBUS_EMUL` **without** `I2C_FUNC_SMBUS_QUICK`, so the probe could not
succeed for any address. The scan now writes one byte to an i2c dummy client for
each of a small, deliberate set - 0x2a, 0x2b, 0x2c, 0x2d and the bootloader's
0x51 - which ACKs the address and actually answers the question.

## Result

```
[    4.788103] MCU rail on with BOOT0 low, announce line armed (level 1)
[    4.901336] right after the rail cycle: application -6, bootloader -6, announce level 0
[   76.541014] no answer from the MCU application after 60000 ms (-6)
[   76.710846] i2c-5 acknowledges: (nothing)
```

The MCU drives its announce line - level 1 at power-up, then low, exactly the
sequence stock shows when the application has something to say - and **no I2C
address acknowledges anything**: not the application's 0x2a, not its neighbours,
not the system bootloader's 0x51. Sixty seconds of polling and a real bus probe
both come back empty, while the same part's bootloader answers on the same
controller as soon as the SWCLK dance puts it into boot mode.

So the fault is now stated as narrowly as the measurements allow:

> Under mainline the MCU is powered and running - it asserts the line only the
> application drives - but its I2C slave never serves any address at all. Under
> stock, on the same part, rail, pins and bus, that same firmware serves 0x2a
> within milliseconds of the rail rising.

That is not a host addressing problem, not a framing problem and not a
missing-address problem: the slave itself never comes up. It is also not the
pogo driver (test 070's A/B) and not the firmware path (test 072 reproduced it
value for value).

## Next step

The remaining host-controlled inputs at the moment the application starts are the
two lines it samples and the rail's shape; everything else about the startup has
been reproduced. The next candidate records those at the transition - NRST and
the rail alongside the announce line - and compares them with the same instant in
the stock trace, so that any difference in what the application sees at its
startup is measured rather than inferred.
