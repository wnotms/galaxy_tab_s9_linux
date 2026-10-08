# X710 GNOME preparation

The owner selected GNOME for tablet touch use. This directory prepares Debian
13 ARM64 packages and the existing mainline Adreno 740 driver's firmware on the
**host**, without installing, starting a desktop, rebooting or touching charging.

Current inventory, pinned sources and qualification:
[GPU_GNOME_BRINGUP.md](../../docs/GPU_GNOME_BRINGUP.md).

Current deployment is newer than the original preparation below: Test352–357
accepted GPU/GNOME/power-key/ordinary touch. Test359 installed the optional
[touch component](touch/README.md), whose load gate permits only exact331 and
whose enable link belongs to GDM, leaving text/charging boots alone. Existing
GDM masks remain; Test360 accepted new-boot GDM-triggered loading and owner login/touch.
Test362 prepared the separate optional [S Pen component](pen/README.md); its
controller enumerated, but owner pen input was not observed in the bounded
window. The package
preparers/installer do not automatically deploy this later integration or the
power-key schema override.

```sh
python3 userspace/gnome/prepare.py \
  reference/desktop-bringup/initial-readonly-1791439861/gnome-packages.json \
  --output out/gnome-trixie-arm64/packages
python3 userspace/gnome/prepare-firmware.py \
  reference/desktop-bringup/initial-readonly-1791439861/gpu-firmware-source.json \
  --source out/gnome-trixie-arm64/firmware-source \
  --output out/gnome-trixie-arm64/firmware-root
```

The package preparer fetches the exact SHA-256/size-bound URLs from the device's
APT simulation. Correct cached files are reused, mismatches are preserved and
rejected. No `apt upgrade`, installation or device command is implemented.
`packages.txt` defines the requested minimal GNOME session and diagnostics;
the manifest also binds its dependencies and records the current boot ID.

Download firmware from the three pinned URLs in `gpu-firmware-source.json` into
the indicated source directory. The firmware preparer checks the complete set
before staging it into a **new empty directory**. It keeps ZAP bytes unchanged
under the current DT's `qcom/a740_zap.mdt` filename. Its ELF validation establishes
that the file contains the load and hash segments; it does not authenticate the
signature against the tablet's secure firmware. Firmware binaries and `.deb`
files stay in `out/`, not Git or a new Windows staging directory.

Run only the affected offline tests:

```sh
python3 -m unittest discover -s tests -p 'test_gnome*.py' -v
```

Installation and first GPU/GNOME activation are separate device stages described
in the bring-up document. Neither preparer can perform them.

## Controlled installation tool

Test352 corrects local APT acquisition after Test351 stopped before installation.
Sources are disabled only for the invocation using actual empty owned paths;
all supplied archives are verified local files. No system source configuration
is changed. `--no-download` is unsuitable here because APT must acquire the
command-line local files outside its archive cache.

Test349 originally registered desktop work during discharge, superseding the
earlier after-Test348 ordering here. Keep charging inputs frozen and GDM inactive
before Test348; record added rootfs packages/firmware in its fresh admission.

`install.py` defaults to host cache validation only:

```sh
python3 userspace/gnome/install.py \
  reference/desktop-bringup/initial-readonly-1791439861/gnome-packages.json \
  --cache out/gnome-trixie-arm64/packages \
  --firmware out/gnome-trixie-arm64/firmware-root
```

Test349 can transfer this directory,
manifest, package cache and firmware staging tree. Native X710 Debian execution
requires explicit `--execute`, `--expected-boot-id <current UUID>` and a **new**
`--evidence <directory>`. It refuses charging-test boots/parameters. It checks
dpkg and a local APT simulation, forbids removals/upgrades/unexpected packages,
then installs the verified local packages and firmware. Existing package
versions and GPU firmware must match; differing files are not overwritten.

The installer leaves **persistent masks** for `gdm.service`, `gdm3.service` and
`display-manager.service`, including after a failed installation. Debian's GDM
postinst respects the masked display-manager link. It temporarily denies
package service actions with `policy-rc.d`, restoring the original file or
symlink afterwards. Ordinary failures restore that policy in `finally`; a hard
kill/power loss may leave its clearly named adjacent backup. Inspect the saved
stage and confirm APT has ended before restoring an interrupted policy. The
tool refuses a stale backup instead of overwriting it.

Output logs stream to evidence files while APT runs; `summary.json` records
checkpoints. A package failure retains the GDM guards and evidence, and needs
reviewed dpkg recovery; it does not attempt automatic package removal/retry.
It never starts GDM, loads touch, reboots, flashes, changes charging or updates
APT indexes. Package installation alone is not desktop hardware acceptance.

For the later first GUI test, remove only the recorded masks, then start
`gdm.service` once from rescue. Inspect Mutter/GDM and the visible session before
enabling GDM for future boots. The current Debian user `ms` already exists;
no root auto-login or password change is part of this preparation.

## Single transfer artifact

The verified archive is `out/gnome-trixie-arm64/gts9-gnome-deploy.tar` (about
166 MB). Its 381 regular files include the local package cache, GPU firmware,
installer, checksums and an explicitly optional/unloaded touch module. Source
and archive identities are recorded in
`reference/desktop-bringup/deploy-bundle/bundle.json`; reproduce it with that
directory's `build.py`. No Windows mirror or device transfer has been made.
Archive validation checks its actual full file set and content. It does not
establish GPU, GNOME or touch hardware acceptance.

## Desktop heat observation

Test361 sets only the ordinary user ms interface enable-animations=false after
saving its previously absent explicit dconf key. This is not a global schema
override or an installer default. Use the active user's runtime bus for live
notification. To restore this original state, reset only
/org/gnome/desktop/interface/enable-animations on that bus. thermal.py collects
read-only activity/temperature/runtimePM; it changes no OPP/governor/charging
policy and is not a permanent background service. Raw normal-use windows may
have different interaction/apps, so they do not establish causal cooling.
