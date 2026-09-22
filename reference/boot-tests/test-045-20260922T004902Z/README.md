# Test 045 — the pogo keyboard is driven, and mainline cannot reach its MCU (2026-09-22T00:49Z)

The EF-DX710 driver works as a driver and the cover works as hardware, but
mainline still cannot talk to the keyboard's STM32.  This test found and fixed
four real faults, and then narrowed the remaining one to a single, documented
difference between the vendor's I2C controller and mainline's.

Authorization: the owner asked for a physical test (`进行实机测试`) on 2026-09-22;
that request is recorded in `source.txt`, as the test rule requires.

Artifacts: final `boot fe218fd5…` (kernel Image.gz with the polled handshake and
the bus scan), `vendor_boot 66c7ddc5…` (the DTB with `swclk-gpios`/`nrst-gpios`),
`init_boot 3198ae1f…` unchanged.  Every flash was a verified read-back; the
pretest boot/init_boot/vendor_boot/dtbo/vbmeta are backed up under
`.work/backups/test-045-20260922T004902Z/` and their hashes are in
`device-layout.txt`.  Vendor_boot was checked to carry the *same* cmdline as the
device before it was flashed.

## The owner's observation is also display evidence

While this test was running the owner reported the panel repeatedly showing
`pogo keyboard connect line` messages.  That is the console being read on the
panel - independent confirmation that test 040's display fix holds across boots -
and it is why the connect-line read is now `dev_dbg` instead of a ratelimited
`dev_info`.

## Four faults found and fixed

1. **The connect line is not a presence level.**  The first build logged
   `keyboard disconnected` on a tablet whose stock firmware enumerates the
   keyboard.  Samsung's node declares `stm32,irq_conn` with
   `irq_conn_type = 0x2003` (`IRQ_TYPE_EDGE_BOTH`) and pinctrl `bias-disable`, so
   the level is undefined when nothing drives it; the vendor driver only ever
   treats it as an edge.
2. **Cycling the rail on every edge was worse.**  37 connect interrupts and a
   `rail on (connect line reads 0/1)` pair repeated in the first seconds: each
   edge reset the STM32 before it could announce anything.  The rail is now
   enabled once and stays on.
3. **The console flooded.**  At ~10 Hz the diagnostic filled the panel; it is now
   `dev_dbg`.
4. **The handshake was passive, and it is active in stock.**  The port waited for
   an unsolicited announcement that never comes.  Samsung's driver polls
   `STM32_CMD_CHECK_VERSION` (0x02, four bytes: hw revision, model id, firmware
   minor, major) and `STM32_CMD_GET_MODE` (0x01), resetting with
   `stm32_power_reset()` on every failed attempt.  The poll, the reset-per-retry
   and the SWD pins (`swclk-gpios`, `nrst-gpios`, pulsing NRST low for 10 ms
   after the rail is up) are now implemented.

## What mainline sees now

```
[    3.070297] input: Book Cover Keyboard Slim (EF-DX710) as /devices/platform/soc@0/8c0000.geniqup/89c000.i2c/i2c-5/5-002a/input/input0
[    4.043981] samsung-pogo-keyboard 5-002a: pogo rail on, MCU out of reset, reading its version
[    7.323968] samsung-pogo-keyboard 5-002a: no answer from the MCU after 40 resets (-6)
[    7.373228] samsung-pogo-keyboard 5-002a: i2c-5 answers at: (nothing)
```

`-6` is `-ENXIO`, a NACK: the transfer ran, the bus was idle and nothing
acknowledged the address.  The one-shot quick-write scan then finds **no device
at any address** on the adapter.

## The hardware and the bus are not the problem

TWRP's stock kernel, on this same tablet with this same cover, answers in the
same session:

```
stm32_pogo_i2c 44-002a: [sec_input] mcu_fw(bin):34, mcu_fw(ic):34, EF-DX710_v1.4.1.0
stm32_pogo_i2c 44-002a: [sec_input] TC_vFF00.9, con:1/1, int:1, depth:0, rst:0, hall:0 model_id:0x2
```

and `/proc/bus/input/devices` lists `Book Cover Keyboard Slim (EF-DX710)`.  That
also answers the question the driver could not: `con:1` is
`gpio_get_value(gpio_conn)` in Samsung's code, so a seated keyboard does drive the
connect line high - mainline sees it toggling because nothing is driving it.

The ground truth captured in `twrp-gpio-truth.txt` shows the stock kernel leaves
gpio12/13/62/75 unclaimed (pinctrl-only) and claims only gpio10, through
`fixed_regulator@1` - the same rail model the board node uses.  In mainline the
multiplexing is also correct:

```
pin 72 (GPIO_72): device 89c000.i2c function qup2_se7 group gpio72
pin 106 (GPIO_106): device 89c000.i2c function qup2_se7 group gpio106
pin 10 (GPIO_10): device regulator-pogo function gpio group gpio10
```

The vendor node puts the keyboard on the same controller (`i2c@89c000`, exactly
the pins gpio72/gpio106, `qup2_se7`) with `reg = <0x2a>`, `irq_gpio` = gpio75 and
`irq_type = 0x2008` (`IRQ_TYPE_LEVEL_LOW`) - all of which the board node matches.

## The one difference left

The vendor's `i2c@89c000` node carries two quirks mainline's geni driver does not
implement:

```
samsung,reset-before-trans;
samsung,stop-after-trans;
```

Stock resets the SE before every transfer.  That is the remaining candidate for
"the same controller, the same pins, the same address, and only the stock kernel
gets an answer", and it is the next thing to port - as a local patch to
`i2c-qcom-geni`, under the patch queue's rule for an SM-X710 quirk that is not
upstream yet.

## Evidence in this directory

| file | what it holds |
|---|---|
| `console-poll.log`, `console-retry.log`, `console-scan.log` | the handshake results, including the empty bus scan |
| `console-pinmux.log` | mainline's pin ownership: `89c000.i2c` on gpio72/106, `regulator-pogo` on gpio10 |
| `twrp-gpio-truth.txt` | the working state from TWRP: stock log, pin ownership, input device |
| `bringup-report*.txt` | the four boot reports from the iterated kernels |
| `device-layout.txt`, `pretest-and-flash.log` | pretest hashes, backups and every verified flash |
| `console-gpio.log`, `console-reattach.log` | the earlier connect-line observations |
