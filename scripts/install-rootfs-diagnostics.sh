#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
target=${1:?usage: install-rootfs-diagnostics.sh DEBIAN_ROOTFS_MOUNTPOINT}

[ -d "$target/etc/systemd" ] || {
	echo "not a Debian root filesystem: $target" >&2
	exit 1
}

overlay="$repo_root/rootfs-overlay"
install -D -m 0644 \
	"$overlay/etc/systemd/logind.conf.d/60-gts9-power-key.conf" \
	"$target/etc/systemd/logind.conf.d/60-gts9-power-key.conf"

# The USB network function's configuration.  Without it gts9-usb-acm creates the
# gadget with its ACM ports alone and no ncm.usb0, so there is no link to ssh
# over - and since 2026-09-26 ssh is the only way into this tablet: both serial
# debug consoles were removed (docs/BOOT_CONSOLE_BLOCK.md, docs/SHUTDOWN_DELAY.md).
# This installer copies the gadget's helper and unit, so it has to copy the file
# that makes them useful too; leaving it out yielded a debug link that carried no
# traffic at all.
install -D -m 0644 \
	"$overlay/etc/gts9-usb-net" \
	"$target/etc/gts9-usb-net"

for file in "$overlay"/usr/lib/systemd/system/gts9-*.service; do
	install -D -m 0644 "$file" "$target/usr/lib/systemd/system/${file##*/}"
done

for file in "$overlay"/usr/libexec/gts9-*; do
	install -D -m 0755 "$file" "$target/usr/libexec/${file##*/}"
done

systemctl --root="$target" enable \
	gts9-boot-stage.service \
	gts9-getty-stage.service \
	gts9-poweroff-stage.service
