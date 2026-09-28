#!/bin/sh
# Restore only verified Test253-created userspace files for the next boot.
# Never restart adbd or the shared gadget here.
set -eu
backup=/var/lib/gts9/test253-adbd-reconnect/original/gts9-adbd.service
printf '%s  %s\n' '9035c0d9e5253d4ca9582ae80db91ae8867d20e80e24e46b104304e39dcd9de3' "$backup" | sha256sum --check
printf '%s\n' '053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5  /usr/local/libexec/gts9-adbd-reconnect' 'd2e840b5ef9723cde15da7a889a79d0700a5d54aabd54873c8b602694a0dedc3  /usr/libexec/gts9-adbd-run' | sha256sum --check
install -m 644 "$backup" /usr/lib/systemd/system/gts9-adbd.service
rm /usr/local/libexec/gts9-adbd-reconnect /usr/libexec/gts9-adbd-run
sync
printf 'original userspace restored for next ordinary boot only\n'
