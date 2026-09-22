# Test 041 — PHY-only quiesce does not fix first enable

Source 10f5c83. Boot only flashed, full readback hash matched. Existing stock
and pretest backups verified. Init_boot/vendor_boot/dtbo/vbmeta unchanged.
Recovery plan: restore pretest boot from .work/backups/test-041-* in TWRP;
stock chain also remains backed up off-device. Recovery partition untouched.

First ID 00 00 00 at 5.391 s; fb blank recovery gets 80 00 04 at 7.953 s.
No ctl start failure in captured mainline report. This rejects PHY lane
quiesce alone as a fix; retire candidate before the next test. No owner
visual verdict was supplied for this test. USB console remained accessible.
The report was read from the read-only USB microSD gadget and SHA256 verified.
Raw last_kmsg is collected but is not used as mainline evidence. Pstore
availability is recorded separately. Final state: TWRP via BCB, candidate
boot remains on the boot partition pending the next controlled test.

TWRP baseline also positively enumerates the attached EF-DX710 Slim keyboard,
model 0x02, MCU firmware 1.4. See pretest input list and recovery dmesg.
