# Test 174 — Type-C reattachment during a stalled battery-start attempt

**Status:** user-observed; exact early-boot stage was not captured.

The user reported starting the tablet with Type-C disconnected. The screen
stopped at a single slowly blinking cursor. After Type-C was reconnected,
the screen advanced from the cursor to the Debian login page.

At the time of this observation, test-173 had not yet been flashed. The
subsequent TWRP pre-write check confirmed that the installed `init_boot` still
matched the test-172 image. Test-172's console trace option was parsed before
`/proc` was mounted, so its opt-in `GTS9_BOOT_STAGE` console lines were not
enabled. The boot-stage file from this particular attempt was not collected
before the following reboot.

This establishes a reported temporal association between Type-C reconnection
and visible boot progress. It does not establish which rail, controller,
firmware state, or boot stage caused the change. No regulator, PMIC, USB PHY,
or SD configuration was changed as part of this test.
