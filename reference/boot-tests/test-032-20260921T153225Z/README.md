# Test 032 — one command at the console reboots into TWRP (2026-09-21T15:32:19Z)

The fix for the bug test 031's console found: `publish_misc_device` now runs
after `setup_usb_gadget`, when UFS is enumerated and the GPT can be read, and it
logs the device it published.

Artifacts: `init_boot d43750a0…` (only change), `boot ba948a93…` and
`vendor_boot 5aae758c…` unchanged.

## Result: the owner's feature works

```
cat /tmp/gts9-misc-dev      -> /dev/sda10
cat /proc/uptime            -> 44.80
SENT  gts9-to-recovery
RECV  gts9-to-recovery: BCB written to /dev/sda10; rebooting into recovery
15:34:19  adb=recovery
```

26 seconds from the command to TWRP, typed over the USB serial console.

## How to use it

- The gadget exposes CDC-ACM and the microSD card together.  Windows shows a COM
  port (COM17 here) and the card as a read-only volume (`G:`), which carries
  `gts9-bringup-report.txt` (158465 bytes this boot, sidecar verified).
- Open the COM port at 115200 8N1 and you get a shell: `uname`, `df`, `dmesg`,
  `ls /dev` all work, and the card is a live view of the tablet's log.
- Type `gts9-to-recovery` to write the Android BCB into `misc` and reset into
  TWRP.  The device path comes from `/init`, which validates it against the GPT
  and cross-checks the kernel's own geometry, so the helper cannot write
  anywhere else.
- If nobody intervenes, the 1800 s safety net in the command line does the same
  thing through the BCB, so a tablet can never be left sitting at the logo.
