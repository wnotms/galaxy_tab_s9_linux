# AGENT.md — SM-X710 mainline port working rules

## Mission

Maintain a mainline-first Linux port for Samsung Galaxy Tab S9 Wi-Fi (`SM-X710`, Android codename `gts9wifi`) on Qualcomm SM8550 (`kalama`). Prefer upstream Linux interfaces and bindings. Samsung's downstream 5.15.153 sources/config/device tree are evidence about hardware, not the target architecture.

## Ground truth and pins

- Device: SM-X710 / gts9wifi, Wi-Fi model.
- SoC: SM8550 / Snapdragon 8 Gen 2; GPU Adreno 740.
- Samsung ABL selector values observed in the supplied live DTS:
  - `compatible = "qcom,kalama-mtp", "qcom,kalama", "qcom,mtp"`
  - `qcom,board-id = <0x10008 0x04>`
  - `qcom,msm-id = <0x218 0x20000 0x207 0x20000 0x207 0x10000 0x218 0x10000>`
- Stock config evidence: Linux 5.15.153, Android clang 14.0.7.
- Mainline build pin: Linux `v7.2-rc3`, commit `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
- Bootstrap board DTS reference: `troikoss/gts9wifi-fedora` commit `656d2ded8031657b60cde22e6fdfbc0b722a9dff`.
- Earlier X710 bring-up reference: `Azkali/sm8550-mainline` branch `gts9wifi-7.0`, inspected at `c48fedbd799a2b792a095840eeb96746afe2f327`. See `docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md` and `kernel/PROVENANCE.md`.

Do not silently change either pin. A kernel bump and a hardware-port change must be separate changes so regressions remain attributable.

## Stock evidence supplied by the owner

The owner supplied a live DTB, a decompiled live DTS and a full stock `.config`. Their SHA-256 values and extracted hardware facts are recorded in `reference/stock/MANIFEST.md`.

Important device-specific differences from the S9 Ultra/X910:

- SM-X710 panel: `GTS9_ANA38407_AMSA10FA01`.
- Touch: STM FTS1BA90A, not the X910 Goodix GT9916.
- Pen: Wacom W90xx / WEZ01 family on I2C.
- WLAN/BT: QCA6490/WCN6855-class, not X910 WCN7850/Kiwi v2.
- Power: SM5714 charger/fuel gauge/USB-PD plus SM5440 direct charger.
- Type-C redriver: Parade PS5169; eUSB2 repeater: NXP PTN3222.
- Audio: four CS35L45 speaker amplifiers are visible in the stock DTS.

Never copy the entire downstream DTS into `arch/arm64/boot/dts/qcom/` and call that a mainline port. Translate only evidenced hardware into upstream bindings and keep unsupported vendor-only properties out.

## Repository invariants

1. `scripts/fetch-mainline.sh` must verify the exact upstream commit.
2. The upstream checkout under `.work/linux-mainline` stays pristine.
3. Device changes are staged into a disposable worktree under `.work/build/`.
4. Kernel build output goes to `.work/build/linux-out` and `out/kernel-gts9wifi`; never commit it.
5. Use `USE_CCACHE=1 ARCH=arm64 LLVM=1`; ccache is required for builds. Do not introduce a GCC-only build path unless there is a demonstrated need.
6. Keep critical early-boot/storage/console providers built in when the port depends on them before the root filesystem is available.
7. The owner-extracted stock config is immutable evidence: reconstruct it with `scripts/materialize-stock-config.sh`, verify its recorded SHA-256, then use it as the Kconfig seed. A symbol requested by the mainline fragment but dropped by `olddefconfig` must be treated as a build/config issue, not ignored.
8. Kernel image, DTB, config and release string must be hashed in every build.
9. No build script may flash or repartition a physical device.
10. Do not claim hardware works because a driver compiles or probes. Record `compiled`, `booted`, `enumerated`, and `physically verified` as different states.

## Remote workflow (owner instruction, 2026-09-21)

- `main` is left alone unless the owner explicitly asks for it. Work happens on a
  branch (currently `test`) and is pushed there.
- One purpose per commit; do not batch unrelated work into one commit.
- **Push to `origin` after every operation.** Verified work must not exist only on
  the local disk: commit it and push the branch, so the remote always matches what
  was actually built, tested or documented.
- If an operation changes nothing in the tree (a read-only check, for example),
  there is nothing to push; do not create an empty commit.
- GitHub Actions is **manual-only** (`workflow_dispatch`). A normal push must not
  start a kernel build or packaging job.
- Routine development is validated **locally**. After pushing a commit, do not wait
  for, poll, or require GitHub Actions before continuing.
- Run the GitHub Actions workflow only when the owner explicitly requests a remote
  CI check. A local successful build/validation is sufficient evidence for
  `compiled` / `packaged` status; it is still not evidence of a physical boot.

## Current direction and physical-test workflow (owner instruction, 2026-09-21)

- First test the repair built from `89a6601` (see `docs/BOOTLOOP_FIX.md`):
  prove `ABL -> Linux -> persistent console -> BusyBox /init` before expanding
  hardware support. The generic initramfs now lives in **init_boot**, so include
  init_boot whenever the new bundle differs from the flashed version.
- The owner explicitly requested flashing this candidate and collecting logs.
  This authorizes a controlled TWRP/adb test of boot, init_boot, vendor_boot and
  the documented dtbo fallback after validating the bundle, device identity,
  partition sizes, backups and per-partition write/read-back hashes. Build and
  validation scripts must remain non-flashing. Do not rewrite recovery, vbmeta,
  bootloaders, userdata or the partition table as part of these tests.
- Start log capture before reboot. Observe for 60–90 seconds, then return to
  recovery and capture immediately. If adb is absent, ask the owner for the
  physical observation/recovery key action; absence of adb is expected with
  this minimal initramfs and does not establish a crash.
- **Every subsequent physical test must have a committed log directory** under
  `reference/boot-tests/test-NNN-YYYYMMDDTHHMMSSZ/`, including failed or aborted
  attempts. Save raw last_kmsg, available pstore, recovery dmesg (labelled as
  recovery), device/layout checks, flash/read-back transcript, artifact hashes,
  source commit, bundle metadata and an observation/result README. Mark absent
  logs explicitly; never fabricate a successful capture or overwrite an older
  test directory. A directory containing only a summary is insufficient when
  raw logs are available. Do not commit firmware images or partition backups.
- Hash the archived evidence and commit/push it to `origin/test` after each
  test, before changing the next kernel/config/DTB. `.work` or external folders
  are staging locations, not the sole home of test evidence. The capture tool
  defaults to the tracked archive; pass CAPTURE_DIR for the specific test.
- Mainline log/marker present: follow the last proven stage and the actual
  panic/probe output. Init reached: verify persistence, then storage and USB
  rescue. Reboots without mainline evidence: validate the sec_log retention
  path and kernel handoff separately. An absent write-back marker, empty pstore
  or a compressed-file DTB offset does not prove that Linux was never entered.
- Keep experiments attributable: change one failure hypothesis per follow-up
  test. MMU-off/head.S or Gunyah watchdog instrumentation remains a separate
  diagnostic branch, not a default workaround. Record the final device state
  and any stock restoration with read-back hashes in the test record.

## Build commands

Normal build:

```bash
./scripts/fetch-mainline.sh
./scripts/build-kernel.sh
```

Clean source-level comparison:

```bash
KERNEL_CLEAN=1 ./scripts/build-kernel.sh
```

Faster compile-only iteration when modules are irrelevant:

```bash
BUILD_MODULES=0 ./scripts/build-kernel.sh
```

Audit stock evidence supplied locally:

```bash
./scripts/audit-stock.sh /path/to/stock.config /path/to/live-device-tree.dts
```

Before committing a script change, at minimum run:

```bash
bash -n scripts/*.sh
```

If the build environment is available, also perform `BUILD_MODULES=0 ./scripts/build-kernel.sh`. For config/DTS/patch changes, a clean build is preferred.

## Bring-up order

Do not debug everything at once. Work in this order unless logs prove another dependency is blocking:

1. ABL accepts the Android v4 image and enters Linux.
2. persistent log / serial diagnostics survive reboot;
3. reserved-memory is safe and there are no TrustZone fatal resets;
4. UFS and/or microSD root storage;
5. USB gadget/Ethernet rescue path;
6. panel/display;
7. touch, buttons and S Pen;
8. GPU/Turnip;
9. Wi-Fi and Bluetooth;
10. audio and DSPs;
11. charging/Type-C/DisplayPort;
12. cameras, sensors and fingerprint/SPSS.

A failure before Linux entry must be debugged as an ABL/boot-image/DT selection problem. An empty pstore is not evidence of a kernel crash if the bootloader never transferred control.

## Samsung ABL constraints

Keep the legacy Samsung selectors in the board DTS unless a physical test proves they are no longer required. The X710 Azkali bring-up and sibling X910 work both demonstrate that Samsung ABL can reject an otherwise valid upstream-style DTB before Linux starts. Preserve `/__symbols__` in DTBs used in experiments that exercise Samsung's DT overlay path (`DTC_FLAGS_... := -@`).

For the pinned Linux 7.2-rc3 baseline, keep `kernel/patches/0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch`: Samsung ABL expects `qcom_tzlog`, `arch_timer`, and `qcom_scm` labels in the SM8550 base tree. Re-check whether the patch is still needed whenever the upstream kernel pin changes.

The current boot-bundle script uses the safer appended-DTB fallback pattern and deliberately does not flash anything. Do not change `dtbo` strategy casually; document the reason and recovery path first.

## Working with the stock config

The owner-extracted stock 5.15.153 `.config` is the **immutable seed and evidence baseline**, but it is not assumed to map one-for-one onto Linux 7.2. It is stored as deterministic Base64/gzip parts under `reference/stock/config/`; `scripts/materialize-stock-config.sh` reconstructs the original bytes and refuses a SHA-256 mismatch.

Use the stock config to answer questions such as:

- was a hardware block enabled in Samsung's kernel?
- was a driver built-in or modular?
- what compiler/Kconfig features did stock use?

For the mainline build, reconstruct the stock config, merge `kernel/config/gts9wifi-mainline.fragment`, then run Linux 7.2 `olddefconfig`. Unknown Samsung/Android-only 5.15 symbols are expected to disappear; required upstream symbols must be asserted explicitly by the fragment/build checks. Never edit the stock seed in place. A refreshed stock extraction must be added as a new identified artifact with updated hashes.

## Patch discipline

- Prefer upstream commits/backports over local patches.
- Every local patch should have one purpose and an explanatory commit message.
- Keep device-specific quirks gated to SM-X710/SM8550 where practical.
- If a patch becomes upstream, replace the local copy on the next controlled kernel rebase.
- Do not add Android-rooting/security modifications to this repository; keep the mainline hardware port focused.
- Do not import Azkali's `c48fedbd799a` early-boot framebuffer/Gunyah watchdog instrumentation into the default patch queue. If conventional logs are unavailable, reproduce it only as a temporary diagnostic series on a dedicated branch.

## Logs to request after physical tests

Ask for the smallest useful evidence set, typically:

```bash
uname -a
cat /proc/cmdline
dmesg -T > dmesg.txt
cat /proc/iomem > iomem.txt
cat /sys/firmware/devicetree/base/model 2>/dev/null
ls -l /dev/dri /dev/mmcblk* /dev/sd* 2>/dev/null
lspci -nn 2>/dev/null
ip -br link
```

For boot failures also collect Samsung/TWRP `last_kmsg` or ramoops/pstore if available. Record the exact artifact hashes that were flashed/tested.
