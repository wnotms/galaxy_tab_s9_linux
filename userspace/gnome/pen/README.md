# Optional persistent X710 S Pen

This component uses the locally built Fedora-derived `wacom-wez01.ko` from
Test362. It is intentionally separate from the generic rootfs installer and
from the accepted touchscreen component. Install the module at
`/usr/local/lib/gts9-desktop/wacom-wez01.ko`, the loader at
`/usr/local/libexec/gts9-pen`, and this unit in `/etc/systemd/system/`.

The loader accepts only the Test331 release/config/notes and the exact module
hash, rejects `lpcharge=1` and SM5440 experiment command lines, verifies the
existing `wacom,w90xx` DT client, and makes at most one ordinary `insmod`.
Other kernels safely skip; an approved kernel with a bad module or failed probe
is an error. It never scans I2C, writes sysfs, updates firmware, unloads or
retries. The GDM Wants relationship keeps text-only and charging boots free of
the optional driver. No pen proximity/palm integration is enabled in the FTS
module yet; existing touch behavior remains unchanged.

This is preparation only. Test362's controller probe succeeded, but its bounded
capture had no owner pen interaction and therefore did not establish physical
coordinate, pressure, button, hover, release, suspend or calibration acceptance.
Enable the unit only in a separately registered desktop boot scope.
