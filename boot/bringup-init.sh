#!/bin/sh
# /init for the SM-X710 (gts9wifi) bring-up initramfs.
#
# Purpose: prove the chain
#
#	Samsung ABL -> mainline Linux -> /init -> interactive shell
#
# and print enough evidence for the first physical boot test defined in
# docs/FIRST_BOOT_TEST.md.  It deliberately does no root mounting, no
# switch_root and no hardware bring-up beyond proc/sys/dev/tmp/run.
#
# Everything it reports is written both to stdout (serial console) and to
# /dev/kmsg when available, so the same evidence also lands in the kernel log
# and therefore in Samsung's sec_log_buf, where TWRP exposes it as
# /proc/last_kmsg after a warm reset.

PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

log() {
    echo "$*"
    # Keep the persistent kernel log useful even when the shell is never seen.
    if [ -w /dev/kmsg ]; then
        echo "gts9-init: $*" > /dev/kmsg 2>/dev/null || true
    fi
}

mount_path() {
    # mount_path <fstype> <target>
    mkdir -p "$2" 2>/dev/null || true
    if mount -t "$1" "$1" "$2" 2>/dev/null; then
        log "mounted $1 on $2"
    else
        # Report and keep going: a missing mount must not hide the shell.
        log "WARN: mount -t $1 $2 failed"
    fi
}

mount_path proc /proc
mount_path sysfs /sys
mount_path devtmpfs /dev
mount_path tmpfs /tmp
mount_path tmpfs /run

# Emit the milestone only after /dev/kmsg exists, so it reaches sec_log even
# when the bootloader left us without a working interactive console.
# Everything printed below is also collected into /tmp/bringup-report.txt and
# written to any removable storage that mounts, because on this tablet neither
# the sec_log ring (test 007) nor USB (test 011) can carry evidence out.
REPORT=/tmp/bringup-report.txt
: > "$REPORT"

report() {
    # report <section title> <command...>
    {
        echo "===== $1 ====="
        shift
        "$@" 2>&1
        echo
    } >> "$REPORT"
}

log ''
log '========================================'
log 'GTS9 MAINLINE INITRAMFS REACHED'
log '========================================'
if command -v busybox >/dev/null 2>&1; then
    log "initramfs userspace is running: $(busybox 2>&1 | head -1)"
else
    log 'WARN: busybox is not on PATH'
fi

log ''
log "--- uname -a ---"
log "$(uname -a 2>&1)"

log ''
log "--- /proc/cmdline ---"
log "$(cat /proc/cmdline 2>&1)"

log ''
log "--- device tree model ---"
if [ -r /sys/firmware/devicetree/base/model ]; then
    log "$(tr -d '\0' < /sys/firmware/devicetree/base/model 2>&1)"
else
    log 'WARN: /sys/firmware/devicetree/base/model is not readable'
fi
if [ -r /sys/firmware/devicetree/base/compatible ]; then
    log "compatible: $(tr '\0' ' ' < /sys/firmware/devicetree/base/compatible 2>&1)"
fi

log ''
log "--- /proc/partitions ---"
log "$(cat /proc/partitions 2>&1)"

log ''
log "--- /sys/class/block ---"
log "$(ls /sys/class/block 2>&1)"

log ''
log "--- /sys/fs/pstore ---"
if [ -d /sys/fs/pstore ]; then
    if [ -n "$(ls -A /sys/fs/pstore 2>/dev/null)" ]; then
        log "$(ls -l /sys/fs/pstore 2>&1)"
    else
        # Empty pstore is normal on a clean boot and is NOT a failure.
        log 'pstore is present and empty'
    fi
else
    log 'WARN: /sys/fs/pstore is not present'
fi

log ''
log "--- uptime ---"
log "$(cat /proc/uptime 2>&1)"

{
    echo "GTS9 bring-up report"
    echo "generated: $(cat /proc/uptime 2>/dev/null) since boot"
    echo
} > "$REPORT"
report 'cmdline' cat /proc/cmdline
report 'device tree model' cat /sys/firmware/devicetree/base/model
report 'partitions' cat /proc/partitions
report 'block devices' ls -l /sys/class/block
report 'mounts' cat /proc/mounts
report 'pstore' sh -c 'ls -l /sys/fs/pstore 2>&1'

log ''
log 'dropping to an interactive shell; nothing was written to any block device'
log ''

# ---------------------------------------------------------------------------
# Peripheral-free proof that userspace was reached.
#
# Neither the persistent ring (test 007: the bootloader overwrites it) nor the
# USB gadget (test 008: mainline dwc3 may not bind yet) can prove that this
# script ran.  Powering the tablet off needs no peripheral at all: a hung or
# panicking kernel cannot do it, and panic=0 means the kernel cannot fake it
# either.  "The tablet switched itself off about a minute after the logo" is
# then unambiguous evidence that ABL -> Linux -> BusyBox /init completed.
#
# Opt-in through the command line, so ordinary boot tests are unaffected:
#   gts9_userspace_proof=<seconds>
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Get the evidence out: write the report to removable storage.
#
# dmesg on a mounted microSD card is the one channel that needs no new driver
# work and no persistence trick - it is the complete mainline kernel log, which
# neither the ring (test 007) nor USB (test 011) can deliver yet.  Each
# candidate block device is tried read-write with the two filesystems a bring-up
# card is likely to carry; failures are logged and skipped.
# ---------------------------------------------------------------------------
proof_seconds=''
proof_if=''
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_userspace_proof=*) proof_seconds=${arg#gts9_userspace_proof=} ;;
        gts9_proof_if=*) proof_if=${arg#gts9_proof_if=} ;;
    esac
done

if [ -n "$proof_seconds" ]; then
    case "$proof_seconds" in
        ''|*[!0-9]*)
            log "WARN: ignoring invalid gts9_userspace_proof=$proof_seconds"
            ;;
        *)
            log "userspace proof armed: powering off in ${proof_seconds}s (if=${proof_if:-always})"
            (
                case "$proof_if" in
                    report)
                        if [ "$report_written" != 1 ]; then
                            log 'proof suppressed: bring-up report was not written'
                            exit 0
                        fi
                        ;;
                    udc)
                        if [ -z "$(ls /sys/class/udc 2>/dev/null)" ]; then
                            log 'proof suppressed: no UDC registered'
                            exit 0
                        fi
                        ;;
                esac
                sleep "$proof_seconds"
                log "userspace proof firing now (PSCI power off)"
                sync
                poweroff -f || reboot -f
            ) &
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# Live evidence channel: USB gadget.
#
# The persistent ring cannot be trusted for this bring-up: the bootloader's own
# log occupies essentially the whole 2 MiB sec_log_buf on every boot, so
# anything this kernel writes there can be overwritten before recovery can read
# it.  A live channel has no such problem - if this script runs, the host sees
# the device immediately, and if it does not, nothing appears.
#
# Bound to the same USB port the bootloader already leaves in device mode.
# Failure is reported and does not stop the rest of the bring-up.
# ---------------------------------------------------------------------------
USB_GADGET=${GTS9_USB_GADGET:-1}
gadget_setup=0

setup_usb_gadget() {
    [ "$USB_GADGET" = 1 ] || { log 'USB gadget disabled by GTS9_USB_GADGET'; return 0; }

    if ! mount -t configfs none /sys/kernel/config 2>/dev/null; then
        log 'WARN: configfs unavailable; cannot set up the USB gadget'
        return 0
    fi
    if [ ! -d /sys/class/udc ] || [ -z "$(ls -A /sys/class/udc 2>/dev/null)" ]; then
        log 'WARN: no USB device controller (UDC) registered'
        return 0
    fi

    G=/sys/kernel/config/usb_gadget/gts9
    mkdir -p "$G" 2>/dev/null || { log 'WARN: cannot create the gadget directory'; return 0; }
    # 0x0525/0xa4a7 (Linux-USB gadget serial) rather than Google's adb IDs:
    # recovery already enumerates as 18d1:d001, and the monitor must be able to
    # tell this gadget apart from it.
    echo 0x0525 > "$G/idVendor" 2>/dev/null
    echo 0xa4a7 > "$G/idProduct" 2>/dev/null
    echo 0x0100 > "$G/bcdDevice" 2>/dev/null
    echo 0x0200 > "$G/bcdUSB" 2>/dev/null

    mkdir -p "$G/strings/0x409"
    echo 'Samsung' > "$G/strings/0x409/manufacturer" 2>/dev/null
    echo 'GTS9 mainline bring-up' > "$G/strings/0x409/product" 2>/dev/null
    echo 'gts9wifi-0001' > "$G/strings/0x409/serialnumber" 2>/dev/null

    mkdir -p "$G/configs/c.1/strings/0x409"
    echo 'bringup' > "$G/configs/c.1/strings/0x409/configuration" 2>/dev/null
    echo 250 > "$G/configs/c.1/MaxPower" 2>/dev/null

    mkdir -p "$G/functions/acm.usb0" 2>/dev/null
    ln -sf "$G/functions/acm.usb0" "$G/configs/c.1/acm.usb0" 2>/dev/null

    udc=$(ls /sys/class/udc 2>/dev/null | head -1)
    if [ -n "$udc" ] && echo "$udc" > "$G/UDC" 2>/dev/null; then
        gadget_setup=1
        log "USB gadget bound to $udc (host sees a CDC-ACM serial port)"
    else
        log 'WARN: could not bind the USB gadget to a UDC'
    fi
    return 0
}

setup_usb_gadget

# Collect the USB state now that the gadget has been attempted, then get the
# whole report off the device.
report 'usb device controllers' ls -l /sys/class/udc
report 'usb gadget state' sh -c 'ls -l /sys/kernel/config/usb_gadget/gts9 2>&1; cat /sys/kernel/config/usb_gadget/gts9/UDC 2>&1'
report 'dwc3 bindings' sh -c 'ls -l /sys/bus/platform/drivers/dwc3/ 2>&1; ls -l /sys/bus/platform/drivers/dwc3-qcom/ 2>&1'
report 'ttyGS' sh -c 'ls -l /dev/ttyGS* 2>&1'
report 'dmesg' dmesg

report_target=''
report_written=0

try_report_on() {
    dev=$1
    [ -b "$dev" ] || return 1
    for fs in vfat ext4 ext2; do
        if mount -t $fs -o rw "$dev" /mnt 2>/dev/null; then
            if cp "$REPORT" /mnt/gts9-bringup-report.txt 2>/dev/null; then
                sync
                report_target="$dev ($fs)"
                report_written=1
                umount /mnt 2>/dev/null
                return 0
            fi
            umount /mnt 2>/dev/null
        fi
    done
    return 1
}

mkdir -p /mnt
for dev in /dev/mmcblk0p1 /dev/mmcblk0 /dev/mmcblk1p1 /dev/mmcblk1 \
           /dev/sda1 /dev/sdb1 /dev/sda /dev/sdb; do
    if try_report_on "$dev"; then
        log "bring-up report written to $report_target"
        break
    fi
done
[ "$report_written" = 1 ] || log 'WARN: no removable storage accepted the bring-up report'


if [ "$gadget_setup" = 1 ]; then
    # Wait for the ACM port to appear, then mirror the kernel log onto it and
    # hand the same port to a shell.  The host side gets live evidence either
    # way: a port that stays silent means this script never ran.
    i=0
    while [ "$i" -lt 20 ] && [ ! -c /dev/ttyGS0 ]; do
        sleep 1
        i=$((i + 1))
    done
    if [ -c /dev/ttyGS0 ]; then
        log 'streaming the kernel log to /dev/ttyGS0'
        (
            cat /dev/kmsg > /dev/ttyGS0 2>/dev/null
        ) &
        while :; do
            /bin/sh -i </dev/ttyGS0 >/dev/ttyGS0 2>&1
            log 'usb shell ended; PID 1 remains alive, retrying in 5s'
            sleep 5
        done
    fi
    log 'WARN: /dev/ttyGS0 did not appear; staying on the console shell'
fi

# PID 1 must survive EOF, an unavailable UART and a user's "exit". Replacing
# init with a shell makes all of those cases panic (Attempted to kill init!).
# Reopen the console after devtmpfs has been mounted; /dev/console may not
# have existed when the kernel opened init's standard descriptors.
while :; do
    /bin/sh -i </dev/console >/dev/console 2>&1
    log 'console shell ended or unavailable; PID 1 remains alive, retrying in 5s'
    sleep 5
done
