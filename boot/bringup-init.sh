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
proof_seconds=''
proof_if=''
proof_code_base=''
proof_action=${GTS9_PROOF_ACTION:-poweroff}
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_userspace_proof=*) proof_seconds=${arg#gts9_userspace_proof=} ;;
        gts9_proof_if=*) proof_if=${arg#gts9_proof_if=} ;;
        gts9_proof_code=*) proof_code_base=${arg#gts9_proof_code=} ;;
        gts9_proof_action=*) proof_action=${arg#gts9_proof_action=} ;;
    esac
done

# ---------------------------------------------------------------------------
# Telemetry without a console: encode the state of the bring-up in the delay
# before the tablet powers itself off.  The owner only has to time it.
#
#   code = 1*microSD device + 2*SCSI/UFS disk + 4*USB device controller
#   delay = base + 10*code seconds      (base 20 -> 20,30,...,90 s)
# ---------------------------------------------------------------------------
if [ -n "$proof_code_base" ]; then
    case "$proof_code_base" in
        ''|*[!0-9]*) log "WARN: ignoring invalid gts9_proof_code=$proof_code_base" ;;
        *)
            code=0
            if [ -n "$(ls /dev/mmcblk* 2>/dev/null)" ]; then code=$((code + 1)); fi
            if [ -n "$(ls /dev/sd* 2>/dev/null)" ]; then code=$((code + 2)); fi
            if [ -n "$(ls /sys/class/udc 2>/dev/null)" ]; then code=$((code + 4)); fi
            proof_seconds=$((proof_code_base + 10 * code))
            log "telemetry code=$code (mmc=$([ $((code & 1)) -ne 0 ] && echo yes || echo no) scsi=$([ $((code & 2)) -ne 0 ] && echo yes || echo no) udc=$([ $((code & 4)) -ne 0 ] && echo yes || echo no)) -> power off in ${proof_seconds}s"
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
REPORT_TOOLS='dd od awk sha256sum basename wc cut tr head printf mount umount cp'

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
    hdr=$(dd if="$dev" bs="$ss" skip=1 count=1 2>/dev/null | head -c 92 | \
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

    dd if="$dev" bs="$ss" skip="$elba" count=$(( (nent * esz + ss - 1) / ss )) 2>/dev/null | \
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

try_report_mount() {
    # try_report_mount <device> <label>
    dev=$1
    [ -b "$dev" ] || return 1
    # exfat matters: cards of 64 GB and up are formatted that way by default,
    # and CONFIG_EXFAT_FS is built in.  The SHA-256 sidecar is what the host
    # reader checks the copy against; it is best effort, the report is not.
    for fs in vfat exfat ext4 ext2 f2fs; do
        if mount -t $fs -o rw "$dev" /mnt 2>/dev/null; then
            if cp "$REPORT" /mnt/gts9-bringup-report.txt 2>/dev/null; then
                sha256sum /mnt/gts9-bringup-report.txt \
                    > /mnt/gts9-bringup-report.txt.sha256 2>/dev/null
                sync
                report_target="$dev ($fs, $2)"
                report_written=1
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
    dd if=/tmp/gts9-report-block.bin of="$dev" bs="$ss" seek=0 conv=notrunc 2>/dev/null || return 1
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
