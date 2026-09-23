#!/bin/sh
# Minimal PID 1 path for the gts9_minimal_rootfs=1 boot profile.
# /proc is mounted by bringup-init.sh so this script can inspect cmdline and
# mount the remaining pseudo filesystems without entering the full bring-up.

PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

MINIMAL_LAST_STAGE=init-start
ROOTFS_DEVICE=/dev/mmcblk1p1
ROOTFS_WAIT_SECONDS=30

minimal_emit() {
    minimal_message=$*
    printf '%s\n' "$minimal_message"
    if [ -w /dev/kmsg ]; then
        printf 'gts9-minimal: %s\n' "$minimal_message" > /dev/kmsg 2>/dev/null || true
    fi
    if [ -c /dev/console ]; then
        printf '%s\n' "$minimal_message" > /dev/console 2>/dev/null || true
    fi
    # This is opportunistic output only: the minimal path never waits for DRM,
    # fbcon, or tty1 to appear.
    if [ -c /dev/tty1 ]; then
        printf '%s\n' "$minimal_message" > /dev/tty1 2>/dev/null || true
    fi
}

minimal_stage() {
    MINIMAL_LAST_STAGE=$1
    minimal_emit "GTS9_MINIMAL_STAGE=$MINIMAL_LAST_STAGE"
}

mount_pseudo_if_missing() {
    pseudo_type=$1
    pseudo_source=$2
    pseudo_target=$3
    mkdir -p "$pseudo_target" 2>/dev/null || return 1
    if grep -q " $pseudo_target " /proc/mounts 2>/dev/null; then
        return 0
    fi
    mount -t "$pseudo_type" "$pseudo_source" "$pseudo_target"
}

minimal_rescue_shell() {
    minimal_emit 'GTS9_MINIMAL_RESCUE=BusyBox shell'
    minimal_emit 'root device missing or handoff failed; inspect the block state below'
    minimal_emit 'last stage: '
    minimal_emit "  $MINIMAL_LAST_STAGE"
    minimal_emit 'check with: cat /proc/partitions'
    cat /proc/partitions 2>&1
    minimal_emit 'check with: ls -l /sys/class/block'
    ls -l /sys/class/block 2>&1
    minimal_emit 'check with: ls -l /dev/mmcblk*'
    ls -l /dev/mmcblk* 2>&1
    minimal_emit 'rescue shell: /bin/sh -i (type exit to restart it)'

    # Keep PID 1 alive if an owner exits the interactive shell.  This path does
    # not depend on tty1 or USB ACM; /dev/console is the only shell endpoint.
    while :; do
        if [ -c /dev/console ]; then
            /bin/sh -i </dev/console >/dev/console 2>&1
        else
            /bin/sh -i
        fi
        sleep 1
    done
}

minimal_fail() {
    minimal_reason=$1
    minimal_emit "GTS9_MINIMAL_FAIL=$minimal_reason"
    minimal_emit "GTS9_MINIMAL_LAST_STAGE=$MINIMAL_LAST_STAGE"
    minimal_rescue_shell
}

for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_rootfs=*) ROOTFS_DEVICE=${arg#gts9_rootfs=} ;;
    esac
done

if ! mount_pseudo_if_missing proc proc /proc; then
    minimal_emit 'GTS9_MINIMAL_FAIL=pseudo-mount'
    minimal_emit 'ERROR: could not mount procfs'
    minimal_rescue_shell
fi
if ! mount_pseudo_if_missing sysfs sysfs /sys; then
    minimal_emit 'GTS9_MINIMAL_FAIL=pseudo-mount'
    minimal_emit 'ERROR: could not mount sysfs'
    minimal_rescue_shell
fi
if ! mount_pseudo_if_missing devtmpfs devtmpfs /dev; then
    minimal_emit 'GTS9_MINIMAL_FAIL=pseudo-mount'
    minimal_emit 'ERROR: could not mount devtmpfs'
    minimal_rescue_shell
fi
if ! mount_pseudo_if_missing tmpfs tmpfs /run; then
    minimal_emit 'GTS9_MINIMAL_FAIL=pseudo-mount'
    minimal_emit 'ERROR: could not mount tmpfs on /run'
    minimal_rescue_shell
fi

minimal_stage kernel-userspace
minimal_stage waiting-root
waited=0
while [ ! -b "$ROOTFS_DEVICE" ] && [ "$waited" -lt "$ROOTFS_WAIT_SECONDS" ]; do
    sleep 1
    waited=$((waited + 1))
done

if [ ! -b "$ROOTFS_DEVICE" ]; then
    minimal_emit "root device missing: $ROOTFS_DEVICE (waited ${waited}s)"
    minimal_fail root-timeout
fi

minimal_stage root-found
mkdir -p /newroot || minimal_fail root-mount
minimal_stage mounting-root
if ! mount -t ext4 -o rw "$ROOTFS_DEVICE" /newroot; then
    minimal_emit "could not mount $ROOTFS_DEVICE as ext4"
    minimal_fail root-mount
fi
minimal_stage root-mounted

if [ ! -x /newroot/sbin/init ]; then
    minimal_emit 'missing or non-executable init: /newroot/sbin/init'
    umount /newroot 2>/dev/null || true
    minimal_fail missing-init
fi
if ! command -v switch_root >/dev/null 2>&1; then
    minimal_emit 'BusyBox switch_root applet is unavailable'
    umount /newroot 2>/dev/null || true
    minimal_fail switch-root-returned
fi

minimal_stage init-found
mkdir -p /newroot/dev /newroot/proc /newroot/sys /newroot/run || \
    minimal_fail root-mount
if ! cp /sbin/gts9-minimal-pid1 /run/gts9-minimal-pid1 ||
   ! cp /bin/busybox /run/busybox ||
   ! chmod 0755 /run/gts9-minimal-pid1 /run/busybox; then
    minimal_emit 'could not stage the minimal PID 1 rescue helper'
    minimal_fail switch-root-returned
fi
MOVED_VFS=''
for vfs in dev proc sys run; do
    if ! mount --move "/$vfs" "/newroot/$vfs" 2>/dev/null &&
       ! mount -o move "/$vfs" "/newroot/$vfs" 2>/dev/null; then
        minimal_emit "could not move /$vfs into the Debian root"
        for moved in $MOVED_VFS; do
            if ! mount --move "/newroot/$moved" "/$moved" 2>/dev/null; then
                mount -o move "/newroot/$moved" "/$moved" 2>/dev/null || true
            fi
        done
        minimal_fail switch-root-returned
    fi
    MOVED_VFS="$vfs $MOVED_VFS"
done

minimal_stage switch-root
exec switch_root /newroot /run/gts9-minimal-pid1

# The static PID 1 trampoline execs the already-validated /sbin/init. If that
# exec returns, it reports the failure and keeps a BusyBox rescue shell alive.
minimal_fail switch-root-returned
