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
