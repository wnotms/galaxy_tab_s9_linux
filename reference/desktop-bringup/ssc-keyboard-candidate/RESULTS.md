# SSC + native Escape candidate — assembled offline, not deployed

The next physical sensor test now has an assembled Android boot image using
the already compiled EF-DX710 Escape driver kernel. It reuses the exact signed
early-ADSP vendor_boot image from Test365, unchanged DTB, init_boot, dtbo,
vbmeta and charging behavior. No second kernel build or repeated firmware
packing. Boot AVB verification and reopened payload/header checks passed;
the sole header delta versus the prior SSC boot is compressed kernel size.
Image and inputs are listed in QUALIFICATION.json; private firmware remains
in ignored out. The new boot is not yet a registered/deployed Test366.

The existing native touch/pen modules can be reused: all frozen source and
binary hashes match, vermagic is exact, and all 29 pen + 38 palm-touch imported
symbol CRCs match this current kernel provider and the qualified pen export.
New staged loaders retain the accepted logic and replace only PROFILE values,
including the new kernel notes SHA. Twelve actual-loader mock checks passed
with real candidate config/notes/module bytes; wrong config/notes, charging
flags, altered modules and unsafe temperature are rejected. Original Test331
loaders and prior sensor candidate files are unchanged. The full kernel build,
181-module archive and keyboard parser qualification are reused from
keyboard-escape-driver; they are not represented as new executed tests here.

The first offline assembly stopped because the report filter expected
`kernel size:` while the existing unpack tool emits `kernel_size:`. Its log
and partial-image hash are preserved in attempt-01. Only that report field
was corrected; the created partial boot was deleted before regeneration.
Attempt-02 passes the exact remaining-header comparison and all other gates.
No failed attempt is relabeled as a pass or a hardware failure.

A mapping transition helper is prepared at
userspace/gnome/keyboard/select-driver.py. On the exact new kernel it removes
only `gts9:swap_escape_grave`; after exact Test331 rollback it restores that
option. Other options and input sources remain intact. It saves original
settings before writing, verifies readback and refuses unknown kernel/machine
or changed boot. It targets ms's own dconf, supports a private short-lived
session bus before the first graphical login, and drops root's session/runtime
environment. It does not overwrite custom XKB files or keyboard firmware.
Affected host validation: 20 tests passed, zero skipped (9 transition tests,
6 accepted pen loader tests, 5 accepted palm loader tests). Private-bus/device
execution and actual keys remain physical acceptance work, not host proof.

Next: independently register the one-boot Test366 with namespace-correct
module/assets rollback, bounded upstream FastRPC trace + QRTR capture and the
mapping helper; push before any device mutation. Validate actual sensor
discovery/samples before GNOME rotation, then confirm Escape/Fn+Escape and
Ctrl+Alt+T with the user. A first fault stops the scope and restores accepted
Test331, interim mapping and ordinary GNOME startup. Test365's first failure
is retained; absence of oemconfig in the bounded vendor audit is not a proven
root cause. No new device writes, services, remoteproc start, flash, reboot,
PPS, pump or current increase. Sensors/full port remain incomplete.
