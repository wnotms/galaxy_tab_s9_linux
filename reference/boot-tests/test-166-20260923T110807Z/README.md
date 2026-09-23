# Test 166 — power-key screen off and wake

**Result: PASS for power-key deep suspend and resume.** The owner reported
that a short power-key press turned the screen off and a second short press
restored the screen and keyboard. The same boot's journal confirms that the
press entered deep suspend and returned from it. Caps Lock was not separately
retested during this particular wake cycle.

The read-only COM17 audit reported Linux `7.2.0-rc3-gts9wifi-dirty`, boot ID
`d67a8a42-6314-4671-98b4-d12d2f68a3cb`, and a suspend event at uptime 2646
seconds. The kernel logged `PM: suspend entry (deep)` followed by
`PM: suspend exit`; systemd reported that suspend finished. The diagnostic
initramfs changes in the worktree had not been built or flashed at the time of
this test. No partition was written.

This does not show whether the earlier black-screen event after a separately
requested suspend has been fixed. It also does not establish that
`systemctl poweroff` removes PMIC power or say anything about battery-only
cold boot. The exact wall time of the physical key presses was not recorded;
the directory timestamp is when this report was archived.

## Evidence inventory

- `source.txt`: owner-reported result and limits of the observation.
- `journal-evidence.txt`: relevant boot-journal lines from the read-only COM17
  audit, without the serial login transcript.
- `SHA256SUMS`: hashes of the evidence files, excluding itself.
- No raw button-event or video capture was available. The audit did not
  interrupt or reboot the device.
