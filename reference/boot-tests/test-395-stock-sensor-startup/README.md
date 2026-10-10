# Test395 — stock sensor startup inputs, read only

Test393 proved two sensor-domain UP snapshots but no SSC400. Test394 proved
the five native SoC fields match actual Samsung recovery sysfs bytes. Neither
proves SSC initialization or samples. The existing Fedora0.4 daemon already
uses the same sensors attach ioctl as Qualcomm mainline-compatible FastRPC.
An extra dynamic-loader call is currently unsupported; ELF exports alone are
not a startup protocol.

This registration gathers this exact X710 stock vendor init files, sensor HAL/
related APPS libraries and daemon binaries for offline comparison. One temporary
read-only loop/mount (noexec/nosuid/nodev; ext4 noload), validated super metadata.
Exact selected directories/patterns and128-file/16MiB-member/64MiB-total bounds
are frozen in the collector. Missing inputs remain missing; no foreign library,
firmware, registry reset or guessed RPC. Preserve every selected original byte,
mtime and SHA256, and directory inventory explaining selection/absence. Android
binaries are not run on Debian or the host. Proprietary binary archive stays
in ignored out; only manifest/analysis/raw commands are committed.

Control is Windows ADB at /mnt/d/android/platform-tools/adb.exe. No Wi-Fi, flash,
reboot, DSP/RPC startup, kernel/config/DTS/modules/rootfs service changes or
charging/input experiment. GNOME remains active. Reuse Test394 five partition/
181 module identity on the same boot; fresh config/notes/boot/ordinary safety/
rescue and complete kernel checks at the two boundaries. No rebuild/full suite.

Commit and push registration/qualification/preflight before one run. Export
has45s SIGINT deadline/15s cleanup grace,75s host bound. First failure stops;
timeout or failed cleanup remains UNKNOWN and never justifies another attempt.
The mount is unmounted before its own loop is detached. Successful archive is
emitted only after cleanup and final same-boot/ADSP-offline gate.

Success means original startup input evidence and unchanged same-boot desktop,
not SSC/accelerometer/rotation. Analyze imports, init arguments and required
APPS/DSP roles before proposing any changed startup sequence.
