#!/bin/sh
# Type this at the bring-up console to reboot the tablet into TWRP.
#
# It writes the Android bootloader control block ("boot-recovery") into the
# first bytes of the misc partition and resets.  /init publishes the device path
# after validating it against the GPT, so this cannot write to a partition that
# is not misc.
set -e
dev=$(cat /tmp/gts9-misc-dev 2>/dev/null)
if [ -z "$dev" ] || [ ! -b "$dev" ]; then
    echo "gts9-to-recovery: no validated misc device (is /init past its report stage?)" >&2
    exit 1
fi

dd if=/dev/zero of=/tmp/gts9-bcb.bin bs=2048 count=1 2>/dev/null
printf 'boot-recovery' | dd of=/tmp/gts9-bcb.bin bs=1 seek=0 conv=notrunc 2>/dev/null
dd if=/tmp/gts9-bcb.bin of="$dev" bs=2048 conv=notrunc 2>/dev/null
sync
echo "gts9-to-recovery: BCB written to $dev; rebooting into recovery"
reboot -f
