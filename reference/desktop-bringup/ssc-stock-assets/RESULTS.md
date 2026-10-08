# Stock sensor assets collected; deployment incomplete

Registered at `b7575189`, collected over authenticated Wi-Fi SSH on Test331 boot
`28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af`, address `10.175.236.134`.
The export took 24.955 seconds: 316 regular files / 73,811,754 bytes, no links
skipped. Every size/hash/archive mtime matches the embedded manifest. All three
temporary mounts were removed. ADSP remained offline before/after collection.
Host proprietary content remains under ignored, private `out/ssc-stock-assets/`;
only paths, hashes, provenance and derived structural results are in Git.

| Source | Files | Access |
| --- | ---: | --- |
| apnhlos `/dev/sda17` | 55 | VFAT, ro/nosuid/nodev/noexec |
| dsp `/dev/sda16` | 79 | ext4, ro/nosuid/nodev/noexec/noload |
| persist sensors only `/dev/sda5` | 182 | ext4, ro/nosuid/nodev/noexec/noload |

`MANIFEST.json` preserves effective mount flags, source names, source nanosecond
mtimes and exact archive mtimes. The host verifier rejects unsafe/duplicate/
special tar entries, changed file sets/bytes/timestamps, unsuccessful cleanup,
missing/truncated MDT segments and invalid registry metadata. Seventeen focused
tests pass, zero skips. No kernel build or full regression was executed; no
kernel/build/routing input changed.

## Firmware

The parser follows the pinned Linux 7.2-rc3 `drivers/soc/qcom/mdt_loader.c` and
`include/linux/soc/qcom/mdt_loader.h`: ELF32 tables, packed/embedded/split hash
metadata, loadable segment filtering, exact bNN sizes, BSS handling and aligned
address bounds. Non-contiguous segment numbers are expected; BSS does not need
a file. This is structural verification, **not firmware authentication**.
Samsung TrustZone acceptance remains an unexecuted controlled-boot test.

| Image | Program headers | Required data segments | Memory span |
| --- | ---: | ---: | ---: |
| adsp.mdt | 51 | 45 | 94,060,544 bytes |
| adsp_dtb.mdt | 3 | 1 | 12,288 bytes |

Both hash metadata blocks are packed into the MDT. All required split data
files are present and exact-sized. Their address spans fit the **existing X710**
ADSP and ADSP-DTB reserved regions, without changing DTS or using smaller
reference-board sizes. Full machine-readable details: `VERIFIED.json`.

## Registry layout and outstanding inputs

Stock has `persist/sensors/registry/registry/<groups>` and an empty completion
marker `.../registry/sensors_registry`. The copied `sns_reg_config` timestamp
cache references **35** `/vendor/etc/sensors/config/*.json` inputs, all at Unix
mtime `1640995200`. These inputs were **not** in the collected persist subtree.
Do not synthesize them or claim an empty config directory is qualified.

Fedora-pinned `hexagonrpcd/rpcd_builder.c` maps virtual
`/mnt/vendor/persist/sensors/registry` (and `/persist/sensors/registry`) to
`PREFIX/sensors`. Therefore map stock files **relative to
persist/sensors/registry/** into `PREFIX/sensors/`; e.g. the stock double-registry
marker becomes `PREFIX/sensors/registry/sensors_registry`. Preserve source and
cache timestamps. Do not copy the extra registry level or normalize everything
to zero: S9 Ultra's zero-mtime helper is for its own zero-valued cache.

The registered daemon uses `-s`, which attaches an existing sensors PD via
`FASTRPC_IOCTL_INIT_ATTACH_SNS`; absence of `fastrpc_shell_2` is not by itself a
missing-firmware failure. ADSP libraries were collected; CDSP libraries are
inventory only and do not authorize CDSP activation. No audio route is enabled.

Next: collect just the stock Android vendor sensor config inputs, reconcile
hashes/mtimes with the cache, then build an isolated writable **copy** for
HexagonFS and register one controlled early-boot experiment. Current Debian
has no mounted vendor logical partition; `/dev/mapper` has only `control`.
Do not late-start ADSP on the running desktop, expose real persist to a daemon,
or auto-restart a failed sensors PD. Rotation is not hardware accepted yet.

No firmware/package installation, service activation, rootfs change, flash,
reboot, kernel/config/DT/module/input/USB/charging change occurred. Host network
timeouts before it returned to `10.175.236.63/24` do not establish a CPU wedge.
Test363 owner pen position/palm result is retained; tip/pressure/button exercise
awaits owner readiness. Test348 authorization remains unused.
