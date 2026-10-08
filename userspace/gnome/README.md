# X710 GNOME preparation

The owner selected GNOME for tablet touch use. This directory prepares Debian
13 ARM64 packages and the existing mainline Adreno 740 driver's firmware on the
**host**, without installing, starting a desktop, rebooting or touching charging.

Current inventory, pinned sources and qualification:
[GPU_GNOME_BRINGUP.md](../../docs/GPU_GNOME_BRINGUP.md).

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
