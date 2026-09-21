# Test 012 — bring-up report to microSD, with a conditional power-off (2026-09-21T13:05:00Z)

Hypothesis: the microSD path comes up in mainline, so `/init` writes the full
report (including `dmesg`) to the card, and the conditional proof
(`gts9_userspace_proof=90 gts9_proof_if=report`) powers the tablet off **only
if that write succeeded**.

Artifacts: `init_boot cc8a7700…`, `vendor_boot 09dd8667…` (flashed and
read back, `flash.log`), `boot 57a973a7…` unchanged, `vbmeta` untouched.
`BOOT BUNDLE VALIDATION PASSED`.

## Result

The owner reports the tablet **stayed on the logo and never powered off**.
By construction that means the report was not written, i.e. **no removable
storage accepted it**: microSD did not enumerate in the mainline kernel.

The mechanism did what it was designed to do - it converted "is there a
writable storage channel?" into one physical bit, with no logs required.
