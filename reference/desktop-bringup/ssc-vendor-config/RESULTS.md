# Vendor sensor inputs collected; offline asset package verified

Collection was registered/pushed at `3658cb90` before execution. The device
remained on Test331 boot `28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af`, Wi-Fi
`10.175.236.134`, ADSP offline. Export completed in **1.217 seconds**.

Both LP geometry copies and slot 0 primary/backup metadata validated and agreed.
The unsuffixed vendor partition has one read-only linear extent within super:
offset 7,227,834,368 bytes, length 1,723,756,544 bytes; super size 11,643,387,904.
One bounded read-only loop was mounted as EROFS with effective
`ro,nosuid,nodev,noexec`. Only `etc/sensors/` was read: **37 files / 62,297 bytes**.
Normal unmount/detach/rmdir succeeded before archive publication. A subsequent
same-boot read confirmed ADSP offline and no remaining temporary mounts.

Every archive member's size, SHA-256 and mtime matches `MANIFEST.json`.
All **35** config JSON inputs named in the previously exported registry cache
are present, with exact cached mtime **1640995200**. The other two files are
stock `sns_reg_config` (virtual path configuration) and Android `hals.conf`.
Proprietary bytes remain in ignored private `out/ssc-vendor-config/`.

## Offline assembly

`userspace/sensors/stage-assets.py` assembles host-only
`out/ssc-assets/sensor-assets.tar.gz`. It verifies both source archives, complete
MDT structure/segments/regions, collection provenance and cleanup, exact config
set/timestamps, completion marker and core sensor libraries. It then reopens
the resulting tar to compare every byte, owner and mtime with its source.
The output contains **328 regular files**, no links, units or installer:

| Destination | Files | Source |
| --- | ---: | --- |
| usr/lib/firmware/qcom/sm8550 | 55 | Stock ADSP MDT/data/domain JSON |
| PREFIX/dsp/adsp | 57 | Stock ADSP libraries, no CDSP activation |
| PREFIX/sensors/registry | 179 | Copied registry groups/cache/completion marker |
| PREFIX/sensors/sns_reg_version | 1 | Stock registry version |
| PREFIX/sensors/config | 35 | Vendor config JSON, original mtimes |
| PREFIX/sensors/sns_reg.conf | 1 | Vendor sns_reg_config mapped by HexagonFS |

`PREFIX=usr/share/qcom/sm8550/Samsung/gts9wifi`. Root-owned archive registry
files use mode 0600; **future deployment must provision the service account and
assign only the copied registry tree**, without touching actual Android persist.
CDSP libraries, Android HAL config, and Android `sensors_list.txt`/
`sensorhubs_list.txt` inventories are not staged. No audio route is enabled.
The output hash and per-member source/bytes/mtime/hashes are in `STAGED.json`.

Thirty-nine affected host tests pass, zero skips: 17 stock archive/MDT tests,
12 LP layout fixtures and 10 assembly/cache/failure tests. Actual source and
output archive verification also passed. No kernel build/full host regression
was executed because no kernel, build, config, DTS or suite routing changed.
Previously qualified ARM64 binaries and four runtime debs are unchanged.

## Remaining integration

Stock `sns_reg_config` points at `/sys/devices/soc0/{hw_platform,
platform_subtype,platform_subtype_id,platform_version,soc_id}`. The checked
stock sysfs path is absent in current Debian (`socinfo.json`). Do not invent
X710 values or import S9 Ultra's identity. HexagonFS has an optional
`PREFIX/socinfo` mapping; qualify the mainline-to-stock identity mapping before
relying on registry regeneration. The cached stock registry is preserved; it
does not establish that fresh discovery/rebuild or rotation succeeds.

Next is runtime integration/controlled **early-boot** registration: finish this
identity mapping, install missing dependencies and packages with activation
inhibited, copied-registry ownership, one-attempt/no-restart units and recovery.
Linux 7.2-rc3's SM8550 ADSP PAS descriptor has `auto_boot=true`; firmware can
be requested asynchronously during driver registration. Explicitly plan the
next boot's firmware availability and text-mode ordering, rather than late
starting ADSP on the active desktop or assuming a firmware copy triggers retry.

**Not deployment ready yet.** TrustZone authentication, FastRPC sensor-PD
attach, SSC discovery, accelerometer readings and GNOME rotation are untested.
No packages/firmware installed, daemons started, persistent files changed,
flash/reboot, charging/PPS/pump/USB/input/kernel/DT/config/module changes.
Test363 pen pressure/button test remains pending owner readiness; no new input
capture was started. Test348 authorization remains unused.
