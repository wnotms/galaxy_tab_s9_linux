# test-097 — stock's 400 kHz bus rate is not the missing condition either

- date: 2026-09-22T13:58:09Z (`reboot system`) – 13:59:12Z (key-press read)
- source: working tree on `0392d2d`; `boot.img fd582dd7…` flashed and read back
- change: `&i2c15 clock-frequency` 100000 -> **400000**, stock's actual rate
  (`qcom,clk-freq-out` is absent downstream, so i2c-msm-geni defaults to 400 kHz and
  the vendor log says `Bus frequency is set to 400000Hz`)
- why it had never been tested: test 059 tried 400 kHz *before* the app-entry reset
  existed, so no application was ever alive on that run

## Result — handshake yes, key reporting no

```
[    4.040520] application-entry reset: BOOT0 low, NRST 2 ms low then high, 150 ms settle, rail on
[    4.171501] MCU announced itself (1)
[    4.379526] packet from the MCU: 03 00 02 (size 3)
[    4.393511] MCU model 0x1 hw 0 firmware 1.4 mode 1
 169:          1  ...  msmgpio     75 Level     5-002a
dmesg | grep -cE "packet from the MCU|key 0x"  ->  1
```

The owner pressed keys on the unfolded cover: still one interrupt, still one packet.
The rate is therefore excluded as the cause of the silence, with the application
demonstrably alive this time.

Timing note (owner instruction): `reboot system` 13:58:09 -> console shell
13:58:35, 26 s, no blind sleep - `scripts/console-run.ps1` returns when the shell
answers.

## Also closed this round: the booster lead

The stock X710 device tree's only `max77816` is `max77816,display_boost@18`, and
TWRP's live regulator list contains no keyboard, booster or pogo supply at all -
just `fixed_regulator${#}`, `panel_ldo_en` and `display_panel_avdd`. The vendor
driver's `kbd_max77816_control(booster_power_voltage)` therefore has nothing to
control on this board either, which is why this port's stub logging
`not support device` matches the hardware rather than diverging from stock.

## What is left

Source and measurement now exclude, with the application alive in each case: the
bus rate (this test), the event wire protocol (same three steps as `stm32_dev_isr`),
a missing start/keep-alive write (stock's only extra hardware action is the booster
call above), the decode path (never given a packet), firmware revision (the same V34
works in TWRP), and pin/level semantics (the gate and active-low are consistent).

The one host-visible *sequence* difference left is that stock runs a bootloader
session at 0x51 and ends it with `stm32_sysboot_disconnect()` before the application
appears. The vendor port does exactly that and still failed to reach the application
(test 070), so this is not obviously it either - but it is the only untested
ordering left that stock performs and this port does not, and it is one boot to
check with the working reset now understood.
