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

log ''
log 'dropping to an interactive shell; nothing was written to any block device'
log ''

# PID 1 must survive EOF, an unavailable UART and a user's "exit". Replacing
# init with a shell makes all of those cases panic (Attempted to kill init!).
# Reopen the console after devtmpfs has been mounted; /dev/console may not
# have existed when the kernel opened init's standard descriptors.
while :; do
    /bin/sh -i </dev/console >/dev/console 2>&1
    log 'console shell ended or unavailable; PID 1 remains alive, retrying in 5s'
    sleep 5
done
