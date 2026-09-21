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
# debugfs carries the two things this bring-up has to read: the deferred-probe
# list (why a device never appeared) and the regulator/clock summaries.
mount_path debugfs /sys/kernel/debug

block_size() {
    bs=$(cat "/sys/class/block/$(basename "$1")/queue/logical_block_size" 2>/dev/null)
    case "$bs" in ''|*[!0-9]*) bs=512 ;; esac
    echo "$bs"
}

gpt_entries() {
    # gpt_entries <disk> -> "<index> <start_lba> <sectors> <bytes> <name>" for
    # every named GPT entry, or nothing when the disk carries no readable GPT.
    dev=$1
    [ -b "$dev" ] || return 1
    ss=$(block_size "$dev")

    # GPT header is LBA 1; the fields used here are PartitionEntryLBA (72),
    # NumberOfPartitionEntries (80) and SizeOfPartitionEntry (84).
    hdr=$(timeout 10 dd if="$dev" bs="$ss" skip=1 count=1 2>/dev/null | head -c 92 | \
          od -An -v -tu1 | tr '\n' ' ')
    [ -n "$hdr" ] || return 1
    sig=$(echo "$hdr" | awk '{printf "%s%s%s%s%s%s%s%s", $1, $2, $3, $4, $5, $6, $7, $8}')
    [ "$sig" = 6970733280658284 ] || return 1              # "EFI PART"
    elba=$(echo "$hdr" | awk '{print $73 + 256*$74 + 65536*$75 + 16777216*$76 + 4294967296*($77 + 256*$78 + 65536*$79 + 16777216*$80)}')
    nent=$(echo "$hdr" | awk '{print $81 + 256*$82 + 65536*$83 + 16777216*$84}')
    esz=$(echo "$hdr" | awk '{print $85 + 256*$86 + 65536*$87 + 16777216*$88}')
    case "$nent$esz$elba" in ''|*[!0-9]*) return 1 ;; esac
    [ "$nent" -ge 1 ] && [ "$nent" -le 1024 ] || return 1
    [ "$esz" -ge 128 ] && [ "$esz" -le 4096 ] || return 1
    [ "$elba" -ge 2 ] && [ "$elba" -le 4096 ] || return 1

    timeout 20 dd if="$dev" bs="$ss" skip="$elba" count=$(( (nent * esz + ss - 1) / ss )) 2>/dev/null | \
        head -c $((nent * esz)) | od -An -v -tu1 | tr '\n' ' ' | \
    awk -v nent="$nent" -v esz="$esz" -v ss="$ss" '
        { for (i = 1; i <= NF; i++) b[i - 1] = $i }
        END {
            for (e = 0; e < nent; e++) {
                o = e * esz
                s = b[o+32] + 256*b[o+33] + 65536*b[o+34] + 16777216*b[o+35]
                n = b[o+40] + 256*b[o+41] + 65536*b[o+42] + 16777216*b[o+43]
                if (s == 0 || n < s) continue
                esc = ""
                for (j = 0; j < 36; j++) {
                    lo = b[o+56+2*j]; hi = b[o+56+2*j+1]
                    if (lo == 0 && hi == 0) break
                    if (hi != 0 || lo < 32 || lo > 126) { esc = ""; break }
                    esc = esc sprintf("\\%03o", lo)
                }
                if (esc == "") continue
                printf "%d %d %d %d %s\n", e, s, n - s + 1, (n - s + 1) * ss, esc
            }
        }' | while read -r index start sectors nbytes esc; do
            # Names are UTF-16LE; only the ASCII subset reaches this point, so
            # octal escapes are enough to get them back.
            printf '%d %d %d %d %s\n' "$index" "$start" "$sectors" "$nbytes" \
                   "$(printf '%b' "$esc")"
        done
}

gpt_labelled_device() {
    # gpt_labelled_device <label> -> the partition device for a GPT-labelled
    # partition, and only when the kernel's own start/size agree with the GPT.
    # A wrong device here would mean writing a bootloader control block into
    # somebody else's partition, so this fails closed like the report does.
    want=$1
    for disk in /dev/sd?; do
        [ -b "$disk" ] || continue
        ss=$(block_size "$disk")
        entries=$(gpt_entries "$disk" 2>/dev/null)
        [ -n "$entries" ] || continue
        match=$(echo "$entries" | awk -v name="$want" '$5 == name { print; exit }')
        [ -n "$match" ] || continue
        set -- $match
        index=$1; start=$2; nbytes=$4
        pdev="${disk}$((index + 1))"
        pbase=$(basename "$pdev")
        [ -b "$pdev" ] || continue
        kstart=$(cat "/sys/class/block/$pbase/start" 2>/dev/null)
        ksize=$(cat "/sys/class/block/$pbase/size" 2>/dev/null)
        case "$kstart$ksize" in ''|*[!0-9]*) continue ;; esac
        if [ "$((kstart * 512))" != "$((start * ss))" ] || [ "$((ksize * 512))" != "$nbytes" ]; then
            log "WARN: GPT and kernel disagree about $pdev ($want)"
            continue
        fi
        echo "$pdev"
        return 0
    done
    return 1
}

# ---------------------------------------------------------------------------
# Automatic reboot into recovery, without a working power button or an owner.
#
# Android's bootloader control block is the standard way to ask a bootloader for
# a boot mode: the first bytes of `misc` hold an ASCII command, and ABL boots
# recovery when it reads "boot-recovery".  That is a *UFS* write, which is why
# it is usable here at all - the SPMI write that reboot(2) RESTART2 performs
# through the SDAM reboot-mode cell blocks this board's kernel (tests 024/025).
#
# One shot only: if the block already asks for recovery and the bootloader
# ignored it, /init powers the tablet off instead of resetting it again, so a
# failed experiment ends rather than looping.
# ---------------------------------------------------------------------------
BCB_LABEL=misc

bcb_asks_recovery() {
    pdev=$(gpt_labelled_device "$BCB_LABEL" 2>/dev/null) || return 1
    head=$(timeout 5 dd if="$pdev" bs=1 count=16 2>/dev/null | tr -d '\0')
    [ "$head" = boot-recovery ]
}

write_bcb_recovery() {
    pdev=$(gpt_labelled_device "$BCB_LABEL" 2>/dev/null) || {
        log "WARN: no $BCB_LABEL partition found for the BCB"
        return 1
    }
    dd if=/dev/zero of=/tmp/gts9-bcb.bin bs=2048 count=1 2>/dev/null || return 1
    printf 'boot-recovery' | dd of=/tmp/gts9-bcb.bin bs=1 seek=0 conv=notrunc 2>/dev/null || return 1
    timeout 30 dd if=/tmp/gts9-bcb.bin of="$pdev" bs=2048 seek=0 conv=notrunc 2>/dev/null || {
        log "WARN: could not write the BCB to $pdev"
        return 1
    }
    sync
    log "BCB written to $pdev ($BCB_LABEL): command=boot-recovery"
    return 0
}

# The console helper needs the same validated device, so publish it.
publish_misc_device() {
    pdev=$(gpt_labelled_device "$BCB_LABEL" 2>/dev/null) || {
        log "WARN: no validated $BCB_LABEL device; the console helper cannot reboot to recovery"
        return 1
    }
    echo "$pdev" > /tmp/gts9-misc-dev
    log "console helper: gts9-to-recovery will write the BCB to $pdev"
    return 0
}
reboot_to_recovery() {
    # Write the BCB and reset, or power off if the bootloader already ignored a
    # recovery request: either way this ends the boot instead of looping.
    if bcb_asks_recovery; then
        log 'WARN: misc already asks for recovery and the bootloader did not act on it; powering off instead of looping'
        poweroff -f || reboot -f
        return
    fi
    write_bcb_recovery || log 'WARN: the BCB write failed; falling back to a plain reset'
    sync
    reboot -f
}



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
# acm (default), msc (mass storage), both - settable from the command line so a
# boot can switch the gadget without rebuilding the initramfs.
USB_GADGET_MODE=${GTS9_USB_GADGET_MODE:-acm}
# What /init does with /dev/ttyGS0:
#   shell  - stream the kernel log and hand the port to a shell (the console)
#   marker - write a few known lines once and record everything the host sends
#            into gts9-serial-in.txt on the card, which makes both directions of
#            the link measurable through the mass-storage channel
USB_CONSOLE_MODE=${GTS9_USB_CONSOLE_MODE:-shell}
# Seconds to leave the gadget alone before collecting the report, so a host can
# talk to it first (used by the serial probe).
USB_WAIT=${GTS9_USB_WAIT:-0}
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_usb_gadget=*) USB_GADGET_MODE=${arg#gts9_usb_gadget=} ;;
        gts9_usb_console=*) USB_CONSOLE_MODE=${arg#gts9_usb_console=} ;;
        gts9_usb_wait=*) USB_WAIT=${arg#gts9_usb_wait=} ;;
    esac
done
gadget_setup=0
# Exported read-only to the host when the mass-storage function is in use.
USB_MSC_BACKING=${GTS9_USB_MSC_BACKING:-/dev/mmcblk1p1}

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

    case "$USB_GADGET_MODE" in
        acm|both)
            mkdir -p "$G/functions/acm.usb0" 2>/dev/null
            ln -sf "$G/functions/acm.usb0" "$G/configs/c.1/acm.usb0" 2>/dev/null
            ;;
    esac
    case "$USB_GADGET_MODE" in
        msc|both)
            # Mass storage, read-only, with no medium to start with: the card is
            # attached later, once the report has been written and the card is
            # unmounted again.  Windows then mounts the card itself, which is the
            # only log channel that needs neither TWRP nor the owner.
            mkdir -p "$G/functions/mass_storage.usb0" 2>/dev/null
            echo 1 > "$G/functions/mass_storage.usb0/lun.0/ro" 2>/dev/null
            echo 0 > "$G/functions/mass_storage.usb0/lun.0/cdrom" 2>/dev/null
            echo 1 > "$G/functions/mass_storage.usb0/lun.0/removable" 2>/dev/null
            ln -sf "$G/functions/mass_storage.usb0" "$G/configs/c.1/mass_storage.usb0" 2>/dev/null
            ;;
    esac

    udc=$(ls /sys/class/udc 2>/dev/null | head -1)
    if [ -n "$udc" ] && echo "$udc" > "$G/UDC" 2>/dev/null; then
        gadget_setup=1
        log "USB gadget bound to $udc (mode=$USB_GADGET_MODE)"
    else
        log 'WARN: could not bind the USB gadget to a UDC'
    fi
    return 0
}

setup_usb_gadget

# The console helper needs the validated misc device, and the GPT can only be
# read once UFS is enumerated - which is why this runs here and not next to the
# helper's definition.
publish_misc_device

# Clear a bootloader control block left over from an earlier recovery request.
#
# The BCB is what sends the tablet back to TWRP, and nothing on this device
# clears it afterwards: TWRP's own cmdline still carried androidboot.boot_recovery=1
# in test 035 after a `gts9-to-recovery` boot.  A stale block therefore drags the
# next boot into recovery too.  Reaching this line already means we are booting
# mainline, so the block has served its purpose either way; clearing it here
# keeps one request to one boot.
clear_stale_bcb() {
    pdev=$(cat /tmp/gts9-misc-dev 2>/dev/null)
    [ -b "$pdev" ] || return 0
    head=$(timeout 5 dd if="$pdev" bs=1 count=16 2>/dev/null | tr -d '\0')
    [ "$head" = boot-recovery ] || return 0
    timeout 10 dd if=/dev/zero of="$pdev" bs=2048 count=1 conv=notrunc 2>/dev/null || {
        log "WARN: could not clear the stale BCB in $pdev"
        return 0
    }
    sync
    log "cleared a stale recovery BCB in $pdev (one request, one boot)"
    return 0
}
clear_stale_bcb

# ---------------------------------------------------------------------------
# Reporting through the RTC.
#
# The PMK8550 RTC is battery backed, is driven by a mainline driver that is
# built in, and busybox can set it, so /init can leave one 16-bit word there
# that survives a power-off.  Now that storage works (test 020) the report
# itself travels on the microSD card, which makes the RTC the fallback channel -
# and it is written *before* the report is collected, so the outcome of the
# write is part of the dmesg that travels with the report.
#
# Opt-in through the command line:  gts9_rtc_report=1
#
# Layout of the 16-bit value written as the RTC time (epoch 1924992000 =
# 2031-01-01T00:00:00Z + code, so the date itself marks the value as ours):
#
#	bits 0-3   microSD stage   bits 4-7   UFS stage
#	bit  8     USB device controller registered
#	bit  9     sdhc_2 in the deferred-probe list
#	bit 10     ufshc in the deferred-probe list
#	bit 11     the report had been persisted when this word was written
#	bits 12-15 checksum: nibble sum of bits 0-11
#
# stage: 0 no platform device, 1 no driver bound, 2 no host, 3 no device,
#        4 device but no block device, 5 block device present.
#
# It is written twice: before the report is collected (bit 11 clear) and again
# after persistence (bit 11 set), so the value left behind says the report
# reached a medium.  The host half is scripts/read-rtc-state.sh; docs/RTC_REPORT.md
# documents the encoding.
# ---------------------------------------------------------------------------
RTC_REPORT=${GTS9_RTC_REPORT:-0}
# Read by the telemetry block at the end of this script.
rtc_dev_present=0
rtc_written=0
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_rtc_report=*) RTC_REPORT=${arg#gts9_rtc_report=} ;;
    esac
done

storage_stage() {
    # storage_stage <platform device> <host class> <device class> <block>
    [ -e "$1" ] || { echo 0; return; }
    [ -e "$1/driver" ] || { echo 1; return; }
    [ -n "$(ls -d $2 2>/dev/null)" ] || { echo 2; return; }
    [ -n "$(ls -d $3 2>/dev/null)" ] || { echo 3; return; }
    [ -n "$(ls -d $4 2>/dev/null)" ] || { echo 4; return; }
    echo 5
}

rtc_state_word() {
    # rtc_state_word <report_persisted 0|1>
    persisted=$1
    state=0
    mmc_stage=$(storage_stage /sys/bus/platform/devices/8804000.mmc \
                '/sys/class/mmc_host/mmc[0-9]*' \
                '/sys/class/mmc_host/mmc[0-9]*/mmc[0-9]*:*' \
                '/dev/mmcblk*')
    ufs_stage=$(storage_stage /sys/bus/platform/devices/1d84000.ufshc \
                '/sys/class/scsi_host/host[0-9]*' \
                '/sys/class/scsi_device/[0-9]*:*:*:*' \
                '/dev/sd*')
    case "$mmc_stage" in ''|*[!0-9]*) mmc_stage=0 ;; esac
    case "$ufs_stage" in ''|*[!0-9]*) ufs_stage=0 ;; esac
    state=$(( (mmc_stage & 15) | ((ufs_stage & 15) << 4) ))
    [ -n "$(ls /sys/class/udc 2>/dev/null)" ] && state=$((state | (1 << 8)))
    grep -q '8804000' /sys/kernel/debug/devices_deferred 2>/dev/null && state=$((state | (1 << 9)))
    grep -q '1d84000' /sys/kernel/debug/devices_deferred 2>/dev/null && state=$((state | (1 << 10)))
    [ "$persisted" = 1 ] && state=$((state | (1 << 11)))
    chk=$(( ( (state & 15) + ((state >> 4) & 15) + ((state >> 8) & 15) ) & 15 ))
    log "rtc state word: mmc_stage=$mmc_stage ufs_stage=$ufs_stage udc=$([ -n "$(ls /sys/class/udc 2>/dev/null)" ] && echo yes || echo no) persisted=$persisted -> state=$state code=$(( (chk << 12) | state ))"
    echo $(( (chk << 12) | state ))
}

rtc_write_state() {
    # rtc_write_state <report_persisted 0|1>
    persisted=$1
    [ -c /dev/rtc0 ] || { log 'WARN: no /dev/rtc0, cannot leave the state in the RTC'; return 1; }
    if ! command -v date >/dev/null 2>&1 || ! command -v hwclock >/dev/null 2>&1; then
        log 'WARN: date or hwclock missing, cannot leave the state in the RTC'
        return 1
    fi
    rtc_dev_present=1
    code=$(rtc_state_word "$persisted")
    # 2031-01-01T00:00:00Z is the marker: any date in that day is this channel,
    # and the real date means nothing was written.
    epoch=$((1924992000 + code))
    i=0
    got=unknown
    while [ "$i" -lt 3 ]; do
        # Every step has a hard timeout: an SPMI write that never completes must
        # not be able to stop /init before the report and the proof, which is
        # exactly what happened in tests 021-024.
        out=$(timeout 5 date -u -s "@$epoch" 2>&1); rc=$?
        if [ "$rc" != 0 ]; then
            [ "$rc" = 124 ] && out='timed out after 5s'
            log "WARN: date -s @$epoch returned $rc: $out"
            return 1
        fi
        out=$(timeout 5 hwclock -u -w -f /dev/rtc0 2>&1); rc=$?
        if [ "$rc" != 0 ]; then
            [ "$rc" = 124 ] && out='timed out after 5s'
            log "WARN: hwclock -u -w -f /dev/rtc0 returned $rc: $out"
            return 1
        fi
        # Read the hardware clock back through the kernel rather than through
        # the system clock, so a rounded write is visible and can be corrected.
        got=$(timeout 5 cat /sys/class/rtc/rtc0/since_epoch 2>/dev/null)
        case "$got" in
            ''|*[!0-9]*) log 'WARN: cannot read /sys/class/rtc/rtc0/since_epoch'; return 1 ;;
        esac
        [ "$got" = "$epoch" ] && break
        log "note: the RTC stored $got instead of $epoch; compensating"
        epoch=$((epoch + (epoch - got)))
        i=$((i + 1))
    done
    if [ "$got" = "$epoch" ]; then
        rtc_written=1
        log "rtc report written: code=$code epoch=$epoch (2031-01-01 + ${code}s); the RTC reports $got"
        return 0
    fi
    log "WARN: could not write the RTC state word (wanted epoch $epoch, the RTC reports $got)"
    return 1
}

# First write: before the report is collected, so this outcome is in its dmesg.
#
# Disabled by default since test 025: RTC_SET_TIME blocks this board's kernel in
# an uninterruptible SPMI write (RTC_SET_TIME from TWRP returns EACCES before any
# write happens, and the same hang took the SDAM reboot-mode write in test 024),
# so with gts9_rtc_report=1 /init never reaches the report or the proof.  The
# storage stages it carries are in the report anyway; the channel comes back when
# SPMI writes are understood.
[ "$RTC_REPORT" = 1 ] && rtc_write_state 0

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
proof_seconds=''
proof_if=''
proof_code_base=''
proof_action=${GTS9_PROOF_ACTION:-poweroff}
# 1 = hand the next boot to recovery as soon as this boot's work is done.
reboot_after=0
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_userspace_proof=*) proof_seconds=${arg#gts9_userspace_proof=} ;;
        gts9_proof_if=*) proof_if=${arg#gts9_proof_if=} ;;
        gts9_proof_code=*) proof_code_base=${arg#gts9_proof_code=} ;;
        gts9_proof_action=*) proof_action=${arg#gts9_proof_action=} ;;
        gts9_reboot_after=*) reboot_after=${arg#gts9_reboot_after=} ;;
    esac
done

# ---------------------------------------------------------------------------
# Telemetry without a console: encode the state of the bring-up in the delay
# before the tablet powers itself off.  The owner only has to time it.
#
#   code = 1*RTC device + 2*RTC state word written + 4*microSD device
#          + 8*SCSI/UFS disk
#   delay = base + 5*code seconds       (base 20 -> 20,25,...,95 s)
#
# Five seconds per step, because the delay now also carries the RTC diagnostics
# that explain an empty state word, and because a boot always adds the same
# 5-8 s from reset to this point: measured = 5-8 s + delay.
# ---------------------------------------------------------------------------
if [ -n "$proof_code_base" ]; then
    case "$proof_code_base" in
        ''|*[!0-9]*) log "WARN: ignoring invalid gts9_proof_code=$proof_code_base" ;;
        *)
            code=0
            [ "$rtc_dev_present" = 1 ] && code=$((code + 1))
            [ "$rtc_written" = 1 ] && code=$((code + 2))
            if [ -n "$(ls /dev/mmcblk* 2>/dev/null)" ]; then code=$((code + 4)); fi
            if [ -n "$(ls /dev/sd* 2>/dev/null)" ]; then code=$((code + 8)); fi
            proof_seconds=$((proof_code_base + 5 * code))
            log "telemetry code=$code (rtc_dev=$rtc_dev_present rtc_written=$rtc_written mmc=$([ $((code & 4)) -ne 0 ] && echo yes || echo no) scsi=$([ $((code & 8)) -ne 0 ] && echo yes || echo no)) -> power off in ${proof_seconds}s"
            ;;
    esac
fi

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
                sync
                case "$proof_action" in
                    recovery-bcb)
                        # Ask ABL for recovery through the BCB in misc, then
                        # reset: no SPMI write, no owner, no power button.
                        log 'userspace proof firing now (BCB boot-recovery + reset)'
                        reboot_to_recovery
                        ;;
                    recovery)
                        # reboot(2) RESTART2 with the string "recovery" is what
                        # the nvmem reboot-mode driver turns into 0x01 in the
                        # PMK8550 SDAM cell; Samsung's ABL reads that cell and
                        # boots recovery.  busybox cannot pass the string, hence
                        # the small helper built into this initramfs.
                        log 'userspace proof firing now (reboot recovery via the SDAM reboot mode)'
                        if command -v gts9-reboot-recovery >/dev/null 2>&1; then
                            gts9-reboot-recovery
                        fi
                        log 'WARN: the recovery reboot returned; falling back to a plain reset'
                        reboot -f
                        ;;
                    reboot)
                        # A plain reset cannot select the recovery boot mode from
                        # Linux - that needs the BCB in misc (no storage) or the
                        # PMIC PON reason with Samsung's magic (no evidence yet).
                        # It is still more convenient than a power cycle: start
                        # holding Volume Up about five seconds before the reset
                        # and the bootloader lands in recovery by itself.
                        log "userspace proof firing now (reset; hold Volume Up for recovery)"
                        reboot -f
                        ;;
                    *)
                        log "userspace proof firing now (PSCI power off)"
                        poweroff -f || reboot -f
                        ;;
                esac
            ) &
            ;;
    esac
fi

# Give a host that is talking to the gadget its window before the report is
# collected: the recorder above is already capturing what it sends.
case "$USB_WAIT" in
    ''|*[!0-9]*) ;;
    *)
        if [ "$USB_WAIT" -gt 0 ] && [ "$gadget_setup" = 1 ]; then
            log "waiting ${USB_WAIT}s for the host to use the gadget"
            sleep "$USB_WAIT"
        fi
        ;;
esac

# Collect the USB state now that the gadget has been attempted, then get the
# whole report off the device.
report 'usb device controllers' ls -l /sys/class/udc
report 'usb gadget state' sh -c 'ls -l /sys/kernel/config/usb_gadget/gts9 2>&1; cat /sys/kernel/config/usb_gadget/gts9/UDC 2>&1'
report 'dwc3 bindings' sh -c 'ls -l /sys/bus/platform/drivers/dwc3/ 2>&1; ls -l /sys/bus/platform/drivers/dwc3-qcom/ 2>&1'
report 'ttyGS' sh -c 'ls -l /dev/ttyGS* 2>&1'
report 'deferred devices' sh -c 'cat /sys/kernel/debug/devices_deferred 2>&1'
report 'sdhc_2 device links' sh -c 'ls -l /sys/bus/platform/devices/8804000.mmc/ 2>&1'
report 'ufshc device links' sh -c 'ls -l /sys/bus/platform/devices/1d84000.ufshc/ 2>&1'
report 'ufs phy device links' sh -c 'ls -l /sys/bus/platform/devices/1d80000.phy/ 2>&1'
report 'usb phy device links' sh -c 'ls -l /sys/bus/platform/devices/88e3000.phy/ 2>&1'
report 'mmc hosts' sh -c 'ls -l /sys/class/mmc_host/ 2>&1; ls -l /sys/class/mmc_host/*/ 2>&1'
report 'scsi hosts' sh -c 'ls -l /sys/class/scsi_host/ 2>&1; ls -l /sys/class/scsi_device/ 2>&1'
report 'regulator summary' sh -c 'cat /sys/kernel/debug/regulator/regulator_summary 2>&1 | head -80'
report 'clock summary' sh -c 'cat /sys/kernel/debug/clk/clk_summary 2>&1 | head -120'
report 'rtc' sh -c 'ls -l /dev/rtc* 2>&1; cat /proc/driver/rtc 2>&1'
report 'usb repeater (live DT)' sh -c '
    for d in /proc/device-tree/soc@0/*/i2c@*/*redriver*; do
        [ -d "$d" ] || continue
        echo "== $d"
        ls "$d" 2>&1
        for p in compatible qcom,param-override-seq qcom,param-host-override-seq; do
            [ -e "$d/$p" ] || continue
            echo "-- $p"
            od -An -tx1 "$d/$p" 2>&1
        done
    done'
report 'ptn3222 binding' sh -c 'ls -l /sys/bus/i2c/drivers/ptn3222/ 2>&1'
report 'interrupts' sh -c 'cat /proc/interrupts 2>&1'
report 'udc state' sh -c 'for f in /sys/class/udc/*/; do echo "== $f"; for p in state current_speed maximum_speed function is_a_peripheral; do [ -r "$f$p" ] && echo "-- $p: $(cat "$f$p" 2>&1)"; done; done 2>&1'
report 'dwc3 debugfs' sh -c 'ls /sys/kernel/debug/usb/ 2>&1; for d in /sys/kernel/debug/usb/*/; do echo "== $d"; ls "$d" 2>&1; for p in mode link_state; do [ -r "$d$p" ] && echo "-- $p: $(cat "$d$p" 2>&1)"; done; done 2>&1'
report 'gadget functions' sh -c 'ls -l /sys/kernel/config/usb_gadget/gts9/functions/ /sys/kernel/config/usb_gadget/gts9/configs/c.1/ 2>&1; cat /sys/kernel/config/usb_gadget/gts9/functions/mass_storage.usb0/lun.0/file 2>&1'
report 'spmi devices' sh -c 'ls -l /sys/bus/spmi/devices/ 2>&1'
report 'reboot mode' sh -c 'ls -l /sys/class/nvmem/ 2>&1; cat /proc/device-tree/reboot-mode/mode-recovery 2>/dev/null | od -An -tx1; ls -l /sys/bus/platform/drivers/nvmem-reboot-mode/ 2>&1'
report 'dmesg' dmesg

# ---------------------------------------------------------------------------
# Getting the evidence out: persist the report.
#
# dmesg is the whole point - the ring, USB and the panel have all failed as log
# channels for this board - so the report has to land somewhere durable.  Two
# channels are allowed, and nothing else is ever opened for writing:
#
#   * removable storage (/dev/mmcblk*), the intended bring-up medium;
#   * the internal "cache" partition - the one internal partition that is
#     scratch space.  userdata, super, persist, efs, metadata, recovery and the
#     boot partitions are never written, by policy and by construction.
#
# cache is addressed by *partition label from the GPT*, never by kernel device
# name: the label is matched on the disk, and the resulting entry is then
# cross-checked against the kernel's own start and size for the device that
# falls out of it.  One disagreement aborts the write.  A wrong write into
# userdata or a modem partition is the single failure this bring-up cannot
# afford, so identification fails closed.
#
# cache is ext4 on this tablet (verified: 53ef magic at 0x438), so the mount
# path preserves it.  If the filesystem cannot be mounted the report is written
# as a raw block with a "GTS9RPT1" header at offset 0 instead - that does
# destroy an empty, unused cache filesystem, which is acceptable for scratch
# space and is logged when it happens.
# ---------------------------------------------------------------------------
report_target=''
report_written=0
REPORT_LABEL=cache
REPORT_MIN_BYTES=$((4 * 1024 * 1024))
# Every tool the persistence path needs.  If one is missing the whole channel is
# skipped rather than half-executed: a partially written or unverifiable report
# is worse than a clean "nothing was written", and a wrong write is worse still.
REPORT_TOOLS='dd od awk sha256sum basename wc cut tr head printf mount umount cp timeout'


report_mount=''
try_report_mount() {
    # try_report_mount <device> <label>
    dev=$1
    [ -b "$dev" ] || return 1
    # exfat matters: cards of 64 GB and up are formatted that way by default,
    # and CONFIG_EXFAT_FS is built in.  The SHA-256 sidecar is what the host
    # reader checks the copy against; it is best effort, the report is not.
    for fs in vfat exfat ext4 ext2 f2fs; do
        if timeout 15 mount -t $fs -o rw "$dev" /mnt 2>/dev/null; then
            if timeout 30 cp "$REPORT" /mnt/gts9-bringup-report.txt 2>/dev/null; then
                sha256sum /mnt/gts9-bringup-report.txt \
                    > /mnt/gts9-bringup-report.txt.sha256 2>/dev/null
                sync
                report_target="$dev ($fs, $2)"
                report_written=1
                # Anything the serial probe recorded goes next to the report, so
                # the host can read it through the mass-storage export.
                if [ -s /tmp/gts9-serial-in.txt ]; then
                    timeout 30 cp /tmp/gts9-serial-in.txt /mnt/gts9-serial-in.txt 2>/dev/null
                    log "serial input recorded to the medium ($(wc -c < /tmp/gts9-serial-in.txt 2>/dev/null) bytes)"
                fi
                sync
                # Unmount before the LUN is attached: the host mounts this
                # filesystem itself, and two writers is one too many.
                umount /mnt 2>/dev/null
                return 0
            fi
            umount /mnt 2>/dev/null
        fi
    done
    return 1
}

write_report_raw() {
    # write_report_raw <partition device> <sector size>
    dev=$1; ss=$2
    body=$(wc -c < "$REPORT" 2>/dev/null)
    case "$body" in ''|*[!0-9]*) log 'WARN: cannot size the report'; return 1 ;; esac
    sha=$(sha256sum "$REPORT" 2>/dev/null | cut -d' ' -f1)
    [ -n "$sha" ] || sha=none
    rel=$(cat /proc/sys/kernel/osrelease 2>/dev/null)
    # The two %08d widths make the header length independent of the values, so
    # "total" can be computed from the header itself.
    hdr=$(printf 'GTS9RPT1 total=%08d body=%08d sha256=%s release=%s\n' 0 0 "$sha" "$rel")
    total=$(( ${#hdr} + body ))
    hdr=$(printf 'GTS9RPT1 total=%08d body=%08d sha256=%s release=%s\n' "$total" "$body" "$sha" "$rel")
    { printf '%s' "$hdr"; cat "$REPORT"; } > /tmp/gts9-report-block.bin || return 1
    written=$(wc -c < /tmp/gts9-report-block.bin)
    [ "$written" = "$total" ] || { log "WARN: report block is $written bytes, expected $total"; return 1; }
    timeout 30 dd if=/tmp/gts9-report-block.bin of="$dev" bs="$ss" seek=0 conv=notrunc 2>/dev/null || return 1
    sync
    log "raw report block: $total bytes (body $body, sha256 $sha)"
    return 0
}

report_via_cache() {
    for disk in /dev/sd?; do
        [ -b "$disk" ] || continue
        ss=$(block_size "$disk")
        entries=$(gpt_entries "$disk" 2>/dev/null)
        [ -n "$entries" ] || continue
        match=$(echo "$entries" | awk -v name="$REPORT_LABEL" '$5 == name { print; exit }')
        [ -n "$match" ] || { log "note: no '$REPORT_LABEL' partition in the GPT of $disk"; continue; }
        set -- $match
        index=$1; start=$2; nbytes=$4
        pdev="${disk}$((index + 1))"
        pbase=$(basename "$pdev")
        [ -b "$pdev" ] || { log "WARN: $disk GPT entry $index is '$REPORT_LABEL' but $pdev is missing"; continue; }
        kstart=$(cat "/sys/class/block/$pbase/start" 2>/dev/null)
        ksize=$(cat "/sys/class/block/$pbase/size" 2>/dev/null)
        case "$kstart$ksize" in ''|*[!0-9]*)
            log "WARN: cannot read the geometry of $pbase"
            continue
            ;;
        esac
        if [ "$((kstart * 512))" != "$((start * ss))" ] || [ "$((ksize * 512))" != "$nbytes" ]; then
            log "WARN: GPT and kernel disagree about $pdev ($REPORT_LABEL): GPT start=$((start * ss)) size=$nbytes, kernel start=$((kstart * 512)) size=$((ksize * 512))"
            continue
        fi
        [ "$nbytes" -ge "$REPORT_MIN_BYTES" ] || { log "WARN: $pdev is too small to hold the report"; continue; }
        log "internal target accepted: $pdev = GPT entry $index '$REPORT_LABEL' on $disk, start=$((start * ss)), size=$nbytes (kernel agrees)"
        if try_report_mount "$pdev" "internal $REPORT_LABEL"; then
            return 0
        fi
        log "WARN: no filesystem mounted from $pdev; falling back to a raw block write"
        if write_report_raw "$pdev" "$ss"; then
            report_target="$pdev (raw block at offset 0, internal $REPORT_LABEL)"
            report_written=1
            return 0
        fi
        log "WARN: the raw write to $pdev failed"
    done
    return 1
}

for disk in /dev/sd?; do
    [ -b "$disk" ] || continue
    report "gpt of $disk" gpt_entries "$disk"
done
report 'block devices in /dev' sh -c 'ls -l /dev/sd* /dev/mmcblk* 2>&1'

missing_tools=''
for tool in $REPORT_TOOLS; do
    command -v "$tool" >/dev/null 2>&1 || missing_tools="$missing_tools $tool"
done

if [ -n "$missing_tools" ]; then
    log "WARN: report persistence disabled, missing tools:$missing_tools"
else
    # Removable storage first: a card is the intended medium and writing to it
    # can never damage the tablet.
    mkdir -p /mnt
    for dev in $(ls -1 /dev/mmcblk*p* /dev/mmcblk* 2>/dev/null); do
        if try_report_mount "$dev" removable; then
            log "bring-up report written to $report_target"
            break
        fi
    done

    if [ "$report_written" != 1 ]; then
        report_via_cache
        [ "$report_written" = 1 ] && log "bring-up report written to $report_target"
    fi
    [ "$report_written" = 1 ] || log 'WARN: no medium accepted the bring-up report'
fi

# Second write: the value left in the RTC records that the report was persisted.
[ "$RTC_REPORT" = 1 ] && rtc_write_state 1

# Attach the microSD card to the mass-storage LUN now: by this point the report
# has been written and the card unmounted, and the host can mount the volume
# read-only while this boot is still running.
if [ "$gadget_setup" = 1 ]; then
    case "$USB_GADGET_MODE" in
        msc|both)
            if [ -b "$USB_MSC_BACKING" ]; then
                if echo "$USB_MSC_BACKING" > /sys/kernel/config/usb_gadget/gts9/functions/mass_storage.usb0/lun.0/file 2>/dev/null; then
                    log "mass storage: $USB_MSC_BACKING exported read-only to the host"
                else
                    log "WARN: could not attach $USB_MSC_BACKING to the mass-storage LUN"
                fi
            else
                log "WARN: $USB_MSC_BACKING is missing; no medium for the mass-storage LUN"
            fi
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# The short cycle the owner asked for: once everything this boot was going to do
# is done, wait ten seconds and hand the next boot to recovery.  The timed proof
# armed earlier stays as the safety net for a boot that never reaches this point,
# so a hang still ends in a reboot instead of a tablet left sitting there.
# ---------------------------------------------------------------------------
if [ "$reboot_after" = 1 ] && [ "$proof_action" = recovery-bcb ] && [ -n "$proof_code_base" ]; then
    log "work complete (report_written=$report_written, target=${report_target:-none}); rebooting into recovery in 10s"
    sleep 10
    reboot_to_recovery
fi


if [ "$gadget_setup" = 1 ]; then
    # Wait for the ACM port to appear, then mirror the kernel log onto it and
    # hand the same port to a shell.  The host side gets live evidence either
    # way: a port that stays silent means this script never ran.
    i=0
    while [ "$i" -lt 20 ] && [ ! -c /dev/ttyGS0 ]; do
        sleep 1
        i=$((i + 1))
    done
    if [ -c /dev/ttyGS0 ] && [ "$USB_CONSOLE_MODE" = marker ]; then
        # Whatever the host sends is kept for the report: this is what makes the
        # host->device direction of the link measurable through the card.
        ( timeout 900 cat /dev/ttyGS0 >> /tmp/gts9-serial-in.txt 2>/dev/null ) &
        log 'recording usb serial input to /tmp/gts9-serial-in.txt'
    fi
    if [ -c /dev/ttyGS0 ] && [ "$USB_CONSOLE_MODE" = marker ]; then
        # Diagnostic mode: prove both directions of the link through the card.
        # The host should see the marker lines, and whatever it types is recorded
        # into gts9-serial-in.txt next to the report.
        log 'usb console in marker mode: writing a marker and recording host input'
        printf 'GTS9-SERIAL-MARKER ready\n' > /dev/ttyGS0 2>/dev/null
        printf 'GTS9-SERIAL-MARKER uname=%s\n' "$(uname -r 2>/dev/null)" > /dev/ttyGS0 2>/dev/null
        printf 'GTS9-SERIAL-MARKER uptime=%s\n' "$(cat /proc/uptime 2>/dev/null | cut -d' ' -f1)" > /dev/ttyGS0 2>/dev/null
        printf 'GTS9-SERIAL-MARKER end\n' > /dev/ttyGS0 2>/dev/null
        # Record the host->device direction where the mass-storage export can
        # reach it: the report's directory on the card.
        if [ -n "$report_mount" ]; then
            ( timeout 600 cat /dev/ttyGS0 >> "$report_mount/gts9-serial-in.txt" 2>/dev/null ) &
            log "recording serial input to $report_mount/gts9-serial-in.txt"
        else
            log 'WARN: no mounted medium; serial input cannot be recorded'
        fi
    fi
    if [ -c /dev/ttyGS0 ] && [ "$USB_CONSOLE_MODE" != marker ]; then
        # The shell is the console.  It is also the only reader of the port, and
        # it has to stay the only one: a host write only completes while
        # something on this side is reading, which is exactly why the earlier
        # boots looked like "sending data hangs" - /init had never reached this
        # block, and between shell attempts nothing was reading at all.
        #
        # The kernel log is *not* streamed here by default: `cat /dev/kmsg` on a
        # port nobody is draining fills the tty buffer and then blocks the
        # shell's own output.  The full log travels on the card instead, and
        # `dmesg` works from the shell.
        case "$USB_CONSOLE_MODE" in
            shell+kmsg)
                log 'streaming the kernel log to /dev/ttyGS0 as well'
                ( cat /dev/kmsg > /dev/ttyGS0 2>/dev/null ) &
                ;;
        esac
        log 'handing /dev/ttyGS0 to an interactive shell'
        printf '\nGTS9 bring-up console.  Log: /tmp/bringup-report.txt on the card.\n' > /dev/ttyGS0 2>/dev/null
        printf 'Type gts9-to-recovery to reboot into TWRP.\n\n' > /dev/ttyGS0 2>/dev/null
        while :; do
            PS1='gts9# ' /bin/sh -i </dev/ttyGS0 >/dev/ttyGS0 2>&1
            log 'usb shell ended (host closed the port); reopening'
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
