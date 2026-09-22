# test-086 — the flash is not a partial image: the lead is disproved before any write

- date: 2026-09-22T11:40:00Z, no device touched, no image flashed
- source: the firmware file this project has been comparing against, read on the
  host (`.work/firmware/keyboard_stm/stm32_gts9family.bin`, sha256 in
  `firmware-file-layout.txt`)
- authorization: none needed - this is a host-side file read

## What was proposed and why it is withdrawn

Test 085's README proposed forcing the vendor driver's firmware update, on the
theory that the MCU's flash was a partially written image: the application's last
sector checksums to the file's value (`0x7E2341C8`), while reading 0x08000000
gives a valid vector table and 0x080000BE/0xC0 gave zeros where the vendor's
`magic_offset` (0xBC/0xC0) says Samsung's `"STM32"` header should be.

**The file says otherwise, and it says so on the host:**

```
file[0:8]    = SP 0x200056c0, reset 0x0800c4a5   <- the same vector table test 049
                                                    read out of the MCU's flash
file[0xb0:0xe0] = ... 0000 0000 0000 0000 ...     <- zeros at 0xbc/0xc0, exactly
                                                    what the flash read back
"STM32" occurs at 0x865 and 0x934 only             <- inside the image's data,
                                                    not at the magic offset
```

So the flash and the file agree at the start as well as at the end: **there is no
partial image, and nothing needs rewriting.** The vendor's `magic_offset` belongs
to a different firmware container format (the FOTA or another model's bin), not
to this file - an assumption this project carried since test 049 and has now
tested.

**The proposal to force a firmware update is withdrawn on this evidence**, and no
MCU flash write was performed or is needed. The MCU's flash is stock's firmware,
byte for byte, which also means the application this investigation has been
chasing is exactly the one that works under stock.

## Where that leaves the investigation

Every host-side variable is measured and matches stock (tests 070-085), the
firmware and flash are identical to stock's, the MCU runs and announces itself,
and its I2C slave still serves no address while the same peripheral serves the
bootloader on the same controller. The remaining candidates are the controller
driver comparison of the plan's stage four - now the only layer never compared -
and whatever the application checks for itself inside the cover.
