# Test 039 — no-DSC experiment, inconclusive

This directory already existed when offline work resumed on 2026-09-22.
No new physical test was performed. Original evidence is preserved unchanged.

The flash transcript records boot SHA-256
`69ed370a648457041e812911d8a52aba7d1b5e8ab9d72c239adfd35c98139983`
and unchanged init_boot/vendor_boot hashes. `source.txt` names commit 1093fec;
that commit does not contain the experimental panel changes. The working-tree
diff recovered at handoff is saved as `source-working-tree.patch`; it is not
independent proof of the exact source used for the flashed image.

The report was generated at 6.34 seconds. DRM registered but reported
“Cannot find any crtc or sizes”; the framebuffer section is empty. The later
console-nodsc logs contain command echoes without diagnostic output, so they
cannot establish successful frame transfer, panel decoding, or recovery.
No owner screen observation, recovery dmesg, last_kmsg or pstore capture is
present here. The current physical device state is unknown. `to-twrp.log`
records the recovery request before this test's flash, not its final state.

Correction to the original hypothesis in source.txt: MSM derives the
uncompressed clock from the full DRM mode, including blanking. The 60 Hz
mode is 3403 x 2496 x 60 = 509633 kHz after integer truncation,
or 3.057798 Gbit/s per lane at RGB888 / four lanes. The 120 Hz mode is
561443 kHz (3.368658 Gbit/s per lane). Selecting 60 Hz does not establish
that an uncompressed mode is within the PHY/clock limits. This run does not
prove DSC is the display fault.
