#!/bin/sh
# Run on Debian as root after transferring the verified ARM64 binary.
# No kernel, service, charging setting, or packaged /usr/bin/acpi is changed.
set -eu
binary=${1:?usage: install-local.sh BINARY SHA256}
expected=${2:?usage: install-local.sh BINARY SHA256}
case "$expected" in *[!0-9a-f]*|'') echo 'invalid SHA256' >&2; exit 1;; esac
test "${#expected}" -eq 64
printf '%s  %s\n' "$expected" "$binary" | sha256sum -c -
destination=/usr/local/bin/acpi
if test -e "$destination" || test -L "$destination"; then
    echo 'Existing local acpi retained; refusing to overwrite it.' >&2
    exit 1
fi
temporary=$(mktemp /usr/local/bin/.acpi-gts9.XXXXXX)
trap 'rm -f "$temporary"' EXIT HUP INT TERM
install -m 0755 "$binary" "$temporary"
# Link atomically without clobbering an existing destination in a race.
ln "$temporary" "$destination"
"$destination" -b
