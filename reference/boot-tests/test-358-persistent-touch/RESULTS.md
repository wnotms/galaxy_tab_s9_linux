# Test358 — stopped before installation

The loader, module and optional GNOME unit passed17 affected host tests, actual
systemd syntax and the read-only exact331/already-loaded check. Installation
stopped before any owned file was written: dpkg-db-backup.service had entered
start-limit-hit. No new insmod, flash, reboot or charging action occurred.

Raw service journal shows five successful backups followed by repeated
start-limit-hit; ExecMainStatus=0. Rootfs has96GiB free. A later read-only check
shows normal current daily timer (nextOct9), currentOct8 realtime and monotonic
both advancing normally. An earlier completed backup's ExecStart timestamp is
Oct25; the rapid-trigger/time discrepancy's cause is **not proven**. Do not
claim a backup-program error or modify RTC/NTP/timer configuration here.

Current touch/GNOME/SSH remain normal on1adc0f13; battery76%,32.3°C,
Good/Discharging. All three owned install targets remain absent. Preserve this
STOP, not an installation pass. A new359 scope may acknowledge only this
recorded start-limit condition and verify one ordinary backup before installing
the same qualified component. No unconditional reset of failed units.

Raw installation JSON is gzip-preserved with stdout/stored hashes in
installation.host-status.json; diagnostics include full service journal.
Results-only tests/build executed:false; prior17 loader tests remain qualified.
3481200s grant remains unused; no firmware/DT/module-directory/config changes.
