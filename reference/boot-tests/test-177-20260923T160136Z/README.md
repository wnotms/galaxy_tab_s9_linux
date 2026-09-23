# Test 177 — minimal rootfs handoff profile

**Status:** candidate flashed and read-back verified; Type-C A boot pending.

The goal is to test the opt-in minimal initramfs on the same physical kernel and
DTB, first with Type-C connected and then battery-only. Type-C is the only
intended variable between those boots.

## Candidate and write scope

Source commit: `a3adc529a53a8b92d8ff113c1b82055973cb71ac`.
The candidate passed `scripts/validate-boot-bundle.sh` with
`boot/cmdline.minimal-rootfs.example.txt`.

Planned writes are exactly:

- `init_boot`: minimal rootfs initramfs, SHA-256 `4515b081f58e5c630a6ad49dfb7a64ca937c977267227375280235147d462baa`.
- `vendor_boot`: `gts9_minimal_rootfs=1` cmdline and matching DTB, SHA-256 `740bbd6392c13dec5999a6b75800b05462965fc67d25b58744c9469c2596f900`.

Do not flash `boot`, `dtbo`, or `vbmeta`. The candidate bundle's `boot.img`
uses a newer local kernel payload, while the current physical test-173 kernel
is known to be `822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86`.
The candidate and test-173 DTB hashes both equal
`f49b373462a278fcafb858fa9f59dac174d88b4f14810ad2638509d9c2e9e9be`.
Test-173's recorded `vendor_boot` hash is
`09bd4bea84d5a0477652002f6e4cd66091b4536f1cd7eb3d5d1a5bf45b2eb61b`. Fresh
backups were read from the device before writing and match the recorded
partition hashes. Both intended partition writes were read back and match the
candidate SHA-256 values. Post-write hashes confirm `boot`, `dtbo`, and
`vbmeta` remain unchanged. See `current-partition-backups.txt`,
`flash-write-readback.txt`, and `postwrite-partition-hashes.txt`.

## Baseline evidence

The owner reports Type-C attached and Debian running. A live read-only serial
audit confirmed `/dev/mmcblk1p1` as ext4 `/`, Linux
`7.2.0-rc3-gts9wifi-dirty`, and `serial-getty@ttyGS0` active. The running
cmdline did not contain `gts9_minimal_rootfs=1`. The documented Debian recovery
helper's `--check` found `/dev/sda10` labelled `misc` with 2048 sectors and an
empty BCB; it made no changes. The helper then set the one-shot recovery
request to enter TWRP. TWRP was visible to the owner and enumerated in Windows
ADB as SM-X710/gts9wifi; WSL's earlier ADB wait timed out because the recovery
ADB interface was on Windows. TWRP's post-flash read found the first 32 bytes
of `misc` zero, so no BCB cleanup write was needed.

## Type-C A test

The device remains connected to Type-C. Candidate `init_boot` and `vendor_boot`
are installed; no other boot-chain partitions were written. Reboot to system
was initiated at 2026-09-23T16:16:00Z. The owner reports a black screen and no
apparent response. Windows ADB and WSL ACM did not reappear in the first
follow-up checks. This does not establish a rootfs failure because the minimal
profile omits initramfs display and USB gadget setup. The host is waiting to
capture `/proc/last_kmsg` after returning to TWRP; see
`typec-a-observation.txt`.

## Results

Type-C A test: flashed/read-back verified; boot result pending.
Battery-only B test: pending; it must use the same flashed images and cmdline.
No conclusion about rootfs cold-boot behavior is available until both tests
record their final stage, `/dev/mmcblk1p1`, switch-root, and Debian/systemd state.
