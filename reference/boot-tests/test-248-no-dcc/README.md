# Test248 repair candidate: remove the observed DCC transmit stall path

Historical preparation record. See [RESULTS.md](RESULTS.md) for the completed
initial target and the explicit temporary device state pending production.

Test247 directly captured CPU4 agetty looping on DCC TX-busy under hvc_write's
IRQ-saving lock. This repair explicitly disables inherited CONFIG_HVC_DCC and
makes the build reject its reintroduction. No stock evidence is edited.

First candidate keeps247's PNMI/CSD/LA/ECC/BBM diagnostics and cmdline so the
repair's kernel delta can be accounted for. Expect HVC_DCC to turn off, with
only explained dependent config changes. Save exact symbols/module versions,
check DCC driver/symbol absence and kernel package, stage matched modules and
verify the original rollback pair. No getty mask, affinity workaround or
DCC writes are part of validation. USB ADB/NCM SSH and panel console remain.

Register one TWRP-entry120 s startup target initially. Check config capability,
no DCC hvc0 node or serial-getty@hvc0 activation, full kernel/source-time logs,
per-boot notes/anchors and unchanged arming. Stop on any failure/suspect or
unattributed reboot; up to20 s extra capture. Do not label an absent DCC path as
proof that every historical stall had the same cause. A later bounded reboot
regression and production deployment require concrete result review; they are
not implied by this initial trial. No physical248 target has run at registration.

Rollback remains BOTH modules and boot/vendor_boot, with all-five partition
hashes and181 original module hashes verified. Original recovery supports USB
ADB and NCM SSH; preserve its configuration. Kernel build/package scripts never
flash. Keep the kernel pin and power/clock settings unchanged.
