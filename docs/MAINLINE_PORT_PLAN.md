# SM-X710 mainline port plan

## 1. Strategy

The maintainable route is the same architecture used successfully by other modern Android-tablet mainline ports:

```text
pinned upstream Linux
        |
        +-- board DTS translated to upstream bindings
        +-- small reviewable patch stack
        +-- a few out-of-tree drivers while upstream support is missing
        +-- mainline base config + device fragment
        |
        +-- LLVM build in a disposable worktree
        |
        +-- Image.gz + DTB + matching modules
        |
        +-- Android boot header v4 packaging for Samsung ABL
```

Do not make Samsung 5.15 the long-term kernel tree. It remains valuable as hardware documentation and as a reference when translating clocks, regulators, GPIOs, I2C addresses, reserved memory and firmware topology.

## 2. Why Linux 7.2-rc3 is pinned initially

SM8550 upstream support has matured substantially, and the existing X710 and X910 ports have a physically validated baseline on Linux 7.2-rc3. Holding that kernel constant while importing the board layer makes failures attributable to the board delta rather than a simultaneous kernel upgrade.

After the repository reproduces a known-good baseline, rebase one major kernel release at a time and keep each rebase separate from functional changes.

## 3. Evidence from the supplied stock SM-X710 files

The uploaded stock artifacts establish the following facts:

| Item | Stock evidence |
|---|---|
| Model | `Samsung GTS9WIFI PROJECT (board-id,04)` |
| SoC | Qualcomm `kalama` / SM8550 |
| ABL board selector | `qcom,board-id = <0x10008 0x04>` |
| Stock kernel | Linux arm64 5.15.153 |
| Stock compiler | Android clang 14.0.7 |
| Panel | `GTS9_ANA38407_AMSA10FA01` |
| Touch | STM FTS1BA90A |
| Pen | Wacom W90xx / WEZ01 family |
| WLAN/BT | QCA6490 |
| UFS | controller at `0x1d84000` in downstream tree |
| microSD | SDHCI at `0x8804000` |
| Charging | SM5714 + SM5440 direct charger |
| USB-C | SM5714 PD, PS5169 redriver, PTN3222 eUSB2 repeater |
| Speakers | four CS35L45 amplifiers |

This also proves that the X710 must not simply reuse the X910 hardware fragment: the touch and WLAN families differ.

## 4. Mainline bootstrap source

The initial board DTS is imported from the hardware-tested SM-X710 mainline work in `troikoss/gts9wifi-fedora` at the exact commit documented in `kernel/PROVENANCE.md`. Its Samsung ABL selectors were cross-checked against the owner's live downstream DTS.

The reference project's full out-of-tree driver and patch stack is **not** copied wholesale. This repository starts with upstream-supported foundations and adds missing panel/touch/charging/audio/etc. pieces subsystem by subsystem. That keeps each change attributable and makes later upstreaming realistic.

The X910 repositories remain useful for shared SM8550/Samsung issues (ABL DT selection, eUSB2, UFS, QTEE/SPSS, charging, DisplayPort), but X710-specific hardware always wins when the two differ.

## 5. Build configuration model

The stock 5.15.153 config is reference-only. Mainline uses:

```text
upstream arm64 defconfig
             +
kernel/config/gts9wifi-mainline.fragment
             |
             v
         olddefconfig
```

This is preferable to feeding the stock `.config` to Linux 7.2 because hundreds of Samsung/Android-only symbols would disappear while new mainline dependencies would be resolved implicitly. Keeping a clean mainline base plus a device fragment makes the actual port requirements reviewable.

## 6. Samsung boot chain

The tablet keeps the stock Samsung ABL. The expected test bundle is Android boot header v4:

- `boot.img`: mainline `Image.gz` with the board DTB appended;
- `init_boot.img`: small/empty legacy-LZ4 generic ramdisk when the real initramfs does not fit the 8 MiB partition;
- `vendor_boot.img`: board DTB, cmdline/bootconfig and the full platform initramfs fragment;
- `dtbo.img`: early experiments should preserve the validated appended-DTB fallback rather than assume Samsung's downstream `ufdt` accepts an upstream tree;
- `vbmeta.img`: only alter verification state deliberately and with a recovery plan.

`scripts/build-boot-bundle.sh` assembles files only. It never writes a block device.

## 7. Bring-up milestones

### M0 — reproducible compile

Acceptance:

- pinned upstream commit verified;
- clean worktree preparation succeeds;
- `Image.gz` and `sm8550-samsung-gts9wifi.dtb` build with LLVM;
- release/config/artifact SHA-256 manifest emitted.

### M1 — Linux entry and persistent diagnostics

Acceptance:

- Samsung ABL transfers control to Linux;
- exact tested boot artifact hashes recorded;
- UART, Samsung last-kmsg path or ramoops/pstore provides logs across reboot;
- no secure-firmware fatal reset during the initial probe window.

### M2 — storage and rescue channel

Acceptance:

- internal UFS and/or microSD enumerates reliably;
- an initramfs can mount the intended root;
- USB networking or another rescue channel works before desktop work begins.

### M3 — display and input

Acceptance:

- ANA38407 panel reaches native mode without relying on a stale splash;
- FTS1BA90A touch coordinates and orientation are correct;
- power/volume buttons work;
- Wacom pen basic position/pressure works before advanced tilt/palm-rejection work.

### M4 — accelerated desktop

Acceptance:

- Adreno 740 probes with correct firmware;
- `/dev/dri/renderD*` exists;
- Mesa Turnip renders without llvmpipe fallback;
- suspend/resume does not regress display/GPU.

### M5 — radios, audio and power

Acceptance:

- QCA6490 PCIe/Wi-Fi and UART Bluetooth are stable;
- ADSP/audio path and all four CS35L45 amplifiers work;
- battery readings, charging, USB-PD and USB host/device roles are validated;
- DisplayPort alt mode is tested separately from basic Type-C.

### M6 — peripherals

Cameras, sensors, fingerprint/SPSS/TEE, cover accessories and polish belong here. Do not let one of these block earlier core milestones.

## 8. Validation discipline

For each physical test, record:

1. git commit of this repository;
2. upstream Linux commit;
3. `kernel.release`;
4. SHA-256 of Image, DTB and every boot image used;
5. exact flash/write procedure performed manually;
6. resulting logs and a concise observed outcome.

A useful status vocabulary is:

- **compiled** — build succeeds;
- **booted** — Linux reached userspace or an expected initramfs shell;
- **enumerated** — kernel created the expected device/interface;
- **observed** — physical behavior was seen;
- **verified** — repeatable test passed on the target tablet.

Do not collapse those states into a single check mark.

## 9. References used for the initial architecture

- `troikoss/gts9wifi-fedora`: current SM-X710 mainline/Linux 7.2-rc3 implementation and boot-chain handling.
- `agcarbajo/ubuntu-galaxy-tab-s9-ultra` and `agcarbajo/postmarketos-galaxy-tab-s9-ultra`: mature sibling SM-X910 mainline work, especially ABL/SM8550 quirks and reproducible worktree builds.
- postmarketOS generic-kernel guidance: keep close-to-mainline kernels current, use LLVM, and minimize non-upstream patch carry.
- Samsung downstream SM8550 5.15 trees: hardware documentation only.

See `kernel/PROVENANCE.md` for the exact imported source pin.
