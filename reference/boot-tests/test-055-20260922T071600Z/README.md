# test-055 — reference traces from the official source and from a working stock session

- date: 2026-09-22T07:16:00Z
- no kernel was flashed and no partition was written in this test; it collects
  reference evidence with the tablet in TWRP (stock kernel) and in mainline
- authorization: owner asked to continue the repair and pointed at the official
  source in the parent folder ("可以参考上级文件夹中的官方源码")

## 1. Samsung's official SM-X710 source confirms the configuration

`SM-X710_EUR_15_Opensource.zip` (parent folder) carries the kernel source for
this exact model. Its pogo node
(`arch/arm64/boot/dts/samsung/galaxytab/gts9wifi/gts9wifi_eur_open_w00_r04.dts`)
is archived in `official-x710-pogo-node.txt` and names:

| property | official value | mainline port |
| --- | --- | --- |
| `stm32,irq_gpio` | gpio 75 | gpio75, level-low |
| `stm32,irq_conn` | gpio 62 | gpio62, edge-both |
| `stm32,mcu_swclk` | gpio 12 | gpio12, output-low |
| `stm32,mcu_nrst` | gpio 13 | gpio13, output-high |
| `stm32,sda_gpio` / `scl_gpio` | gpio 72 / 106 | gpio72 / gpio106 |
| `stm32_vddo-supply` | fixed regulator on gpio 10 | `vreg_pogo`, gpio10 |
| `stm32,fw_name` | `keyboard_stm/stm32_gts9family.bin` | no firmware file used |

This is the third independent source for the same numbers (the port's DT, the
device's own `dtbo.img` overlay, and now Samsung's OSS DTS), so the hardware
description is not in question.

The driver tree is equally settled: `diff -rq` between the official X710
`drivers/input/sec_input/stm32/` and the X910 copy this port was written from
(`official-driver-diff.txt`) shows the shared files are **identical** — including
`stm32_pogo_fw.c`, `stm32_pogo_cmd_v3.c` and `stm32_pogo_core_v3.c` — and the
only extra files are the v1/v2 variants, which this device does not use (TWRP
loads `stm32_pogo_v3.ko`, i.e. `TARGETV3`). The startup and protocol analysis
behind the port is therefore against the right code.

The official release does **not** ship `stm32_gts9family.bin` (its
`firmware/keyboard_stm/` has only gts7l, gts7llite and birdie), and TWRP reports
`get_fw_ver_bin: EF-DX710_v0.0.0.0` with `check_fw_update: NG`.

## 2. A working stock session, byte for byte

With the tablet in TWRP the stock driver's own switch was turned on
(`echo 1 > /sys/class/sec/sec_keypad/debug_level`, `BIT(0)` = I2C byte log) and
its bring-up re-run through `keyboard_connected` (`stock-bringup-trigger.log`).
The live application answered, and its protocol is exactly the port's
(`stock-i2c-byte-log.txt`):

```
stm32_i2c_write_burst: 04 00 01      <- payload size 4 (LE), ed_id 1 (MCU)
stm32_i2c_write_burst: 02            <- CHECK_VERSION (0x02)
stm32_i2c_read_bulk:   07 00 01      <- reply header: payload 7, id 1
stm32_i2c_read_bulk:   00 01 04 01   <- hw_rev 00, model_id 01, minor 04, major 01
stm32_read_version: [IC] version:1.4, model_id:01, hw_rev:00
...
stm32_i2c_write_burst: 04 00 01 / 01 -> GET_MODE -> read_bulk 04 00 01 / 01  -> [MODE] 1
stm32_i2c_write_burst: 04 00 01 / 03 -> read 07 00 01 / 6E 37 DF EA -> CRC32 0xEADF376E
stm32_i2c_write_burst: 04 00 02 / 18 -> the touchpad (ed_id 2)
```

Every frame matches the port's `pogo_read_reg()`/`pogo_write_reg()`: the same
three-byte header `{4, 0, 1}`, the same `len + 3` length field, the same "id last"
byte, the same per-command byte. `get_fw_ver_ic` reads `EF-DX710_v1.4.1.0` and
`get_crc` reads `EADF376E`.

## 3. The stock driver never runs its bootloader session on this device

`request_firmware("keyboard_stm/stm32_gts9family.bin")` fails in TWRP (no such
file), so `stm32_dev_firmware_update_mode()` returns before
`stm32_dev_checksum()`, before `stm32_sysboot_mcu_validation()` and before any
`stm32_sysboot_disconnect()`. The rail is only enabled afterwards, in
`stm32_interrupt_init()`. So on this device the stock stack reaches a working
application **without ever entering the system bootloader, without the SWCLK
dance, without GO and without touching NRST**: the application runs from
power-on, and the driver only reads it.

That is the opposite of what the port does first, and it explains why every
bootloader-side success in tests 046-054 was beside the point: the question is
why the application does not run in mainline at power-on, not how to start it.

## 4. Mainline's pin state at runtime is correct

`mainline-pin-state.log`, read over the console from the running mainline kernel:

```
gpio10  : out high func0 2mA no pull      <- the MCU's rail, enabled
gpio12  : out low  func0 2mA no pull      <- SWCLK / BOOT0, driven low
gpio13  : out high func0 2mA no pull      <- NRST released
gpio62  : in  low  func0                  <- connect line
gpio75  : in  high func0                  <- announce line, idle high
pin 72/106: device 89c000.i2c function qup2_se7
```

By the time the driver has probed, every line is in the state the stock kernel
leaves it in. The open difference is *when* gpio10 goes high: in mainline it is
the regulator's pinctrl default state (`output-high`), applied at the fixed
regulator's probe — before the pogo driver applies its own pinctrl state and so
before gpio12 is driven low — while in stock the rail is switched by
`stm32_dev_regulator(1)` in `stm32_interrupt_init()`, after the driver owns
those pins. If this part latches its boot source at power-on, mainline powers it
with BOOT0 undriven and the application never comes up, which is what every
measurement so far shows. Test 056 tests that ordering directly.
