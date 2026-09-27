# Test 233: known binary pmsg payload across a direct healthy reboot

Owner request (2026-09-27): “继续解决cpu卡死问题”. Current boot
 a80804be-229c-46f7-aae8-bd797fb22883 is responsive after more than 900 seconds.
Production kernel/config/cmdline/ramoops geometry remain unchanged; ECC=0,
mem_type=0, pmsg_size=1048576. Native USB ADB and NCM/SSH remain installed.

Question: does a known 32 KiB binary record reach the next boot's pmsg pstore
with exact bytes? Test-183 reported absent pmsg; test-231 now supplies new
positive evidence of retained but corrupt console text. This calibration
quantifies absence, corruption and exact retention separately on the current
stack. It is not a wedge series or a CPU fix.

Generate a fresh UUID/boot-ID framed payload with SHA-256 before writing. It
contains zero/ones/alternating and deterministic hash-derived bytes. Push to
/tmp, verify device hash, then perform one bounded write to /dev/pmsg0. Emit
only a small tagged /dev/kmsg marker. Preserve baseline pstore hashes/logs,
check current health, issue ordinary systemctl reboot directly into Debian.
No TWRP is planned between write and read, no panic is induced, no watchdog,
partition, kernel, rootfs service or memory-map changes are made.

Recover pstore from /sys/fs/pstore and /var/lib/systemd/pstore as raw bytes.
Require a fresh capture identity, complete exact payload and matching host and
device hashes; compare independently repeated reads if corruption appears.
Archive boot list and observer identity. No payload match means inconclusive
loss/absence, never a repaired trace. Stop if the observer has a positive wedge
or becomes inaccessible. A normal-reboot pass does not establish crash retention.
