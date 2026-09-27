# Test248: the diagnosed DCC path is absent and startup passes

The sole candidate target passed120.08 s. This validates the first hardware
repair checkpoint, not final production deployment or every historical fault.
No deliberate workload or fault was injected. The next step is the production
build with this DCC fix and without temporary PNMI/CSD/LA/ECC/BBM diagnostics.

Source a4210ed. Initial normal-reboot ADB command exited255 when transport
closed; independent polling then found the expected TWRP serial. No command
was blindly restarted and no target retry occurred. The runner resumed only
at fresh TWRP capture/partition checks. See runner/resume-after-reboot.json.
All181 matching candidate modules and boot/vendor_boot were installed, hashed
and verified before reboot; all other partition hashes remained original.

Target1707f656-b262-45be-8473-982ae5ffefa8, capture4ff0340a-587e-4c23-9f4c-db78a329ee37.
Notes match the exact saved image and six anchors agree+0x80000. First ADB6.68 s.
Embedded config confirms HVC_DCC is disabled, both /dev/hvc0 and its sysfs tty
are absent, and serial-getty@hvc0 is inactive. CSD timeout5000/panic0, detailed
RCU reports, pseudo-NMI, LA1/ECC64 and watchdog1/1/1/10 remain verified.
All181 module hashes match; bluetooth/mac80211/ath11k loaded build-id notes
also match (not full memory-byte attestation). Final1101 kernel JSON records
retain source times and target identity. No failure/suspect signature or failed
systemd unit was observed; retained history has no intermediate Debian target.
At127.71 s all four SSH/USB services were active, ADB responsive and Windows
NCM SSH protocol banner available. No authenticated SSH shell was tested.

## Explicit current state and transition decision

The tablet currently runs this **temporary diagnostic repair candidate**.
After reviewing its success, keep it running while preparing the production
repair, rather than reboot into the already-observed DCC fault path again.
This is not a completed production rollout. The single248 target budget is
closed; it permits no repeated diagnostic boots. The next production transition
needs its own recorded package/module/detector/transport checks and bounded
reboot regression.

Original module files are still saved as
/usr/lib/modules/.gts9-test248-original on the SD root. Original module tar
SHA256d2f1a6052da02f7c65b7bbc44b9f5dda92b619af06345d8efaf35deb2e7009bb
has verified local and Windows copies. Original boot/vendor_boot backups remain
at /mnt/d/android/gts9-test230/backup-{boot,vendor_boot}.img with recorded
hashes. Restore both modules and images if recovery is required; no partition-
only rollback. Cleanup of owned staging/saved directories remains outstanding
until the production transition is verified. No USB/SSH configuration changed.
