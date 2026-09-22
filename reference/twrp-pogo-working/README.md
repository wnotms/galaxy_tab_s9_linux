# TWRP / stock-kernel pogo keyboard: the known-good reference

Collected on 2026-09-22T08:22Z from this SM-X710 with the EF-DX710 attached, in
TWRP, whose recovery kernel is the stock Samsung kernel with Samsung's own module
stack. Nothing was written, flashed or reconfigured: every command below only
reads.

**This directory is the "known good" side of the comparison.** In this state the
keyboard works, and the application interface answers:

```
EF-DX710_v1.4.1.0   GET_MODE = 1   CRC32 = EADF376E
```

## Collected evidence

| file | what it holds |
| --- | --- |
| `modules.log` | `/proc/modules` + `lsmod` + the module file location: `stm32_pogo_v3.ko` (from `/lib/modules`), used by `wez01` and `a96t396`, with `sec_input_notifier`, `sec_common_fn`, `sec_tsp_log`, `matrix_keymap` and `sec_class` around it |
| `i2c-clients.log` | every I2C client and adapter, and the two pogo clients |
| `gpio-pinctrl.log` | pinctrl ownership of pins 10/12/13/62/72/75/106 |
| `controller-runtime.log` | runtime-PM state of the controller and the client, the SE's IRQ lines, and the rail's consumer |
| `dmesg-pogo.log` | the dmesg greps - **and their negative result**, see below |

## Facts the collection establishes

**The bus.** The keyboard is on `i2c-44` = `89c000.i2c` inside
`8c0000.qcom,qupv3_2_geni_se` - the same controller mainline enumerates as
`i2c-5`/`89c000.i2c`. Two clients hang off it:

```
44-002a  name stm32_pogo   driver /sys/bus/i2c/drivers/stm32_pogo_i2c
         of_node .../i2c@89c000/stm32@2a
44-0051  name dummy        driver /sys/bus/i2c/drivers/dummy
```

i.e. the application client is a real, bound device from the DT and the
bootloader client is a `i2c_new_dummy_device()` handle, exactly as
`stm32_pogo_v3_start()` creates them.

**The pins.** All seven pins are configured `function gpio`:

```
pin 10  (GPIO_10)  samsung_mobile_device:fixed_regulator@1   function gpio
pin 12  (GPIO_12)  44-002a   function gpio   (GPIO UNCLAIMED)
pin 13  (GPIO_13)  44-002a   function gpio   (GPIO UNCLAIMED)
pin 62  (GPIO_62)  44-002a   function gpio   (GPIO UNCLAIMED)
pin 72  (GPIO_72)  89c000.i2c  function gpio (GPIO UNCLAIMED)
pin 75  (GPIO_75)  44-002a   function gpio   (GPIO UNCLAIMED)
pin 106 (GPIO_106) 89c000.i2c  function gpio (GPIO UNCLAIMED)
```

Two things to note. The rail pin belongs to the fixed regulator, not to the pogo
driver - as it does in mainline. And the reset/SWCLK/connect/IRQ pins are held by
the pogo *device* as a pinctrl group while the GPIO descriptors stay unclaimed,
which is the signature of the vendor's legacy `of_get_named_gpio()` +
`gpio_direction_output()` path rather than gpiolib descriptors.

**The rail.** `fixed_regulator${#}` (gpio10, the stock name for what mainline
calls `pogo-vdd`) is enabled with exactly one consumer, `44-002a-stm32_vddo` -
the pogo driver. Mainline's equivalent state is identical (test 064).

**The controller's interrupts** (`i2c_geni`, GICv3 388-395, 502-505, 611-618) are
registered and have counted transfers, so the stock GENI driver is live on this
bus in this session.

## What this collection could not get, and why

`dmesg-pogo.log` is nearly empty: TWRP's ring held only 1006 lines by the time it
was read, all of them later audit records, because the pogo probe happens in the
first ~35 s of the boot and the ring had rotated. The stock driver's own
bring-up messages were captured in an earlier session instead
(`test-047-20260922T060344Z/posttest-stock-keyboard.txt`, and the byte-level log
in `test-055-20260922T061600Z/stock-i2c-byte-log.txt`).

Capturing the *probe order* as executed needs the module reloaded - `rmmod
stm32_pogo_v3` then `insmod /lib/modules/stm32_pogo_v3.ko` - which re-runs probe
(rail on, IRQ request, firmware path, first reads) and writes its info-level
messages to a fresh ring. That is the next action for this reference, and it
changes no hardware state beyond the rail toggling the way the driver itself
toggles it on every connect.
