# Fedora config-mtime cache comparison profile — offline only

The new profile uses the complete Test400 Fedora ADSP pair and changes one
copied input: `sensors/registry/sns_reg_config`. Its 35 cached mtime `data`
fields become0, exactly the values observed in the pinned Fedora release.
Owner/type/version fields stay unchanged. The other 327 files retain exact
bytes, mode and mtime. All 35 config files, the device's factory calibration,
registry/version markers, DSP libraries, firmware and PD maps are preserved.
The changed cache file also retains its baseline mode and mtime.

This isolates a published input difference; it is not a blanket Fedora registry
copy or a demonstrated SSC fix. It does not modify the actual persist partition
or measured native SoC identity. No device access, kernel/DT/module/charging/USB
change or firmware deployment occurred. The matched Test400 vendor is reusable
because none of its firmware/early-boot inputs changed; no new image was built.

`PROFILE.json` binds all 328 output members and the one-file/35-field diff.
The archive was reopened and every byte/mode/mtime compared with the planned
result. Hash-verified source archives, no duplicate/new member set, strict cache
schema, exact shared config bytes, current cache matching and Fedora-zero
reference boundary precede output creation. An already modified cache, differing
reference config, bad archive hash or occupied output is rejected.

24 affected tests passed with no failures/errors/skips: eight new real-profile
tests and 16 input-comparison tests. They check input immutability, all unchanged
members, metadata, archive round-trip, refusal to restage/reinterpret a changed
baseline, missing members, nonzero reference fields and pre-output hash failure.
Syntax passed. The preceding firmware-profile qualification is unchanged.
No full test run, kernel build, routing edit or GitHub Actions.

**NOT DEPLOYMENT READY.** Before independently registering a physical follow-up,
qualify collection of firmware-generated files and write/rename callbacks in
the isolated registry. Immutable Test400 cached-content expectations must not
classify an intentional generated cache as corruption or ignore an actual
callback fault. Preserve original files, before/after hashes, callback frames,
transport/status/framing checks, and reject unexplained writes outside the
isolated asset prefix. Do not extend this to physical persist access.

A follow-up must use one attributed startup, report actual config opens/reads
and writes separately from SSC400/sample acceptance, and restore exact370/
original rootfs absence/normal GNOME on either outcome. No repeated unchanged
Test400 boot or automatic registry reset on the running desktop. The profile
has an explicit pending comparison consumer, no Windows stage and no extra
boot image. Existing Test391–Test400 retention applies. PPS/pump/DCC remain OFF;
sensor bring-up and automatic rotation are still unfinished.
