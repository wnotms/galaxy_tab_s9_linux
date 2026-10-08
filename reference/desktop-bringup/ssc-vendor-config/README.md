# Registered read-only vendor sensor input collection

Purpose: fill the 35 missing stock sensor configuration inputs identified by
`ssc-stock-assets/VERIFIED.json`, without starting or installing the sensor stack.
Same Test331 boot `28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af`, X710 compatible,
authenticated SSH to `10.175.236.134`, ADSP offline are mandatory.

`userspace/sensors/read-vendor-sensors.py` reads at most the first 1 MiB of
`/dev/disk/by-partlabel/super` for LP metadata. Both geometry copies and slot 0
primary/backup headers/tables must validate with SHA-256 and agree. Only the
unsuffixed, read-only vendor partition on one linear extent in one super device
is accepted; A/B, fragmented, multi-device, sparse/zero or unknown layouts stop.
The physical super size and all offsets/bounds must agree.

Create one **read-only** temporary loop device bounded to that exact vendor
extent; confirm its kernel read-only state. Only ext4/EROFS is accepted. Mount
it under a private `/run/gts9-vendor-sensors-*`, `ro,nosuid,nodev,noexec`, with
`noload` for ext4. Verify effective flags, read **only etc/sensors/** regular
files, refuse links/specials, cap to 512 files / 8 MiB total / 1 MiB per file.
Save original mtimes and hashes, unmount normally and detach only the allocated
loop, then remove the empty temporary directory. Never force cleanup or expose
real persist to a daemon. Reconfirm boot and ADSP offline before publishing an
archive. On any mismatch/error retain partial host evidence and stop.

This is stock input collection, not a new hardware feature experiment. No
partition/filesystem write, real persist mount, firmware/package installation,
service activation, DSP start, flash/reboot, input/USB/charging/kernel/DT/config
change. Host archive stays private under ignored `out/ssc-vendor-config/`;
proprietary config bytes are not committed. Compare all required input mtimes
against the already collected X710 registry cache, not S9 Ultra defaults.

Rollback: only normal unmount/detach/rmdir of our temporary resources; no image
deployment is required. ADSP early-boot activation remains a separate future
registration. Twelve focused LP fixture tests and Python syntax must pass;
unchanged kernel and existing sensor builds do not need rebuilding.
