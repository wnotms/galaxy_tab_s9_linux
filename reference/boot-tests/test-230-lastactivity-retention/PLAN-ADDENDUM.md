# Before-flash transport and retention-path clarification

Recorded before writing the candidate partitions. TWRP identity and all five
partition hashes match the test-229 production state; battery is 85%.
The existing rollback images were copied to dedicated host backup files and
their full hashes verified against the current full partition hashes. This
provides byte-identical backups without rewriting any device partition.

ADB on Debian inherits TMPDIR=/data/local/tmp, which does not exist there.
The initial read-only BCB check failed before any write. Retrying the unchanged
repository helper with TMPDIR=/tmp passed; BCB write/read-back and a plain
systemctl reboot then entered TWRP successfully. Preserve both attempts.

TWRP exposes no saved files under /sys/fs/pstore and no /dev/mem; its inventory
compound command exits 1 on the missing optional /dev/mem. An empty TWRP pstore
is not proof that persistent RAM lost a snapshot, because this recovery kernel
may not expose the mainline backend. Recovery last_kmsg remains bootloader/
recovery evidence, not an attributed mainline snapshot.

Therefore, after the planned snapshot and TWRP capture, restore production and
also inspect /sys/fs/pstore and /var/lib/systemd/pstore in the first subsequent
Debian boot. Only a record containing the exact capture ID and complete matching
marker lines establishes retention through this recovery chain. A journal copy
alone does not establish pstore retention. If neither backend yields matching
contents, report persistence unproven/failed for this path and stop; do not
start a wedge series. Preserve the original live snapshot separately.
