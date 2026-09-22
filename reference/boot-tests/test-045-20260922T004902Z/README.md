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

## Two more candidates tried on hardware, both retired

Neither fixed it, and both are recorded because they narrow the field:

- **`samsung,reset-before-trans`** (the vendor's I2C quirk, patch 0007).  The
  first implementation called `geni_load_se_firmware()` and failed before
  touching the bus - SM8550 sets no `firmware-name`, so every transfer returned
  `-22` instead of a NACK.  Rewritten to replay the register sequence
  (`geni_se_rearm()`), the transfers came back clean and the MCU still did not
  answer.  The quirk is correct but it is not the missing piece, so it is held in
  `kernel/patches/pending/`.
- **Power-cycling the rail** instead of only enabling it, in case mainline's
  regulator core drops it before the driver claims it and leaves the MCU
  brown-out latched.  `pogo rail power-cycled, MCU out of reset` then the same
  `-ENXIO` and the same empty scan.

## What the evidence now says

Everything on the host side is right, and each item was measured rather than
assumed: the controller owns `qup2_se7` on gpio72/gpio106, the rail is
`regulator-pogo` on gpio10 driven high, SWCLK is driven low and NRST is pulsed
and released, the address is 0x2a with `IRQ_TYPE_LEVEL_LOW`, and the transfers
complete - a NACK is the hardware reporting that the bus was idle and nothing
acknowledged.  The slave is simply not running in mainline, and is running for
TWRP's stock kernel minutes earlier, on the same tablet and cover.

The remaining suspect is therefore outside the keyboard driver: the pogo rail is
a *switch*, and whatever feeds it has to be on as well.  The next measurement is
the stock kernel's `regulator_summary` in TWRP, to see which supply feeds that
rail and whether mainline leaves it disabled.

## Round 2: the rail is on in both kernels, and the bus lines are next

The stock kernel's regulator table was captured in TWRP
(`twrp-regulator-summary.txt`) and compared with mainline's from the same boot
(`bringup-report-cycle.txt`).  The pogo rail is enabled in **both**:
`fixed_regulator${#} use=1 open=1` in stock, `pogo-vdd use=1 open=1` in mainline,
each with its client as the consumer.  A full name-keyed diff is not conclusive
because the two trees name the PMIC rails differently (`pm_humu_l13` against
`vreg_l13b_3p0`), but no rail that matters here - pogo, panel, USB, UFS, the MMP
and display GDSCs - is on in stock and off in mainline.  The rail's *source* is
not modelled as a parent in either tree, since the fixed regulator has no
`vin-supply`.

Samsung's v3 driver (`stm32_pogo_i2c_v3.c`) prints **scl/sda levels** on a failed
transfer, which is the measurement this investigation still lacks: a clean NACK
says the bus was idle, not whether a line is being held.  Reproducing that took
three attempts, and the first two are worth recording:

1. `devm_gpiod_get_optional(dev, "sda"/"scl", GPIOD_IN)` fails with **-EINVAL**
   while the pins are multiplexed to `qup2_se7` - gpiolib will not hand out a pin
   the controller owns.  That is why the vendor reads them with `gpio_get_value()`
   on numbers it never claims.
2. `of_get_named_gpio()` no longer exists in this kernel, so the unclaimed-read
   route is not available either.

The remaining approach, now in place, is a **"recovery" pinctrl state** that moves
gpio72/gpio106 to plain GPIOs, after which they can be claimed, read and clocked:
nine clocks plus a STOP is the standard I2C recovery and doubles as the fix if the
bootloader left the bus held.  The DTB carries the state and the board node
references it (`pinctrl-names = "default", "recovery"`, verified in both the built
DTB and the live tree), but the driver logged neither `bus before recovery` nor
`bus after recovery`, which means `pinctrl_lookup_state()` returned an error and
the code skipped the whole path - **silently, because its error branches do not
log**.  That is the next thing to fix, and it is four lines: report why
`devm_pinctrl_get()` or the state lookup failed, then read the levels.

## Round 3: what the TWRP tree shows, and the 0x51 bootloader interface

The owner pointed at the source tree TWRP is built from
(`/home/ms/Samsung/android_device_samsung_gts9wifi`).  It builds against a
**prebuilt stock kernel** (`prebuilt/kernel`, `TARGET_FORCE_PREBUILT_KERNEL`), a
prebuilt `dtb.img` and `dtbo.img`, and its ramdisk loads Samsung's module stack
(`stm32_pogo_v3.ko` plus `sec_input_notifier`, `sec_common_fn`, `matrix-keymap`
and eight more).  So the working environment is stock 5.15 plus stock firmware
blobs - not a configuration mainline can copy directly.

Two things came out of it that matter:

1. **Stock's log shows `rst:0`** - the MCU answered on the *first* attempt, with
   no reset needed.  The keyboard was already running when the stock driver
   probed at 33 s, so nothing in that driver powers it up from cold.  In mainline
   it is dead at 4 s and no amount of rail or reset work revives it.
2. **`stm32_pogo_v3_start()` talks to `0x51` first.**  Its first action is
   `stm32_i2c_new_dummy(stm32, boot_addr)` with `boot_addr = 0x51`, then
   `stm32_dev_firmware_update_menu(stm32, 0)` - the STM32's **system bootloader**
   interface, which the driver also treats specially everywhere else
   (`client->addr != 0x51` guards the power-reset and connect-state logic).  The
   application interface at 0x2a is only used after that flow, and the bootloader
   is entered with NRST low, SWCLK **high**, NRST released, then SWCLK low again
   (`stm32_sysboot_connect`).

The bus scan already covered 0x08-0x77, so 0x51 was probed and also NAKed.  That
does not make the interface irrelevant: the scan is a quick-write probe, and this
is the address to talk to next.

**Next step:** implement the bootloader handshake - instantiate 0x51, run the
`sysboot_connect` pin dance, send the SYNC frame - and see whether the MCU answers
*there*.  If it does, the part is alive and the problem is moving it into the
application; if 0x51 NAKs as well, the MCU is unpowered and the question moves off
the driver entirely, to the connector's supply.

### The bootloader protocol, ready to implement

All of it is in `stm32_pogo_fw.c` and `stm32_pogo_v3.h`:

| item | value |
| --- | --- |
| bootloader I2C address | `0x51` (`boot_addr` in `stm32_pogo_v3_start`) |
| initialise / SYNC command | `STM32_BOOT_I2C_CMD_SYNC` = **0xFF** |
| ACK / NACK responses | **0x79** / **0x1F** |
| version command | `0x01` followed by its complement (`0xFE`) |
| id command | `0x02` followed by its complement (`0xFD`) |
| startup delay | `STM32_BOOT_I2C_STARTUP_DELAY` = 50 ms |
| sync retries | 3, 50 ms apart |

Entering the bootloader (`stm32_sysboot_connect`): NRST low, SWCLK **high**,
3 ms, NRST released, 50 ms, then SWCLK low.  Sending `0xFF` afterwards is the
handshake: a `0x79` response proves the MCU is powered and executing, and a NACK
(or the bus staying quiet) proves it is not.

So the next implementation is small and its outcome is binary: instantiate 0x51,
do that pin dance, write `0xFF`, read one byte.  ACK means the part is alive and
only has to be moved into the application (SWCLK low, NRST pulse - which the
driver already does); NACK means the MCU is unpowered and the problem is the
connector's supply, not the driver.

## Round 4: the MCU is alive - its bootloader answers

Implementing the 0x51 handshake settled the biggest open question.  The driver now
instantiates the bootloader client, holds SWCLK high across an NRST pulse as
`stm32_sysboot_connect()` does, writes the single `0xFF` sync, then re-enters boot
mode and reads the version, exactly as stock does:

```
[    4.086091] samsung-pogo-keyboard 5-002a: MCU bootloader took the 0xFF sync
[    4.438800] samsung-pogo-keyboard 5-002a: MCU bootloader version 0x12
[    8.215872] samsung-pogo-keyboard 5-002a: no answer from the MCU after 40 resets (-6)
[    8.273392] samsung-pogo-keyboard 5-002a: i2c-5 answers at: (nothing)
```

So the part is **powered and executing**, its rail is fine, and the bus, pins and
address are all correct.  What does not happen is the *application*: after the
vendor's `stm32_sysboot_disconnect()` sequence (SWCLK low, NRST low, NRST high,
150 ms) the bootloader stops answering and 0x2a never does either.  The MCU is not
dead - it has simply left the bootloader without the application coming up, which
is what a boot-mode selection problem looks like.

### A pin conflict mainline has and the vendor's working case does not exercise

mainline's `sm8550.dtsi` puts the digital microphones on **gpio12 and gpio13**:

```
dmic45-default-state {
        clk-pins  { pins = "gpio12"; function = "dmic3_clk";  };
        data-pins { pins = "gpio13"; function = "dmic4_data"; };
};
```

Those are the keyboard's SWCLK and NRST.  A live check showed `device 5-002a
function gpio` on both while this driver held them, so they are not being taken
today, and TWRP never probes audio at all - but it is a real hazard for any boot
where the DMIC driver applies its state after this one, and it is the first thing
to rule out if the application starts and then dies.

### Next step: start the application explicitly

The bootloader's own jump command is `STM32_BOOT_I2C_CMD_GO` = **0x21**
(`stm32_pogo_v3.h`).  Stock's `sysboot_mcu_chip_command()` has the case but only
sets `cmd[0]` and breaks, so it never sends it - which means the vendor relies on
the reset-with-SWCLK-low to start the application AND never exercises it in a case
mainline has to handle.  Sending 0x21 to 0x51 after the version read, then reading
0x2a again, is the next measurement: it either brings the application up (and the
keyboard works) or it does not, and either way the boot-mode question is answered.

## Round 5: the display regression, fixed and confirmed

The owner reported a blank screen mid-round.  The cause was in the boot script, not
the panel: `display_recover` cycled the framebuffer as soon as `fb0` appeared, and
on this boot that was 5.91 s while the panel driver logged its first read at
6.29 s.  The cycle therefore re-initialised a link that had not come up yet, the
recovery's own success check failed, and nothing retried - so a display that
worked in test 040 stayed dark.

The recovery now waits for the driver's own line (`ana38407 panel id: 00 00 00`,
not the summary that follows it) before touching the framebuffer, and retries the
full blank/unblank cycle up to three times, stopping at the first `80 00 04`:

```
[    5.460473] ana38407 panel id: 00 00 00
[    5.943551] gts9-init: display: framebuffer cycle for first-enable zero ID
[    6.327614] ana38407 panel id: 80 00 04
[    6.523423] gts9-init: display: cycle 1 recovered panel ID 80 00 04
[    7.544907] gts9-init: display: wrote a marker line to /dev/tty0
```

Cycle 1 recovers it, 1.7 s earlier than test 040's single cycle did, and the owner
confirms the console is visible again.

## Round 5 keyboard: two app-entry attempts, both measured

With the bootloader reachable, both ways of starting the application were tried on
hardware and both failed, which is itself the useful result:

```
[    4.080860] MCU bootloader took the 0xFF sync
[    5.325535] application after the reset entry: -6 (did not start)
[    6.397110] MCU bootloader GO (0x21): -110
[    7.584067] application after GO: -110 (still not running)
```

The reset entry uses the vendor's exact `stm32_sysboot_disconnect()` timings
(SWCLK low, 1 ms, NRST low, 2 ms, NRST high, 150 ms) and 0x2a still NAKs.  The GO
write then times out (-ETIMEDOUT, not a NAK): by that point the MCU answers on
neither interface, so the part has left the bootloader without the application
coming up on i2c.

**Next step:** stop disturbing it.  Stock's log has `rst:0` - the application was
already running when its driver probed, and that driver never powers the rail,
pulses NRST or enters the bootloader to get there.  Everything this port does to
"help" (rail power-cycle, bootloader dance, reset entry) happens to a part that the
bootloader has probably already started, and each reset is a chance to lose it.
Reading 0x2a first, with no rail cycle and no reset, is the next measurement - and
if that answers, the keyboard works and the helping was the fault.

## Round 6: read-first disproved, and the retry saved a second boot

Two results, one for each half of the objective.

**Display.** The next boot after the fix needed **cycle 2**: cycle 1 ran at 6.49 s and
did not recover, cycle 2 recovered `80 00 04` at 7.25 s.  The panel comes up on the
first cycle or the second depending on how the boot settles, so the retry is not
belt-and-braces - without it that boot would have been dark again, exactly like the
one the owner reported.

```
[    5.473217] panel id 00 00 00, expected 80 00 04
[    6.275531] ana38407 panel id: 00 00 00
[    6.486864] gts9-init: display: cycle 1 did not recover the panel ID yet
[    7.250613] ana38407 panel id: 80 00 04
[    7.396642] gts9-init: display: cycle 2 recovered panel ID 80 00 04
```

**Keyboard: "read the application first" is disproved.**  The build that enables the
rail and reads 0x2a *before* touching SWCLK, NRST or the bootloader logged no
"application already running" line - the app does not answer first either.  So the
MCU really does sit in its system bootloader in mainline, and after the bootloader
session plus either app-entry attempt it goes quiet on both interfaces.

**The DMIC pin sharing is not a mainline bug.**  The vendor's own DT puts
`dmic45_clk_active`/`dmic45_data_active` on **gpio12 and gpio13** with
`function = "func1"` - the same two pins as the keyboard's SWCLK and NRST.  It is
genuine hardware sharing, present in both trees, and not active here: the pinmux
still shows those pins owned by `5-002a` minutes into the boot because mainline's
audio stack never comes up.

### Next step: send GO while the bootloader is still live

The GO attempt failed for a timing reason, not a protocol one: it was sent *after*
`sysboot_disconnect()` and its 150 ms, by which point the MCU had already stopped
answering - the write returned `-ETIMEDOUT`, not a NAK.  Inside the bootloader
session the interface is alive (SYNC and GET_VER both work), so the next attempt is
SYNC → **GO** → read 0x2a, with no reset in between.
