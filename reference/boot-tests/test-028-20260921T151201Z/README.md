# Test 028 — the boot hands itself back to TWRP (2026-09-21T15:12:01Z)

Two owner requests in one change: drop the proof delay, and reboot into TWRP
automatically once the kernel boot is complete, with the log collected on the
microSD card.

`/init` now finishes its work (report collected, persisted, outcome logged),
waits **ten seconds**, writes the Android bootloader control block
(`boot-recovery`) into the first bytes of `misc`, and resets.  The timed proof
stays armed with a 90 s base as the safety net, so a boot that hangs still ends
in a reset rather than a tablet sitting at the logo.

Artifacts: `boot ba948a93…` (unchanged), `init_boot 2ede31a0…`,
`vendor_boot 9b6ad592…` (`gts9_proof_code=90 gts9_proof_action=recovery-bcb`).

## Result: the cycle is closed

`adb reboot` at 15:12:18, and at **15:12:51** adb reports the tablet in recovery
again — 33 seconds, unattended.  Mainline booted, wrote a fresh 155 KB report to
the microSD card (sha256 `47524c7c…`, verified against the sidecar the initramfs
writes next to it), and reset itself into TWRP through the BCB.

The report itself is the first complete one since test 020 (`observation.txt`
lists what it contains), and it settles two open questions:

- both storage controllers are up: `mmc=yes scsi=yes`, with `mmc1` and
  `sda`..`sdf` enumerated;
- the PTN3222 redriver **is** programmed: `10 override cells` read from the board
  DT and `applied 5 register overrides`.  Test 022's contrary reading came from a
  stale report file, not from the driver.

## Why not `reboot recovery`

That path goes through the PMIC SDAM reboot-mode cell, and an SPMI *write* blocks
this board's kernel uninterruptibly (tests 024/025, and the same from TWRP with
EACCES before any write).  The BCB is a UFS write, and UFS works.  It is one shot:
if `misc` already asks for recovery and the bootloader ignored it, `/init` powers
off instead of looping.

## Still open

The gadget's control interface enumerates and Windows creates COM17, but the
CDC-ACM data path still does not carry bytes even with the redriver programmed -
so the USB console is a convenience that is not yet available, and the card +
automatic recovery is the working channel.
