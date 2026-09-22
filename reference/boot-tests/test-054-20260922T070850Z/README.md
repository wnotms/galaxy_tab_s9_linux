# test-054 — a real power-on with BOOT0 low, and the gadget is the console only

- started: 2026-09-22T07:08:50Z
- source commit: `762828a`
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img efb5b992…` and `vendor_boot.img 6b24a946…` (the command line
  changed) from `out/boot-bundle-test054`; `init_boot.img 12b77d17…`,
  `dtbo.img c17418be…` unchanged
- authorization: owner asked to continue the repair, to reduce the wait between
  system switches, and for the card's automatic mount to be off with only the
  debug serial console left

## Owner's request, verified

```
[    5.914175]     gts9_usb_gadget=acm
[    7.403412] gts9-init: USB gadget bound to a600000.usb (mode=acm)
```

The gadget is the CDC-ACM console alone: no `Mass Storage Function` line and no
medium, so nothing appears as a removable drive on the host, and the card is not
mounted. `gts9_card_mount=1` on the command line restores both.

## Hypothesis and result

A power-on reset is the only reset that can change the boot source on a part
whose option bytes select the software BOOT0, and this port had never given the
MCU one: it enabled a rail that was already high from the regulator's pinctrl
state, then worked the bootloader and NRST. `pogo_power_cycle()` drives SWCLK
(BOOT0) low and holds NRST asserted while the rail goes down and up.

```
[    4.468568] MCU powered up again with BOOT0 low
[    4.534816] waiting up to 60000 ms for the MCU application
[   68.509632] no answer from the MCU application after 60000 ms (-6)
[   68.581435] MCU application did not answer; entering its bootloader
[   68.717238] MCU bootloader took the 0xFF sync
[   68.735273] MCU bootloader version 0x12
[   68.748693] MCU IC version 00340034
[   68.797497] MCU option bytes 0xfefffeaa: RDP 0xaa, bit 24 clear
[   68.982460] after the disconnected reset: application -6, bootloader -6, connect 1
```

The power cycle happened, the application still did not answer in 60 s, and the
bootloader came back exactly as before — so the cycle is safe and repeatable, but
it is not the missing step either.

## Where the port stands on the keyboard

Every mechanism tried, each measured and recorded:

| test | candidate | result |
| --- | --- | --- |
| 046 | complete the Get Version ACK chain | version 0x12, GO refused |
| 047 | vendor reset after the unknown-command probe | both GO ACKs accepted, app silent |
| 048 | five-second poll with no reset after GO | silent (hypothesis disproved) |
| 049 | GO at the bank address read from the header | header is not in flash; GO leaves the part answering nowhere |
| 050 | the vendor's own sequence (validation, IC version, disconnect) | IC version `00340034` matches stock's `mcu_fw(ic):34`; app silent |
| 051 | where the header is, which interface answers | no header in flash; neither interface after the reset |
| 052 | patient 60 s read-only wait, no reset at all | silent (hypothesis disproved) |
| 053 | read the option bytes | `0xfefffeaa`, RDP level 0, bit 24 already clear |
| 054 | a real power-on with BOOT0 low | silent |

The bootloader side is replicated and byte-verified against stock's own known
value, the pin/rail/address configuration is identical to the device's stock
overlay, and the stock stack demonstrably gets the application to answer on the
same hardware. What has *not* been reproduced is the controller side of the bus:
stock's overlay for this bus carries `samsung,reset-before-trans` and
`samsung,stop-after-trans`, which the mainline `i2c-qcom-geni` driver does not
implement. That is the next thing to try, together with the exact semantics in
the downstream driver rather than the approximation tried earlier.
