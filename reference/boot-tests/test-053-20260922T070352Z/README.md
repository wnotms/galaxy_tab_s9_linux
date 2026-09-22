# test-053 — card left alone, and the MCU's option bytes are already clear

- started: 2026-09-22T07:03:52Z
- source commit: `dab25d7` (option byte read) + `ef271a8` (card mount off)
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img 33afd56d…` and `init_boot.img 12b77d17…` (the initramfs
  changed) from `out/boot-bundle-test053`; `vendor_boot.img 828dadec…`,
  `dtbo.img c17418be…` unchanged
- authorization: owner asked to continue the repair, to reduce the wait between
  system switches, and for the microSD card's automatic mount to be off for now
  with only the debug serial console left ("暂时取消对tf卡的自动挂载，只保留调试串口")

## Results

1. **The card is left alone.** `GTS9_CARD_MOUNT` defaults to 0, and
   `/proc/mounts` shows no `mmc` or `/mnt` entry at all: no mount is attempted
   and no card is touched. The report stays in `/tmp` and is read over the
   console (`cat /tmp/bringup-report.txt`), which is where the console banner now
   points. One residue showed up in the log — `Mass Storage Function, version:
   2009/09/11` — because the bundled command line still asked for
   `gts9_usb_gadget=both`; the next test sets it to `acm`, so the gadget is the
   console only.

2. **The MCU's option bytes are already what the vendor's write would make
   them:**

```
[   68.347487] MCU IC version 00340034
[   68.394789] MCU option bytes 0xfefffeaa: RDP 0xaa, bit 24 clear
```

   `0xAA` in the low byte is read-out protection level 0, and bit 24 — the bit
   Samsung's `stm32_target_option_update()` clears on every boot — is already
   clear. The vendor's write would therefore change nothing, so that theory is
   closed without writing anything to the MCU, and the unprotect path
   (`0x92`, which erases the part) is not needed either.

3. The application still did not answer: the patient poll ran its full 60 s
   again, and the bootloader visit answered exactly as before (sync, version
   `0x12`, IC version `00340034`), with `application -6, bootloader -6` after the
   disconnect.

The remaining difference from the stock stack was then the MCU's power-on: the
port enabled a rail that was already high from its pinctrl state and then worked
resets, while a power-on reset is the only reset that can change the boot source
on a part whose option bytes select the software BOOT0. Test 054 gives the MCU a
real power cycle with BOOT0 low.
