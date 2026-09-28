# Test249: production DCC-path repair deployed and accepted

The default production kernel with `CONFIG_HVC_DCC=n` is now installed, with
its matched 181-file module directory. Only `boot` and `vendor_boot` were
flashed; the final live readback verifies their candidate SHA-256 values and
the unchanged `init_boot`, `dtbo` and `vbmeta` values. There is no HVC DCC
write path, `/dev/hvc0` or `serial-getty@hvc0` service at runtime. The exact
embedded config and kernel notes match the saved build; six runtime/link
address anchors agree. Pseudo-NMI, CSD tracing, last-activity and diagnostic
ramoops ECC/BBM changes are absent. No temporary SSH/USB configuration change
was made.

The first production boot from TWRP was
`17714931-a67c-41ba-8183-6392979a679e`. The first observer initially marked
the result inconclusive at 7.74 s because it expected an explicit
`# CONFIG_HVC_DRIVER is not set` line; Kconfig omits that symbol when its only
selector, HVC_DCC, is disabled. The observer was corrected to verify the full
embedded config SHA-256 against the build, and it resumed **the same boot**.
The complete persistent kernel journal with source timestamps and a final
live check gave a clean 158.22 s window. This was not a second physical boot.
Windows ADB and NCM SSH port 22 were available.

One ordinary warm reboot produced
`38a30c1d-68b2-4e10-8bb4-42dce8bb0385`. It passed the independently
attributed 120.09 s window with 1,091 kernel journal rows, source timestamps,
exact config/notes/modules, no CPU stall/panic/suspect marker and no failed
systemd unit. A later final check at 485.28 s verified the same boot ID,
all five partition hashes, all 181 production module files, no stale on-device
module backup directories and no new kernel fault. These bounded startup
checks validate the repaired DCC path on two boot paths; they do not prove
that every historical CPU stall had the same cause or that no future stall is
possible.

The warm boot's first Windows NCM TCP check failed while ADB, the device-side
gadget/`usb0` and `sshd` remained active. A follow-up check in the **same boot**
passed without a change or reboot and returned an OpenSSH banner. The prior
diagnostic248 startup's separate Code43 descriptor failure and this NCM
transient are detailed in `usb-incident/RESULTS.md`; neither is claimed fixed.
The deferred `aux_bridge` message also remains a separate missing PS5169
provider/DisplayPort bring-up issue and is not a CPU-lockup signal.

The original230 image pair and module archive and the passing248 rollback
image/module pair were hashed again before removing two temporary module
backup directories from the tablet. The production module directory remains
complete. The final accepted device state is the production DCC-disabled
kernel; external paired rollback artifacts remain available in the WSL build
outputs and under `D:\android` for Windows ADB recovery.
