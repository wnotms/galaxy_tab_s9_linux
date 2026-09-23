# Test 168 — Debian poweroff with Type-C attached

**Result: FAIL for a stable poweroff; the poweroff request was followed by a
new Linux boot.** This does not yet distinguish a real power cut followed by
VBUS-triggered startup from a failed/returned poweroff handler or a reset.

The owner authorized one live `sudo -n systemctl poweroff` test over COM17. The
Type-C cable remained attached throughout. The command was sent at
2026-09-23 11:32:18 UTC. COM17 produced no new prompt during the 60-second
observation window, which ended at 11:33:18 UTC. The owner reported that the
tablet powered off and then started again automatically. A subsequent COM17
login succeeded and showed a different kernel boot ID, confirming that a new
Linux boot occurred; it does not prove whether the PMIC actually removed power
before startup.

## Evidence

- The pre-shutdown kernel boot ID was
  `d67a8a42-6314-4671-98b4-d12d2f68a3cb`.
- `/var/log/gts9-last-poweroff-stage` was written with
  `stage=systemd-poweroff-service` and the same boot ID. The device's clock in
  that marker read `2026-04-13T20:50:58Z`; the host-side command capture time is
  the reliable time reference for this test.
- The previous boot journal records the poweroff-stage unit succeeding,
  `poweroff.target`, and `systemd-shutdown` syncing filesystems and sending
  SIGTERM. The captured journal ends there; it has no `Power down` or PSCI
  entry evidence.
- After the automatic startup, COM17 reported boot ID
  `fbdf54c1-3232-4127-b399-f4d4f98d0974`, with uptime 196 seconds during the
  first audit. The rootfs was Debian and the serial login worked.
- `/sys/fs/pstore` was empty and there was no ramoops node, so no persistent
  kernel shutdown trace was available. The Linux kernel console is `ttyMSM0`,
  not the COM17 USB ACM console, so silence on COM17 cannot prove the final
  kernel stage.
- Type-C was never disconnected in this test. It remains an uncontrolled
  possible source of automatic startup after a true power cut.

## Interpretation and next test

This proves systemd reached its poweroff service and a new kernel boot followed.
It does **not** prove that `kernel_power_off()` reached or returned from the
PSCI `SYSTEM_OFF` call. No firmware, PMIC, regulator, or Type-C behavior was
changed.

The discriminating repeat is to issue poweroff with Type-C attached, unplug the
cable as soon as the display goes dark, keep it disconnected, and observe
whether the tablet stays off. If it stays off, press the power key once with
Type-C still disconnected to test battery-only cold boot. Reconnect COM only
after the physical observation so the persisted stage marker and next boot can
be read. Do not infer success from a dark display alone.

The serial capture used a reusable host-side path that was overwritten during
the next poweroff attempt, so the raw transcript for this test is not retained.
The evidence above was recorded from the live serial output. No credentials are
recorded in this test report.
