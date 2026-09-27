# Test246 preparation complete: matching kernel, modules and rollback artifacts

Not flashed or booted yet. CPU repair remains OPEN. This preparation follows
the natural CPU2 failure in245; it does not turn a compile into a repair result.

The incremental ccache build completed in about208 seconds, including all
configured modules. Patches0022+0024+0026 are present; calibration helper0027
is absent. Exact vmlinux/System.map/Module.symvers are saved in out/test246.
Compared with245, the only config changes are PSEUDO_NMI=y and its two Kconfig
selected capability flags HAVE_PERF_EVENTS_NMI/HAVE_HARDLOCKUP_DETECTOR_PERF.
HARDLOCKUP_DETECTOR itself remains disabled. DTB/release are byte-identical.
Kernel image SHA-256 is
`f991c6a3f87925f4277ccb6687cf5f9ad76618de078becd23def99d1f79c6e4d`.
Old-stock seed conversion emits its existing BASE_SMALL/panic-type/console
override warnings; the build/config assertions pass. No compiler repair is
claimed for those seed warnings.

Boot bundle creation and the complete bundle validator pass for
out/boot-bundle-pnmi-bbm. Only boot/vendor_boot are intended for flashing; the
generated vbmeta remains excluded. Module depmod validation against this
kernel's exact Module.symvers exits0 with empty diagnostics.

## Concrete module result

All167 currently installed .ko files were compared from a verified device
backup. Three have changed allocated sections and new priority-mask alternative
sites: bluetooth0→62, mac802110→19, ath11k0→8. The other164 have equal allocated
section contents in this comparison (not a proof that all ELF metadata or
relocations are identical). All167 have equal named imported-symbol CRCs and
the same imported-symbol sets. Two __versions tables differ only in ordering.
Thus vermagic/import-version checks alone would miss these inline-code changes.

This is actual current-module binary evidence; the earlier two-file sample
did not prove such a difference. Do not claim the exact module state of a
historical boot without its own evidence, or infer that this caused test245
(which used the ordinary-IRQ kernel). Test241's built-in CPU0 calibration
remains valid within its measured scope.

## Verified backups and swap procedure

The original module directory was archived without changing its files. Every
one of181 regular files matches independently read device hashes before and
after backup; the build symlink is recorded. Local and Windows backup copies:
out/test246/original-modules.tar and
/mnt/d/android/gts9-test246/original-modules.tar, SHA-256
`d2f1a6052da02f7c65b7bbc44b9f5dda92b619af06345d8efaf35deb2e7009bb`.
A first exec-out stream attempt returned tar's terminal-refusal error rather
than an archive; it was rejected and preserved. The verified retry used a
temporary tar plus ADB pull, then removed that owned temporary device file.

The matching candidate tar contains181 files, each verified against the build
tree. The offline-tested module-swap.sh checks machine identity, hashes/file
count/build symlink, stages the full directory, and renames it atomically while
retaining the original directory. Restoration verifies the original backup
before moving it back and keeps the used candidate for inspection.
Offline checks confirm a corrupt candidate manifest stops before replacing
originals, a complete install matches all181 new hashes, and restore matches
all181 originals. Shell syntax passes for this helper and all41 repository
scripts. No unrelated full host suite was run.

## Remaining deployment gates

Before executing the one registered hardware target, the host runner must
freshly verify the live source and TWRP identities, mounted Debian filesystem
and machine ID, original partition/module hashes and staged archive hashes.
Do not trust only the helper's directory path: verify the actual mounted SD
partition. Install and verify matching modules in TWRP, flash/read back
boot/vendor_boot, and only then reboot with the complete verified pair.
If either installation fails, stay in TWRP and restore both originals before
booting. On rollback restore the module directory as well as the two images;
the older partition-only rollback is insufficient for this trial.

The device remains on original production boot bd20438b-cea6-4172-8e5f-de83a6b69a51
at the last read-only backup checks. No test246 hardware target or live module
replacement occurred. Preserve the known UPower failure as separate health
evidence and use the registered120 s window, not an added300 s wait.
