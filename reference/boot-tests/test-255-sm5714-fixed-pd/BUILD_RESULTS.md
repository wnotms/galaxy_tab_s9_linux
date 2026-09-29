# Test255 offline build and validation

Final implementation: `814788a306cd6b942f7a28dcdcb5e5539da02691`. Starting test HEAD was
26d62393efbd002f185ba759a7cca8638667dee9, checked locally and against origin.
All actions in this task were host-only. Installed Test254 was not queried,
changed, flashed, rebooted or replaced. No GitHub Actions/CI was requested.

## Exact config and source scope

Linux pin remains a13c140cc289c0b7b3770bce5b3ad42ab35074aa (7.2-rc3).
[Resolved config](validation/candidate.config) and independently extracted
[embedded config](validation/embedded.config) are byte-identical. Their SHA256
is `cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f`. The [complete diff](validation/config.diff) from Test254 has
exactly one symbol addition:

```diff
+CONFIG_TYPEC_SM5714=y
```

No removed/change-to-existing symbol and no unexpected config delta. TYPEC,
TYPEC_TCPM, USB_ROLE_SWITCH and REGMAP_I2C were already y; new Kconfig depends
I2C && TYPEC_TCPM && BATTERY_SM5714 and selects the existing REGMAP_I2C.
[Gate](validation/config-gate.json) verifies all85 Test254 container requirements
plus both battery/ADC prerequisites; USER_NS/POSIX_MQUEUE still y, HVC_DCC still n.
SM5440_DIRECT/DP_ALTMODE/PS5169/SBU configuration remains absent or n.
Do not require a nonexistent HVC_DRIVER selector line.

[Compiled source check](validation/compiled-source-check.json) verifies that
actual staged TCPC/charger/companion/DTS bytes match the reviewed
[prebuild snapshot](validation/prebuild-source-hashes.json), and TCPM core/API,
DWC3 core/drd/gadget and role-switch class equal pinned upstream git objects.
[Protected sources](validation/protected-source-hashes.json) retain all96
baseline files in the reviewed rootfs/userspace/other-kernel/boot/container-gate
scope. [Eight helpers](validation/retained-stage1-helpers.json) for float,
thermal, gauge current/temp, faults and current encoding are byte-identical to
Test254. [Incremental charger diff](validation/test254-to-stage2-driver.diff)
records ownership/budget/charge/suspend/fault gates without changing those limits.

## DTS/DTB

[Raw full DTB diff](validation/dtb.diff) includes phandle renumbering.
[Reproducible semantic comparison](validation/dtb-audit.py) resolves those
references to node paths and compares every change with the fixed
[approved list](validation/approved-dtb-changes.json); [result](validation/dtb-semantic-diff.json)
has23 approved property/node changes, zero extra and zero missing changes. No CPU/GPU/OPP,
thermal/regulator/clock/Wi-Fi/Bluetooth or hub3/GPI property delta.

Existing hub9/0x33/400kHz/GPIO133-low wiring was already present. Enable only its
TCPC driver and GPIO133 pinctrl. Narrow dormant connector dual-role/3A/source/DP
policy to Sink/Device, fixed5V1800mA and9V1500mA, op-sink13.5W; remove source/
role-swap/altmode/SS-SBU provider graphs and OTG/discharge pinctrl ownership.
The inherited dormant SM5440 child is explicitly disabled and its TCPM link
removed; no controller/driver/register access is added. Existing undriven
PS5169/SBU nodes remain outside acceptance.

DWC3 remains peripheral and its USB2 graph is exactly retained. Compiled-DTB
review exposed inherited usb-role-switch from sm8550.dtsi: peripheral mode
never registers that provider (core.c/drd.c), so TCPM would defer forever.
Board /delete-property/ removes that stale declaration. Stock optional role
lookup returns NULL; no DWC3/gadget/adbd source or dynamic role control is added.
USB3 orientation, DP, powered dock and suspend/resume PD continuity are unaccepted.

## Standard kernel build

```sh
JOBS=8 USE_CCACHE=1 BUILD_MODULES=1 \
KERNEL_WORKTREE="$PWD/.work/build/linux-src-sm5714-stage2" \
KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-sm5714-stage2" \
KERNEL_OUT_DIR="$PWD/out/kernel-sm5714-stage2" \
./scripts/build-kernel.sh
```

The same standard ARM64 Image.gz+DTB+modules pipeline passed (exit0), clang21.1.8,
LLVM=1, ccache, JOBS8, release7.2.0-rc3-gts9wifi-dirty. The final rebuild took
62.71s with cache populated by the preceding full build; this is not a cold-build
benchmark. [Complete final build log](validation/build-final.log) is retained.
No new TCPC/charger compiler warning or error. Existing fragment merge messages
and BASE_SMALL/softlockup/hung-task default warnings are not new Stage2 deltas.

The [preceding full build](validation/build-superseded.log) is explicitly
[superseded](validation/superseded-build.json), because final pending-probe,
input/fault/shutdown safety fixes and the inherited-property correction needed
rebuild. Its source/hash record is retained; never use it as the final candidate.
The pre-existing .work/linux-mainline historical overlay was not cleaned/edited.
Separate source/output roots preserve the accepted/rollback builds.

| Local output under out/kernel-sm5714-stage2 | SHA256 |
| --- | --- |
| Image.gz | f1ce90a4e65a4ab1cf1179391bef2237963eb832cb1bb3be6fdbe5781e27e46c |
| sm8550-samsung-gts9wifi.dtb | c6148471113c5cb7589c64dee776e17b2fc20235cfeff4482616817a8b4e1c0b |
| config | cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f |
| kernel-notes.bin | fb3d249642e900d9bb591fb629c1865b370b50098d44970b986cc793f45c160c |
| modules-sm5714-stage2.tar.gz | 28e33cda7814686ee32b480c0b0cf4f02952cdc89d19ad7af37feb47e79edf1c |

[Kernel notes](validation/kernel-notes.txt) carry GNU build ID
7cea65dc135f1d169433b1ae08edde0846fb3cf0. The paired archive contains exactly
181 regular files/167 .ko, the identical Test254 file set with new matched hashes.
[All hashes](validation/module-hashes.json) and [archive/depmod check](validation/module-archive-check.json)
verify every payload and the exact release vermagic. depmod -n -e -E Module.symvers
exits0 with empty stderr. Host build symlinks are excluded.
[Retained outputs](validation/retained-artifacts-check.json) match saved Test254,
Test252 and Test249 identities. No rollback artifact was overwritten.

## Offline packaging

out/boot-bundle-sm5714-stage2 contains boot `26ef6bd143a9575b997b8cf73f24686d647f1ac742f0e7d92d44aa600ef7c063` and
vendor_boot `d80d03cdf0ac810d9ac741074a9b97327c48880a98a4459db219ed7813461a46`. [Bundle build log](validation/bundle-build.log),
[validator log](validation/bundle-validation.log) and [unpack checks](validation/bundle-check.json)
verify Image.gz+appended DTB and the same new DTB in vendor_boot. Header fields,
old cmdline, bootconfig and empty platform ramdisk are exact. init_boot and dtbo
match Test254. Generated vbmeta matches the old generated bundle, **not** the
installed accepted vbmeta; never deploy generated init_boot/dtbo/vbmeta.
Boot+vendor_boot+paired modules need separate future authorization/registration.
Images/archive/raw notes remain ignored local artifacts; committed text manifests
and SHA record identities, not a claim that binaries are stored on GitHub.

## Local tests

All existing1148 tests are retained,35 new Stage2 tests added. Real C policy,
companion and transport callbacks execute with mocked I2C/register I/O; these
are not electrical tests. Focused SM5714 set:46 passed,3.799s.

| Required command | Result |
| --- | --- |
| bash scripts/check-stall-offline.sh --changed --base HEAD~1 |1183 passed,83.539s unittest, zero skips |
| python3 scripts/run-host-tests.py changed --report out/host-tests/sm5714-stage2-changed.json |1183 passed,98.513s runner, executed true |
| python3 scripts/run-host-tests.py all --fail-on-skip --report out/host-tests/sm5714-stage2-all.json |1183 passed,82.895s runner, executed true |

[Changed](validation/host-tests/changed.json), [full](validation/host-tests/all.json),
[wrapper](validation/host-tests/offline-wrapper.log) and raw logs preserve scope.
Changed conservatively selected all because new suite/build/audit paths lack a
reviewed narrower dependency rule; no zero-selection regression claim.

An earlier changed run had1178 selected and one real PTY fixture partial-read
failure; its [original report](validation/host-tests/changed-attempt01.json) and
log remain. Separate pushed commit a718bd89 drains both markers within1s and
retains every existing assertion (20 rootfs checks and five repeat runs passed).
No test was deleted/skipped/weakened to pass Stage2.

WSL global no-argument sync was already blocked on unrelated Windows mounts.
As in Test254, the temporary host PATH wrapper performs real syncfs on repo
ext4 and /tmp tmpfs; explicit arguments use real sync. [Invocation logs](validation/host-tests/wrapper-syncfs.log)
record it. No production helper or device setting changed, no fake/no-op sync.
[Machine summary](validation/summary.json) distinguishes offline readiness from
physical acceptance. Future gates/rollback are in [registration](README.md).
