# Test246: matched pseudo-NMI kernel/modules, one clean startup window

**CPU repair remains OPEN.** The sole registered target completed120.08 seconds
without a detected CPU/RCU/CSD/workqueue failure or the runner's suspect timeout
signatures. No natural failed-target stack was captured. This is neither a
failure-rate estimate nor evidence that pseudo-NMI fixed the fault. The trial
budget is closed; do not repeat identical healthy boots.

## Deployment and target attribution

Source commit: `9a96339`; build/package provenance is in BUILD_RESULTS.md and
validation/. Applied0022+0024+0026 with PSEUDO_NMI; no calibration helper0027,
synthetic workload, intentional fault or power-setting change.

TWRP matched the expected tablet. The first read-only module discovery failed
because standalone blkid is unavailable; no module mutation occurred. Preserved
module-install/ and module-discovery/ establish the failure and recovery.
Using the available `toybox blkid` identified ext4 UUID
851819a7-0d96-4217-b64a-aeeee5d8be61 on /dev/block/mmcblk1p1. The mounted root's
machine ID and actual mount source were checked before writes.

module-install-v2/ verified the181 original files, staged181 candidate files,
then installed and verified all181 again. Only boot/vendor_boot were flashed;
read-back and all-five partition hashes passed. Both verification records were
required before unmount and `twrp reboot system`.

- Target: `2de14bb7-4cd7-4b76-a78c-ad3766d187fa`.
- Capture ID: `882ba36f-60e6-4c52-a1a0-0e2167ffb530`.
- Exact saved kernel notes match; six independent anchors agree on +0x40000.
- First ADB response6.75 s; profile/module checks passed by10.26 s.
- Runtime GIC priority masking and pseudo-NMI enabled; LA1, ECC64,
  watchdog/soft-watchdog/softlockup-panic/panic1/1/1/10; printk5/4.
- All181 installed files match the candidate manifest. Loaded build-id notes
  for bluetooth/mac80211/ath11k match this build (not full memory-code attestation).
- At120.08 s, all1101 final kernel JSON records have source timestamps and the
  target boot ID. No failed systemd units at the final health check.
- Retained boot history has this target immediately after the source production
  boot. This cannot prove absence of a boot that left no persistent journal.
- Additional transport check at158.09 s found all four SSH/USB services active,
  responsive ADB and a Windows USB-NCM SSH banner. It does not extend the defined
 120 s stability verdict or establish an authenticated SSH shell.

Raw follower, immutable-by-ID journal and verdict are in target-run/;
identity/module evidence is in target/ and transport in target-transport/.
There was no fault snapshot to decode. TWRP dmesg/last_kmsg/pstore listings in
baseline/ and twrp-restore/ retain their recovery context; they are not a newly
attributed failed-target stack. No new crash-pstore pull was needed for this
clean target.

## Restoration and final device state

Normal recovery used the checked BCB helper and the ordinary reboot.target
transaction. module-restore/ verified and restored all181 original files.
The owned .gts9-test246-tested candidate directory was independently checked
against all181 candidate hashes before its removal (module-cleanup/).
Original boot/vendor_boot were restored and read back; all five original
partition hashes match. init_boot/dtbo/vbmeta/recovery were not flashed.
Paired module/image gates passed before the final reboot; the SD root was
synced and unmounted first. The executed sequence is recorded in runner/.

Final production boot: `f231faf9-fd13-468d-b6ec-58b8ade46d8e`.
First connection6.68 s, observation120.07 s; all1094 final JSON records retain
source timestamps/identity and no failure/suspect signature was detected.
All181 module files match the original manifest after boot. Runtime watchdog,
soft watchdog, softlockup panic, panic delay and ECC are back to original zeros;
calibration helper absent. No failed units at this check. The previous UPower
217/USER failure remains a separate unresolved finding; its absence here is
not a fix or a reason to erase prior evidence.

At163.08 s, the same production boot had four active SSH/USB services, USB NCM
169.254.42.1 and working ADB. Windows received the SSH protocol banner; no
credentials, SSH configuration or USB gadget configuration were changed and
no authenticated SSH shell was tested.

Final offline audit checks original/candidate module manifests, source-time
journals, identities, service status, SSH results and original partition hashes.
Runner Python syntax and repository shell syntax pass. This archive/runner
change does not warrant the unrelated full host regression or another build.

## Remaining question

Test245 still provides the positive natural failure: CPU1 waiting for CPU2
while ordinary backtrace failed to supply CPU2's PC before panic. Test246 adds
matched-module deployment and a clean diagnostic startup, not that missing PC.
Next investigate evidence collection at the first stuck synchronization request
from the exact pinned code, offline first. Keep a future early-capture design
separate from a repair claim; no new boot is registered by this result.
