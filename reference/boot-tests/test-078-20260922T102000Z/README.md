# test-078 — Samsung's own driver, same code path, same failure

- started: 2026-09-22T10:20:00Z
- source commit: `d7a1586`
- images: `boot.img da9d4f1f…` (vendor port); `vendor_boot 3ec6c8d1…`,
  `init_boot aed8f3c5…` (with firmware), `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-077

## What it asked

The stock driver's own application read had never been observed in mainline,
because its state machine gates on the connect line and this board pulses that
line (test 073) - `check_init_work` dropped `connect_state`, stopped the keyboard
and never reached `stm32_check_ic_work -> stm32_read_version`. With the cover kept
considered connected (an experiment, marked as one in the source), the stock code
path runs through to its I2C traffic.

## Result — the stock path fails exactly like the port

```
44.629762 stm32_i2c_write_burst: I2C retry 3, ret:-6
44.639087 stm32_i2c_write_burst: I2C write over retry limit
44.649105 stm32_power_reset, 16
44.656581 stm32_conn_isr (1)
44.682687 stm32_dev_regulator on: vdd:on
```

Samsung's driver, unmodified apart from the connect-line experiment, issues its
own writes to `0x2a` and gets `-6` - the same NACK the mainline port has been
getting since test 046 - and reacts the way its code says it should, with its
retry loop and `stm32_power_reset()`. Before that, in the same boot, it ran
stock's complete firmware path and read the bootloader at `0x51` successfully.

## Where this leaves the investigation

The same board, the same cover, the same firmware in the MCU's flash, and now the
same driver code: the read succeeds under stock and fails under mainline. Every
host-side input that could explain that has been measured and reproduced:

| what the host provides | measured | result |
| --- | --- | --- |
| rail, BOOT0, NRST at the application's startup | test 075 | identical to stock |
| stock's firmware path (checksum, validation, option/empty checks, IC read, disconnect) | test 072 | reproduced value for value |
| no traffic during the first seconds; the application announces itself unprompted | test 076 | the application runs |
| a real address probe over the whole 7-bit range | test 077 | nothing acknowledges, while the bootloader answers on the same controller |
| the driver itself, both implementations | tests 070/078 | both fail identically |

What the host cannot see or set is what the application checks for itself once it
is running - inside the cover, over its own internal bus: the touchpad it
supervises (stock reads it as `ID_TOUCHPAD`, ed_id 2, in test 055's byte log), the
hall and the booster the vendor driver also queries. Those are the only inputs
left, and the vendor driver can now be run here to compare its reads of them with
its own stock behaviour.
