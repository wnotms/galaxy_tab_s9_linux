# X710 GPU and GNOME bring-up

## Current result — 2026-10-08

Host preparation is complete; GNOME and GPU firmware are **not deployed**.
The device remains Test331, boot `be1baaaa47fc41f582558f7092c01653`, in the
read-only natural discharge preparation for Test348. Keep that charging round's
frozen kernel/config/DT/modules and rootfs services unchanged. First finish its
registered test and exact restoration to Test331/TWRP, then perform desktop
installation and activation as a separate attributable stage.

Read-only evidence is in
`reference/desktop-bringup/initial-readonly-1791439861/`. It includes the full
kernel journal, input/DRM inventory, APT simulation, raw package metadata and
download URLs. The stock APNHLOS partition was temporarily mounted read-only
under `/run`, inspected for firmware and unmounted; no partition was written.

| Component | Actual observation | Work remaining |
| --- | --- | --- |
| GPU kernel | Mainline `adreno`, `CONFIG_DRM_MSM=y`, card0/renderD128 | First real GPU initialization and hardware rendering |
| Display | DPU card1, DSI-1 connected, 2560×1600 | Mutter/Wayland scanout and GPU/DPU buffer sharing |
| GPU firmware | SQE/GMU/ZAP missing from rootfs | Install the three staged, pinned files |
| Mesa | libgallium 25.0.7 installed; DRI/Vulkan missing | Install staged DRI and Turnip packages |
| GNOME | No installed session or display manager | Install minimal session, controlled first start |
| Touch | Existing DT already describes ST FTS1BA90A at i2c4/0x49; its driver is missing | Independent kernel integration and touch acceptance |
| Input fallback | EF-DX710 keyboard and power keys enumerated | No touchpad currently enumerated |

DRM node presence does not prove hardware acceleration. The GMU has not yet been
shown initialized by a real workload, and renderers must be checked against
llvmpipe/lavapipe fallback. Card numbers are observations, not permanent identity;
select by sysfs driver/connector paths in later tests.

## Reused implementations

- Fedora same-model clean local commit
  `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`: `docs/Hardware-Notes.md`,
  `kernel/files/sm8550-samsung-gts9wifi.dts`, `kernel/files/fts1ba90a.c`,
  `kernel/prepare.sh`. Its GPU stack is mainline MSM plus Mesa Freedreno/Turnip.
  Its `expose-separate-gpu-kms-resources.patch` addresses Xorg PRIME/resource
  enumeration; it is not imported merely to start GNOME Wayland. Current
  `msm.separate_gpu_kms=Y` requires an actual Mutter scanout/rendering test.
- S9 Ultra clean local commit
  `32273b0a410b3e73b20a3a2451e24260fb2a36bd`: useful common SM8550/GNOME
  reference, but its Goodix touchscreen is not the X710 ST controller. Do not
  copy its touchscreen node or electrical parameters.
- The actual pinned Linux 7.2-rc3 tree's `adreno/a6xx_catalog.c` associates
  chip ID `0x43050a01` with `a740_sqe.fw`, `gmu_gen70200.bin` and ZAP. Its
  `drivers/soc/qcom/mdt_loader.c` supports a complete ELF/MBN as well as split
  MDT/bNN files. No KGSL driver or vendor Android userspace is imported.
- GPU blobs: [Azkali same-model firmware repository](https://github.com/Azkali/gts9wifi-firmware),
  pinned `3f6fff46e09fa359005653c2027d12525ec192ee`.
  The source/hash manifest records each exact URL and byte count. The complete
  12,088-byte ZAP ELF has three program headers, one load segment, an embedded
  hash segment and no missing bNN segments. Staging it under the DT-requested
  `.mdt` name changes no bytes. Secure-world authentication remains untested.

Source files used for these conclusions are SHA-256 recorded alongside the
inventory. Firmware is not committed or claimed to have been generated here.

## Prepared userspace

`userspace/gnome/packages.txt` requests GNOME session/shell/GDM/settings/console/
files, Mesa DRI/Vulkan, diagnostic tools and fonts, without the larger desktop
metapackage. Actual device APT simulation: **368 new packages, no upgrade or
removal**, 165,385,796 download bytes and approximately 743 MB installed space.
All 368 host downloads matched SHA-256 and size from the existing Debian APT
metadata. This is package preparation, not an installation success.

The downloaded ARM64 packages contain `msm_dri.so`,
`libvulkan_freedreno.so`, `freedreno_icd.json` and GNOME Wayland sessions.
No Zink/software-rendering environment overrides or third-party Mesa repository
are needed for the first attempt. GNOME 48 is the current Debian trixie selection
in this inventory; do not equate it with Fedora's newer GNOME release.

## Device installation and first acceptance

1. After Test348 is closed, register desktop bring-up separately. Save current
   boot/config/notes, package state, full journal and working ADB/Wi-Fi rescue.
   Keep known-good boot/modules; desktop rollback must not depend on the GUI.
2. Copy the verified cache to the Debian filesystem and the three firmware
   files to the exact `lib/firmware/qcom/` destinations in the staging manifest.
   Preserve any pre-existing destination instead of replacing it silently.
   The minimal initramfs carries no firmware today. First check whether normal
   rootfs firmware loading suffices; only change the boot packaging if a real
   early-load failure proves it necessary.
3. Re-run APT simulation against **local absolute `.deb` paths**. Require the
   recorded versions, no removals, no upgrade of existing packages and healthy
   dpkg state. Absolute paths avoid assuming epoch-containing APT cache filenames.
   If the package state has changed, refresh the manifest rather than force it.
4. Install with service startup inhibited (`policy-rc.d`, preserving/restoring
   any existing policy) and noninteractive debconf. Do not let GDM start as a
   package post-install side effect. Preserve USB/NCM/SSH units. Record the
   resulting package state and installed firmware hashes.
5. From authenticated rescue, perform one controlled GPU initialization via
   Vulkan diagnostics. Save full journal; require an Adreno device and no GPU
   fault/firmware authentication failure. Node presence or a software renderer
   is not a GPU pass. Do not rebind DSI/DPU or cycle their rails.
6. Start GDM once and inspect `journalctl -b -u gdm3`, the user session and
   Mutter logs. Require visible GNOME Wayland, working keyboard and GPU-backed
   rendering with the separate DPU connector. Save logs on the first failure;
   stop GDM and return to tty/rescue rather than repeatedly rebooting.
7. Once touch is ported, test ten contacts, coordinate orientation and edge
   accuracy. Then use GNOME display settings for 200% scale (1280×800 logical)
   and test the on-screen keyboard. Do not present an untested scaling default
   or merely running GNOME as completed tablet touch support.
8. Rollback: stop/disable GDM, return to text target if required, restore saved
   desktop configuration/firmware and review package removal using the saved
   package-state delta. Do not touch charging, partitions or paired modules as
   a desktop recovery shortcut. End in the registered state.

Touch is a separate, minimal same-model Fedora driver port; the DT node already
exists. Its `linux/wacom_wez01.h` coordination dependency needs an explicit
decision before import. Do not silently pull in S Pen or the whole Fedora patch
queue to satisfy one include. No touch firmware update is planned.

## Checks executed

- Thirteen affected host tests passed (package identity/download failure/cache
  preservation and ZAP ELF/staging validation), 0.005 seconds.
- All package and firmware cache hashes/lengths checked; complete ZAP layout
  checked; package contents inspected for native Freedreno/Wayland components.
- Kernel build, full regression, GPU activation, GNOME installation, touch and
  desktop hardware tests: **executed: false**. No kernel/config/DT/build routing
  changes; existing Test348 qualification is preserved separately.
