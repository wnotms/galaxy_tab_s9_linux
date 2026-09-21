# Test 019 — SM-X910 PHY patches, cut short by hand (2026-09-21T13:53:28Z)

Carried two changes at once: `CONFIG_QCOM_PDC=y` (the SPMI arbiter's interrupt
controller) and the two SM-X910 port patches in `kernel/patches/` — the UFS QMP
TX pull-down fix and Samsung's eUSB2 PHY init sequence.

Artifacts: `boot 307207ce…` (both PHY patches), `init_boot b13296a1…` (delay
telemetry now carries `rtc_dev`/`rtc_written`), `vendor_boot 11e92536…`
(`gts9_proof_code=600 gts9_rtc_report=1`); all flashed and read back.

## Result: superseded, not a result

The owner rebooted the tablet by hand into TWRP about six minutes in, before the
armed 600 s power-off could fire (`observation.txt`).  No report, no RTC state
word, nothing from the ring — and, crucially, nothing that separates the two
changes the run carried.

So this boot image was replaced by test 020's PDC-only build and the two PHY
patches moved to `kernel/patches/pending/`.  The changes were made into a normal
commit before the boot, so nothing was lost by holding them: they go back in one
at a time, once the PDC fix has been measured on its own.
