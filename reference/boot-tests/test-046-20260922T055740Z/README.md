# Test 046 — completed ACK candidate boots; keyboard startup still fails

Owner request: `刷入测试`. Source: `ad4463f` on `test`.
Only boot was written and its full-partition read-back SHA-256 matched the
candidate. init_boot, vendor_boot and dtbo already matched. vbmeta remains stock.
Current and original stock backups were verified before flashing.

The owner reported `能看到 Linux 控制台文字`. USB COM17 and the read-only
microSD gadget came up; the live shell returned the expected mainline release.
The panel recovered ID `80 00 04` at 6.31 seconds. This is a booted candidate,
not a working keyboard.

Live dmesg (`console-startup.log`, repeated in `console-final.log`):

- 4.164 s: bootloader took the 0xFF probe.
- 5.185 s: version exchange failed with -110 (ETIMEDOUT). The message does not
  identify which of the four transfers failed, so this does not prove the
  trailing ACK alone timed out.
- 6.274 s: GO command refused; the driver does not log the transport errno here.
- 7.460 s: application after GO -110; reset fallback then returned -6 (ENXIO).
- 10.381 s: no answer after 40 resets; address scan found nothing.
- Bus recovery pinctrl failed because gpio72 is owned by 89c000.i2c. No recovery
  clock pulse should be inferred from this attempt.

The microSD report was copied through the USB storage gadget and its sidecar
SHA-256 verified. It is an early snapshot; use the later console dmesg for the
completed keyboard attempt. No real key event was observed and no successful
keyboard input is claimed. Host PnP output uses the original Windows encoding.

At 06:00:18 UTC the live shell accepted gts9-to-recovery and reported the BCB
write and reboot. The final recovery state and raw recovery captures are stored
separately; recovery dmesg and last_kmsg are not treated as mainline evidence.

Source follow-up: Samsung stm32_sysboot_connect() resets into system boot mode
again after its successful unknown-command 0xFF probe, without another SYNC.
Our helper instead left the probe in the command stream. The next isolated
candidate should match that second reset before Get Version/GO. Hardware
verification is needed; this source discrepancy alone is not a proven cause.

Final state: TWRP returned successfully; all four candidate boot-chain hashes
were verified again, and vbmeta remains identical to the stock backup.
Pstore was empty (see pstore-status.txt); raw last_kmsg was available and saved.
