# Remaining Fedora X710 sensor input differences after Test400

Fedora remote HEAD was checked again and remains
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`. The comparison reads the exact
qualified release archive30cace40 and current asset archive6abc10ec without
extraction or device operations. `COMPARISON.json` records file identities,
metadata, exact JSON leaf changes and unparseable vendor JSON differences.

All 35 sensor config files have identical bytes. `sns_reg.conf` and
`sns_reg_version` also match. The five DSP sensor libraries present in the
Fedora package match the current copies. Differences in the common device
prefix are 148 equal files, 35 byte-different files and 95 member-set
differences. The latter include extra current audio libraries/gyro cache
groups and five Fedora reference SoC files; they are not 95 missing fixes.

The complete config-mtime cache differs: every current cached value is
1640995200 and equals its archived config mtime; all 35 Fedora cached values
are0 while its archived config mtimes are1786379433. This is an actual published
input difference, not a measured firmware decision or demonstrated root cause.
Test400 kept the current cache when substituting firmware. Its immutable unit
journal logs 35 config stat callbacks and one directory open, but no config-file
open among the 36 messages containing that virtual config path. The raw source
hash and exact messages are retained in `CONFIG_ACCESS.json`. This does not
prove what the DSP internally parsed or exclude unlogged operations.

Other registry differences include factory bias/correction matrices, placement,
volatile calibration and algorithm data. They are reported separately and must
not be treated as safe whole-package replacements for this tablet's calibration.
Nonstandard vendor JSON is not silently repaired. Numeric strings and version
fields retain their exact representation; formatting equality is reported only
when strict JSON objects themselves match.

Fedora's packaged platform_version is0. The current measured native SMEM value
is65536, exposed as the raw decimal value by Samsung's own socinfo getter.
Changing it to0 would substitute a reference fixture for device identity;
it is not a confirmed mapper fix. Keep the measured mapping.

The next controlled input question can isolate the published mtime-cache
difference instead of copying calibration, deleting the whole registry or
changing identity. Before any deployment, qualify a separate profile that
changes only the copied sns_reg_config mtime fields, retains all other input
bytes/metadata, leaves physical persist untouched, and records any regenerated
isolated files. A new observation must distinguish config read/reparse evidence
from actual SSC400 publication and accelerometer samples. Existing immutable
cache callback expectations cannot simply be reused if firmware writes new
cache content; adapt evidence collection and host tests before registering.
No such profile, registration or physical test was created in this step.

32 affected tests passed with zero failures/errors/skips (16 new input-comparison
tests and 16 unchanged firmware-profile tests); syntax checks passed. Input
immutability, duplicate/nonfinite JSON, missing config/markers, cache coverage,
malformed timestamp and foreign calibration/identity distinctions are tested.
No kernel build, full regression, routing change, Actions, device command,
registry reset, firmware write or charging change. Normal370/GNOME remains
the Test400 restored endpoint; PPS/pump/DCC OFF. Sensors/rotation unfinished.
