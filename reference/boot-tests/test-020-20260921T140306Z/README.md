# Test 020 — CONFIG_QCOM_PDC: storage and USB come up (2026-09-21T14:03:06Z)

One change, `CONFIG_QCOM_PDC=y`, and it unlocked the board.

## Result: both storage controllers and the USB device controller work

The report is on the microSD card, checksum-verified end to end — the first
time any mainline boot on this tablet has produced a durable log:

- **SPMI arbiter binds** (`PMIC arbiter version v7`), which is what the PDC was
  blocking.  Everything behind it appears with it: the PMIC GPIOs, the PMK8550
  RTC (`registered as rtc0`) and the ADC.
- **microSD enumerates**: `mmc1 -> 8804000.mmc`, card present (`mmc1:aaaa`).
  The card-detect line is `pm8550_gpios 12`, an SPMI device - so the PDC fix is
  what the card was waiting for, not a missing driver or a bad DTS.
- **UFS enumerates**: `host0 -> 1d84000.ufshc`, SCSI devices `0:0:0:0` through
  `0:0:0:49488`, block devices `sda`..`sdf` with every partition present.  The
  SM-X910 TX pull-down patch in `kernel/patches/pending/` is therefore *not*
  needed on this board; UFS was waiting on the PMIC side as well.
- **The USB gadget enumerates on the host**: `VID_0525&PID_A4A7`, serial
  `GTS9WIFI-0001` (`usb-monitor.log`), so DWC3 + eUSB2 PHY + PDC are working.

`deferred devices` mentions nothing storage-related, and the report itself -
145 KB with dmesg, the GPT dump of every LUN, the regulator and clock summaries
- arrived on the card intact.

## Still open

- The gadget exposes only its control interface (`MI_00`); the CDC-ACM data
  interface never appears, so Windows creates COM17 and then cannot open it.
- The RTC state word is still not written (the registers hold the value that was
  running before the boot), and the report's dmesg is collected before the RTC
  step, so it does not say why.  Test 021 moves the RTC step before the report
  and logs every command's outcome.
