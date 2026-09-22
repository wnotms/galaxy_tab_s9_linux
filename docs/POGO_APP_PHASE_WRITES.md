# What stock does in the application phase, and what this port does not

Scope: the host-side actions between the MCU's model announcement and key reporting,
read out of Samsung's own driver in `kernel/drivers/input/samsung-pogo/` (the
imported vendor port) and the official tree at
`/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/`. Every
claim below is a source read, not a device measurement.

## The event sequence is the same on both sides

`stm32_dev_isr()` (`stm32_pogo_interrupt_v3.c:354`) and this port's `pogo_irq()`
perform the same three wire steps, in the same order:

1. gate on the interrupt line being asserted - `if (gpiod_get_value(stm32->dtdata->gpio_int))
   return IRQ_HANDLED;` (vendor `:361`); this port gained the equivalent gate, see
   commit `f9a0361`. The MCU asserts by pulling the line **low**;
2. write the 3-byte header - `stm32_i2c_header_write(stm32->client, stm32_caps_led_value, 0)`
   (`:265`), which is `stm32_i2c_write_burst(client, buff, 3)` (`stm32_pogo_i2c_v3.c:153`),
   against this port's `pogo_write(p, header, sizeof(header))` with `{3, 0, caps}`;
3. read 3 bytes, take the little-endian size from the first two and subtract 3
   (`:268-271`), against this port's `pogo_read()` plus `get_unaligned_le16()`.

A `payload_size` of zero or larger than the maximum is the model announcement on both
sides, and a non-zero in-range size is read as the event payload.

## What stock does with the model announcement that this port does not

Inside that branch (`:272-289`) stock runs four things after reading the version:

| action | file:line | wire effect | this port |
| --- | --- | --- | --- |
| `stm32_read_version()` | `:276` | i2c reads | does it (`pogo_read_mcu()`) |
| `atomic_set(check_ic_flag)` + `schedule_delayed_work(check_ic_work, 10 ms)` | `:279-280` | none, internal retry | absent |
| `atomic_set(check_conn_flag)` + `stm32_send_conn_noti()` | `:281-282` | none, notifier only | absent (no notifier stack) |
| `kbd_max77816_control(stm32, booster_power_voltage)` | `:283` | **regulator enable** | absent - and its stub logs `kbd_max77816_control : not support device` |

The first three cannot explain a silent MCU: two are internal bookkeeping and the
version read already succeeds here (`MCU model 0x1 hw 0 firmware 1.4 mode 1`).

The fourth is the only one that would change the hardware. It is also the one the
imported port already reported as unsupported: test 070's log contains
`kbd_max77816_control : not support device`, because the booster regulator is not
described in this board's device tree.

## The open question, stated honestly

For the X710, `AGENT.md` records the owner's finding that the supplied board node
does not describe an S9 Ultra style keyboard booster, and warns that the X710's
MAX77816 display supply must not be treated as a keyboard supply. If that is right,
stock's booster call is a no-op on this board too, the wire protocols above are
identical, and the difference that makes stock's keyboard report keys has to be
elsewhere - which is where the investigation stands.

Two ways to settle it, both cheap:

1. **Check the stock environment, not the source**: in TWRP, where the keyboard
   demonstrably works on this same unit and firmware, read the regulator list and
   see whether any keyboard/booster supply exists at all
   (`cat /sys/kernel/debug/regulator/regulator_summary` or the TWRP dmesg). If there
   is no keyboard booster, this lead is closed by measurement rather than inference.
2. **Log what the MCU does after the handshake** with the current test-096 style
   build: the added gate already distinguishes "delivered while released" from "no
   delivery at all", and the raw packet log prints anything that does arrive. That
   keeps the search on the wire where the evidence is.
