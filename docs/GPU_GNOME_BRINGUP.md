# X710 GPU and GNOME bring-up

## Current result — 2026-10-08

GNOME and GPU firmware are deployed. Test352 installed368 verified packages and
three pinned GPU files; Test353 fixed only render-group membership and verified
ordinary-user freedreno FD740 EGL and Turnip Adreno740 Vulkan. GNOME48.7/Mutter
Wayland obtained an accelerated EGL context with the existing separate DPU/GPU
configuration. Test354 owner confirmed keyboard/password login and desktop use.
These are functional checks, not performance or long-term reliability claims.

Test355 stopped **before any touch load** after the owner reported poweroff and
manual restart. Previous-boot logs show a short power-key event, GNOME48.1's
VM policy requesting PowerOff, and orderly systemd shutdown. Existing logind
ignore/backlight helper was already correct. Test356 sets only GNOME
power-button-action=nothing; owner confirms screen off/on and usable desktop,
authenticated SSH confirms sameboot and two short-key events with no poweroff.
The policy source is userspace/gnome/99-gts9-power-key.gschema.override.

Test357's accepted331 boot was1adc0f13-a210-4856-bb15-c6e9df17867a, Wi-Fi10.175.236.157.
Test357 loaded the byte-identical Fedora X710 touch module once from var/tmp
outside the accepted181-module directory. Existing7-0049 DT client is bound and
input event4 enumerated; five-second IRQ delta126, no new kernel fault.
Test357 owner confirms correct position/direction and desktop use; raw191.244s capture confirms two simultaneous contacts and final all-slots released. Capture is terminal, not live.
Test359 now installs an identity-gated optional touch loader and GDM-Wants unit,
outside181dir; current-boot start was already-loaded/zero-insmod. Original358
zero-write stop for dpkg backup start-limit remains recorded; one scoped backup
acknowledgement/verification in359 succeeded without timer/clock policy changes.
No suspend/double-tap wake or S Pen acceptance yet.
The normal loader accepted all ABI/BTF checks; unsigned external-module taint
is explicitly recorded (MODULE_SIG_FORCE=n), not a forced-load bypass.

After359 the owner manually rebooted to331 boot25ff0ad0-cf2f-4cc6-971d-2b38365da2db.
Test360 now started GDM once: the enabled optional touch unit performed one
normal load, bound7-0049/event4, sameboot/GDM/SSH/10s initial health passed.
Persistent masks restored without --now; GUI remains active, owner confirms login/
touch desktop normal in this new boot. Text-only startup does not load touch. Kernel/config/DT/charging code and original181 modules
remain unchanged. Test348's authorized1200s attempt is unused. Its original
natural-discharge watcher is terminal, not running. Before future charging work,
stop desktop and account for GPU/userspace/power-policy/touch changes in fresh
admission; preserve original safety limits and eventual exact331/TWRP endpoint.
No charging test runs as part of this desktop work.

| Component | Evidence | Remaining |
| --- | --- | --- |
| GPU | Test353 ordinary-user freedreno FD740 / Turnip Adreno740 | Workload/performance and long-duration checks |
| Display | Existing2560×1600 DPU/DSI, GNOME Wayland visible; owner touch orientation correct | UI scaling/dynamic rotation acceptance |
| Firmware/Mesa/GNOME | Test352 exact installation; Test353/354 runtime and owner confirmation | Optional userspace warning follow-ups |
| Power key | Test356 nothing policy + owner two short presses + sameboot journal | Suspend/long-hold remain separate |
| Touch | Test357 ordinary/two-contact acceptance; Test359 optional persistent component installed | Ten-contact and suspend/dynamic-rotation checks |
| S Pen | Test362 optional Fedora-derived module compiled W=1;29 export CRCs match331 | First registered input/owner acceptance; palm integration separate |

Initial read-only inventory remains at
reference/desktop-bringup/initial-readonly-1791439861/; its missing-firmware/desktop
observations are historical and superseded by Test352–357. No partition was
written for desktop work. Actual tests' RESULTS/summary/raw evidence take
precedence over the original deployment plan below.

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
  `.mdt` name changes no bytes. The later Test352/353 renderer initialization succeeded; this initial layout check alone did not prove secure-world authentication.

Source files used for these conclusions are SHA-256 recorded alongside the
inventory. Firmware is not committed or claimed to have been generated here.

## Prepared userspace

`userspace/gnome/packages.txt` requests GNOME session/shell/GDM/settings/console/
files, Mesa DRI/Vulkan, diagnostic tools and fonts, without the larger desktop
metapackage. Actual device APT simulation: **368 new packages, no upgrade or
removal**, 165,385,796 download bytes and approximately 743 MB installed space.
All 368 host downloads matched SHA-256 and size from the existing Debian APT
metadata. This original preparation was later installed successfully in Test352; exact versions and raw installation results are recorded there.

The downloaded ARM64 packages contain `msm_dri.so`,
`libvulkan_freedreno.so`, `freedreno_icd.json` and GNOME Wayland sessions.
No Zink/software-rendering environment overrides or third-party Mesa repository
are needed for the first attempt. GNOME 48 is the current Debian trixie selection
in this inventory; do not equate it with Fedora's newer GNOME release.

## Original installation sequence and remaining acceptance

1. Register Test349 desktop bring-up separately. Save current
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
   `userspace/gnome/install.py` now implements the local-cache/simulation gate,
   temporary service policy and persistent GDM/display-manager masks. It defaults
   to cache validation; Test352 records the actual corrected local-only installation. The current
   ordinary user `ms` was confirmed read-only on the same Test331 boot.
5. From authenticated rescue, perform one controlled GPU initialization via
   Vulkan diagnostics. Save full journal; require an Adreno device and no GPU
   fault/firmware authentication failure. Node presence or a software renderer
   is not a GPU pass. Do not rebind DSI/DPU or cycle their rails.
6. Start GDM once and inspect `journalctl -b -u gdm3`, the user session and
   Mutter logs. Require visible GNOME Wayland, working keyboard and GPU-backed
   rendering with the separate DPU connector. Save logs on the first failure;
   stop GDM and return to tty/rescue rather than repeatedly rebooting.
   Debian's actual primary unit is `gdm.service`; remove the installer's recorded
   masks first and capture that unit's journal. Keep automatic startup disabled
   until the controlled first session passes.
7. Once touch is ported, test ten contacts, coordinate orientation and edge
   accuracy. Then use GNOME display settings for 200% scale (1280×800 logical)
   and test the on-screen keyboard. Do not present an untested scaling default
   or merely running GNOME as completed tablet touch support.
8. Rollback: stop/disable GDM, return to text target if required, restore saved
   desktop configuration/firmware and review package removal using the saved
   package-state delta. Do not touch charging, partitions or paired modules as
   a desktop recovery shortcut. End in the registered state.

Touch is now prepared as a separate, byte-identical same-model Fedora external
module in `kernel/desktop/fts1ba90a/`; the DT node already exists. The imported
`linux/wacom_wez01.h` keeps its original optional false-returning stub while
Wacom is unconfigured. No S Pen driver or wider Fedora patch queue is pulled
in. The default build and Test348 inputs remain unchanged. The module compiled
against the qualified Test348 provider with W=1 and passed eight actual-C
decoder tests; Test357 loaded it transiently after direct exact331 export-CRC/BTF checks. Test357 ordinary touch/two contacts and owner position/direction acceptance passed. No touch firmware update
is planned. See that directory's README and its separate offline evidence.

## Initial host preparation checks (historical)

- Thirteen affected host tests passed (package identity/download failure/cache
  preservation and ZAP ELF/staging validation), 0.005 seconds.
- All package and firmware cache hashes/lengths checked; complete ZAP layout
  checked; package contents inspected for native Freedreno/Wayland components.
- Kernel build, full regression, GPU activation, GNOME installation, touch and
  desktop hardware tests: **executed: false**. No kernel/config/DT/build routing
  changes; existing Test348 qualification is preserved separately.

Computer input control findings are in
[SM5714_USB_INPUT_CONTROL.md](SM5714_USB_INPUT_CONTROL.md).

## GNOME power-key integration

Install the owned99-gts9-power-key.gschema.override into
/usr/share/glib-2.0/schemas/ and run glib-compile-schemas there. The prepared APT
installer does not currently apply this later integration automatically. Existing
users may have an explicit dconf value: record it and set only
org.gnome.settings-daemon.plugins.power power-button-action to nothing for the
ordinary user and Debian-gdm, using their own clean D-Bus/session environment.
Test356 stores exact before/after values and rollback. This keeps the existing
gts9-power-key.service in charge of short-press backlight changes; do not change
logind, falsify virtualization, or grab the PMIC key. Other power settings remain
unchanged; this fix is not suspend/idle-power qualification.

## Desktop heat observation

Owner reports heat while GUI active. Test360 only recorded startup snapshots:
pack25.4°C before/after11.649s; GPU simple_ondemand/final220MHz; CPU schedutil.
CPU7 cached frequency is high before GUI too, insufficient to infer sustained
load. Surface/SoC temperature and long-duration heat cause remain unmeasured.
Prioritize an independent idle/ordinary-use profile, background rendering and
reversible GNOME/display preferences. This is not permission to change charging
current, OPP/clock/thermal protections or to reuse348 as a heat experiment.

Test361 completed two60s ordinary-use windows and set only ms interface
enable-animations=false through the active user bus. Original explicit key
absent: reset it to roll back. GPU runtime suspend counters and CPU7 idle time
advance normally. Screen was2047/2047, QQ/activity differed; pack26.0->26.8°C.
Owner says current run has no heat, previous run did; historical cause remains
unproven. Retain owner brightness, no lower-default change or extra heat trial. Full raw
and exact counter semantics in test361. No hardware/charging policy change.

## S Pen first-stage preparation

Optional driver at kernel/desktop/wacom-wez01 reuses Fedora same-model WEZ01,
with small timer/devres/probe-error fixes and15 affected actual-C tests. Test362
registers one currentboot-only normal load after checking all29 imports against
exact331 Image. Existing DT already supplies i2c3/0x56/GPIO154. No firmware/
charging/config/DT/181-module directory change. Accepted touch remains its
disabled Wacom-stub build; kernel pen-proximity palm rejection is not yet wired.
Build/ABI qualification is not physical input acceptance.
