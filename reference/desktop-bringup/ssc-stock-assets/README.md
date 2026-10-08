# Read-only stock sensor asset staging registration

Purpose: collect the owner's X710 stock ADSP firmware, DSP libraries and sensor
registry/configuration into private host staging for the Fedora-derived SSC port.
This does not start or install an ADSP/sensor runtime.

Entry: confirmed `samsung,gts9wifi`, the observed Test331 boot
`28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af`, ADSP offline, authenticated Wi-Fi SSH.
Observed stock layout is apnhlos/sda17/vfat, dsp/sda16/ext4 and persist/sda5/ext4;
recheck filesystem types before every temporary mount. Refuse existing source
mounts. Temporary mounts are confined to an owned `/run/gts9-ssc-stock-*` tree,
all `ro,nosuid,nodev,noexec`; ext4 also uses `noload`. Verify effective read-only
flags and unmount/rmdir on exit. No recursive removal or forced unmount.

Scope: apnhlos files beginning `adsp`, regular files from the DSP library
partition, and **only sensors/** from persist. Skip/report symlinks. No other
persist data, Android app data, firmware writes or permission changes. Bound
the export to 192 MiB/8192 files and any individual file to 64 MiB. Output is
a streaming archive with per-file hashes, original mtimes, mount evidence and
boot attribution. Host data stays under ignored `out/ssc-stock-assets`, mode
0700/0600; proprietary firmware and device calibration contents stay out of Git.

Stop on identity, filesystem, mount/cleanup, read, transport, size or boot-state
failure. Retain partial host output without retrying or enabling a DSP. Success
requires host verification of every archive member against the manifest and no
remaining temporary mounts. A missing/invalid manifest is not an accepted export.

No `/lib/firmware` installation, real-persist access by hexagonrpcd, daemon start,
package install, remoteproc start, kernel/DT/config/input/USB/charging change,
flash or reboot. Rollback needs no image deployment because this is read-only
source collection. Later activation requires a separate early-boot registration,
bounded observation, Test331 rescue and a private writable registry copy.
