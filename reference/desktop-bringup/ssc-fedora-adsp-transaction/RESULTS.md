# Fedora X710 ADSP transaction and matched early firmware — offline qualification

ADB has recovered. A single read-only snapshot confirms the last accepted
Test399 return boot `1f8302ac-b357-4e48-8b26-d786bb0de2dc` is still running:
GNOME/adbd active, device usb0 UP/LOWER_UP, ADSP offline,100%,32.7°C,
VBAT4.443V. Raw output and parsed READ_ONLY_DEVICE.json are retained. This is
transport/status evidence, not a new full baseline admission or sensor result.
No recovery/reboot/firmware/partition/rootfs/service mutation was sent.

`userspace/sensors/adsp_firmware_transaction.py` is a separate recovery-only
transaction for the qualified complete52-file Fedora ADSP/ADSP-DTB pair.
It requires the actual root `5.15.94-Foldiby-+` executing kernel, the accepted
Debian machine ID, and a recovery proc view identifying the current process.
A mainline boot cannot pass using a supplied recovery text marker. The host
must also retain existing `ssc-recovery-admission.py` model/serial/same-boot
checks; the firmware helper does not replace host recovery admission.

The exact original and candidate asset archives are independently pinned.
Every installed original must match the baseline bytes/mode/root ownership;
capture its actual nanosecond mtime instead of guessing the archive timestamp.
All52 originals and their hashes/metadata are backed up and fsynced before
the first replacement. Durable phase/pending-file intent precedes atomic
replacement, followed by each write-boundary verification. A prior transaction
refuses installation replay. Partial backup never reaches a firmware write.
Both before/after file states are recognized after an interrupted replacement
or restoration. Unknown current contents or corrupt backups stop all restore
writes and retain evidence. Exact-original restoration is verified across52.

The terminal ledger and backups remain for host collection. Explicit recovery
cleanup is permitted only after verified restoration; unknown entries or changed
backups are retained. No recursive deletion. The registered host must archive
the terminal ledger before cleanup. Neither transaction nor cleanup activates
remoteproc/services, changes calibration, touches other firmware or partitions.

The existing assets installer is unchanged and still refuses different existing
firmware. A real filesystem integration test proves that rejection, then proves
the separate ordering: firmware transaction → unchanged asset install → owned
asset restore → original firmware restore. Candidate firmware is pre-existing
to the assets ledger and is restored only by the firmware transaction.

`userspace/sensors/fedora_adsp_boot.py` builds the matching early firmware from
exact399 vendor SHAaf6531b5… and pinned AOSP tools. Bounded newc parsing rejects
unsafe paths, duplicate/nonroot/nonregular entries and incomplete/trailing data.
The ramdisk must contain exactly52 firmware files, three current PD maps and
five directories. All52 firmware bytes come from the same qualified Fedora
profile;19 differ. The three maps, directory/file metadata (except changed file
sizes), DTB, bootconfig, cmdline, trace enrollment and all other header arguments
stay exact. Rootfs candidate firmware mtime follows its qualified asset profile;
early ramdisk metadata follows399. Their firmware bytes agree; no mixed signed
MDT/segment pair. Reopened CPIO/LZ4, unpacked components and AVB verification pass.

Generated private artifact:
`out/boot-bundle-ssc-fedora-adsp/vendor_boot.img`,100663296bytes,
SHA256 `21d289fd4e76ebcf2621267a6259c65449c4e9e262e62e43ad80bc61e3330082`.
Full BUILD.json and raw tool logs are archived here. AVB uses the existing
unsigned NONE format and verifies payload/hash/footer; this is **not** Qualcomm
PAS authentication or runtime/sensor compatibility validation. Firmware and
images remain outside Git. No new kernel or modules were built.

87 affected host tests PASS0skip in33.928s:26 transaction,15 boot/CPIO/package,
16 profile,30 unchanged early-ADSP control tests. Transaction tests use real
archives and filesystem bytes/modes/mtimes/rename/fsync, emulating only recovery
kernel/root ownership/chown permissions on the nonroot host. This is not a
physical TWRP permission/mount qualification. Coverage includes interrupted
backup/replacement/post-rename/restore, corrupt backups, unknown contents,
hardlinks/symlinks, wrong kernel/root/machine/proc/archive, edited ledger,
refused replay, exact metadata return, protected assets and bounded cleanup.
Initial successful test iterations are retained separately; final source-bound
qualification is HOST_TESTS.json/qualified-tests.txt. Syntax checks pass.
No routing change/full regression/kernel build/Actions. Unchanged17 stock MDT
tests remain qualified by the previous profile component, not a new executed run.

## Next independent physical scope (not registered or executed here)

Prepare Test400 with the same399 kernel/config/DT/181 modules, initialized
readdir daemon/library, sensor→root order, provider observer and one30s window.
The one input comparison is the complete Fedora firmware pair in both boot and
rootfs. Fresh full370 baseline/rescue/health admission and committed/pushed
registration must precede any mutation. Do not inherit old firmware's exact
callback totals as predictions for this changed firmware: validate actual raw
callbacks/replies against the unchanged asset manifest, retain actual counts,
and independently assess SSC400/samples/rotation. Never relax CPU/identity/
transport/battery/thermal or unknown-evidence stop conditions.

Run firmware operations inside the offline Debian chroot with a separately
owned temporary read-only recovery `/proc` bind (e.g. `/tmp/gts9-test400-fw/proc`).
Use a firmware scratch directory separate from the unchanged assets scratch
directory. Journal ownership before binding; unmount in every exit path before
unmounting Debian. A missing/failed bind stops, rather than bypassing the guard.
Stage/hash both complete archives and helpers at their transfer boundary.

Install firmware before isolated assets; then overlay and matched vendor image.
After one candidate boot, preserve first anomaly/full evidence and always return:
TWRP admission → owned overlay/assets restore → exact original52 firmware
restore → archive/verify terminal ledger → bounded owned backup cleanup →
original370 vendor/readback → attributed normal GNOME with the existing15s
return gate. No unchanged failed replay, live late ADSP start, guessed registry
or sleepstate write. Registration/runtime integration and physical proc binding
are still outstanding; this component is **NOT DEPLOYMENT READY**.

Retain current399 and exact370 rollback until their consumers change; no new
numbered test was executed, so retention remains390–399. The new host-only
comparison package has an explicit pending registration consumer. Temporary
uncompressed/compression output copies are represented by hashes, not duplicate
firmware payload logs. Windows staging was not created. Kernel/config/DT/modules,
USB/charging/input untouched; PPS/pump/DCC OFF,4.44V float/thermal fail-closed
unchanged. SSC/sensor samples/automatic rotation remain unfinished.
