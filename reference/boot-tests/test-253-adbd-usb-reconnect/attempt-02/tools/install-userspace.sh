#!/bin/sh
# Run through SSH only after pushed registration and accepted read-only preflight.
set -eu
stage=/var/lib/gts9/test253-adbd-reconnect
[ "$(cat /proc/sys/kernel/random/boot_id)" = fcb9a367-fa8e-43df-afb1-08db722ff2f1 ]
[ "$(systemctl show -p MainPID --value gts9-adbd.service)" = 838 ]
[ "$(cat /sys/kernel/config/usb_gadget/gts9/UDC)" = a600000.usb ]
[ ! -e /usr/local/libexec/gts9-adbd-reconnect ]
[ ! -e /usr/libexec/gts9-adbd-run ]
[ ! -e "$stage/original" ]
printf '%s\n' '9035c0d9e5253d4ca9582ae80db91ae8867d20e80e24e46b104304e39dcd9de3  /usr/lib/systemd/system/gts9-adbd.service' '3dee0a5b423dc76d8c1751d88e30ee5f7052f8cdff37dd64dac4956651631ad3  /usr/lib/android-sdk/platform-tools/adbd' '053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5  /var/lib/gts9/test253-adbd-reconnect/gts9-adbd-reconnect' 'd2e840b5ef9723cde15da7a889a79d0700a5d54aabd54873c8b602694a0dedc3  /var/lib/gts9/test253-adbd-reconnect/gts9-adbd-run' '52e80912b62c06a5677f8a7da1ea3a19b65b7627f306c9c66a9b934ba48a499b  /var/lib/gts9/test253-adbd-reconnect/gts9-adbd.service' | sha256sum --check
/lib/ld-linux-aarch64.so.1 --list "$stage/gts9-adbd-reconnect"
"$stage/gts9-adbd-reconnect" --version
mkdir -m 700 "$stage/original"
cp -a /usr/lib/systemd/system/gts9-adbd.service "$stage/original/gts9-adbd.service"
printf '%s\n' '9035c0d9e5253d4ca9582ae80db91ae8867d20e80e24e46b104304e39dcd9de3  /var/lib/gts9/test253-adbd-reconnect/original/gts9-adbd.service' | sha256sum --check
printf '%s\n' 'launcher and custom daemon originally absent' > "$stage/original/absence.txt"
install -D -m 755 "$stage/gts9-adbd-reconnect" /usr/local/libexec/gts9-adbd-reconnect
install -D -m 755 "$stage/gts9-adbd-run" /usr/libexec/gts9-adbd-run
install -m 644 "$stage/gts9-adbd.service" /usr/lib/systemd/system/gts9-adbd.service
printf '%s\n' '053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5  /usr/local/libexec/gts9-adbd-reconnect' 'd2e840b5ef9723cde15da7a889a79d0700a5d54aabd54873c8b602694a0dedc3  /usr/libexec/gts9-adbd-run' '52e80912b62c06a5677f8a7da1ea3a19b65b7627f306c9c66a9b934ba48a499b  /usr/lib/systemd/system/gts9-adbd.service' | sha256sum --check
[ "$(systemctl show -p MainPID --value gts9-adbd.service)" = 838 ]
[ "$(readlink /proc/838/exe)" = /usr/lib/android-sdk/platform-tools/adbd ]
[ "$(cat /sys/kernel/config/usb_gadget/gts9/UDC)" = a600000.usb ]
sync
printf 'staged for next ordinary boot; live daemon and shared UDC unchanged\n'
cat /proc/sys/kernel/random/boot_id
