# Isolated registry mutation evidence — host qualified

The new read-only helper captures bounded before/after copies of the registered
sensor prefix and replays acknowledged apps_std file operations through the
unchanged qualified listener2 frame parser. It does not access Android persist,
extract/install assets, start a service or touch charging/USB/DSP control.
No historical parser, runner or test was changed.

Snapshots require the exact Debian machine/boot, fixed isolated prefix and both
owned RPC producers inactive before and after collection. Files must be regular,
not symlinks or cross-filesystem mounts, with no executable/special modes. Each
opened inode/size/mtime/ctime must agree before/after the bounded read. Limits are
128KiB/file, 2MiB total and 2048 files. Returned data includes bytes/hash/mode/
owner/mtime and the phase; replay requires the full before set to match its
independently qualified archive manifest. Host fixture seams are not physical
snapshot qualification.

Mappings follow the current Fedora rpcd_builder.c exactly: two persist aliases
map into the copied sensor tree; the virtual `/vendor/etc/sensors/sns_reg_config`
maps to **sns_reg.conf**, not the cached registry/sns_reg_config group. Config
and /system/vendor aliases are handled explicitly. Writes are permitted only
from the sensor unit into copied registry leaves or sns_reg_version; config/
identity/library writes and unmodelled methods are rejected. This is evidence
validation, not a newly installed hardware/daemon write restriction.

The byte replay tracks truncate/read/write/append/seek/close and extended method33
rename, including open-inode identity when a file is replaced. Replies must fit
the requested capacities; counts, status and host transport acknowledgement are
checked. Short/failed/unattributed writes, unexpected metadata/ownership, unclosed
mutable descriptors or unexplained final content stop. Reads are compared with
the actual replayed current bytes, rather than an obsolete pre-write manifest.
New final files must be explained by the complete recorded operations.

Actual Test400 frames replay the qualified original sensor input bytes with no
write. This uses archive-derived host snapshots, **not recovered physical
before/after snapshots from Test400**. One read-only bootstrap descriptor remains
open at the journal boundary. It is reported as such, without an invented close;
the future after snapshot must be taken after both producers stop. A retained
mutable descriptor still stops, and incomplete read coverage is not a DSP parse
or SSC acceptance claim.

33 tests passed, zero failures/errors/skips. Five compile the exact current
Fedora apps_std/HexagonFS C files with UBSan and run real private-file write,
append, rename, short-input rejection and readonly-descriptor rejection. Other
cases cover generated reads, replacement inode behavior, aliases, seek, missing/
corrupt/foreign snapshots, capacity/status/transport failures, unknown methods,
descriptor reuse, symlink and producer gates, plus the actual Test400 journal.
No UBSan diagnostic. Two initial failed assumptions are retained separately:
the real archive has179 files mode0600 rather than0644; and the bootstrap reader
is intentionally retained until process exit. Corrections do not bypass current
archive mode, producer-quiescence or mutable-close requirements.

Syntax passed. No kernel/DT/config/module/daemon/library mutation or build,
full regression, routing change, Actions, device command or physical snapshot
collection. This component alone is not a registered Test401. Next integrate
before capture after preparation but before RPC start, and after capture after
the single registered observation and deactivation. Preserve raw callback frames,
the first anomaly and both snapshots before restoring the normal desktop. Any
future generated calibration content stays in the isolated test copy; it is not
adopted over factory persist. SSC400, accelerometer and physical rotation remain
separate required acceptance evidence. PPS/pump/DCC OFF.
