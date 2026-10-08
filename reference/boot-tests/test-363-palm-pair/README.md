# Test363 — opt-in Wacom/FTS palm-rejection pair

This registration is for one fresh ordinary Test331 desktop boot. The current
boot already has the ordinary FTS module and Test362 Wacom module loaded, so no
replacement or unload is attempted in that boot. A fresh boot is required to
prove the pair ordering.

The device-side operation, when explicitly started, is limited to the installed
identity-gated `gts9-palm` loader: one normal Wacom insmod followed by one
normal `fts1ba90a-palm.ko` insmod from outside the181-file production module
directory. It must stop if ordinary FTS is already present. No force flags,
sysfs writes, firmware update, I2C scan, rail cycle, flash, charging change or
automatic reboot is allowed.

Preflight must retain boot ID/config/notes, battery health, GDM/SSH and failed
units. After the pair binds, check both input devices and the kernel journal for
probe/I2C/IRQ/CPU/GPU faults. A separate short non-grabbing capture then asks
the owner to hover, tap, draw, press the side button, lift the pen, and use a
finger while the pen is near the panel. The expected behavior is pen events,
normal touch after pen removal, and no finger stream while pen proximity is
active. This is the first physical test of the optional palm-aware module;
probe or module-load success alone is not acceptance.

Stop on identity change, loader/probe error, IRQ storm, new severe kernel fault,
battery health/temperature failure, lost SSH/GNOME/touch, or any unexpected
ordinary FTS ownership. Preserve the first full journal and raw input evidence.
Rollback is the exact Test331 normal boot; no partition write is needed because
this test uses current userspace modules only. Test348 charging grant remains
unused.
