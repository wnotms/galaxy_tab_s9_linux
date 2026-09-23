#!/bin/sh
# Minimal PID 1 path for the gts9_minimal_rootfs=1 boot profile.
#
# /proc is mounted by bringup-init.sh so this script can inspect cmdline and
# mount the remaining pseudo filesystems without entering the full bring-up.
#
# Every stage is reported on /dev/kmsg and /dev/console, and - once the Debian
# root filesystem is mounted - persisted to
#
#	/newroot/var/log/gts9-minimal-last-boot
#
# by boot/minimal-rootfs-state.sh.  That file is the evidence a later TWRP
# session reads when the panel stays black and no USB console appears; losing
# it would make a failed boot indistinguishable from a boot that never ran.

PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

ROOTFS_DEVICE=/dev/mmcblk1p1
ROOTFS_WAIT_SECONDS=30
MINIMAL_STATE_LIB=${GTS9_MINIMAL_STATE_LIB:-/minimal-rootfs-state.sh}

# Fallbacks, replaced by the state library below.  A hand-built initramfs that
# forgot the library still boots and still talks on the console; it only loses
# the persistent record.
minimal_emit() {
    printf '%s\n' "$*"
    if [ -w /dev/kmsg ]; then
        printf 'gts9-minimal: %s\n' "$*" > /dev/kmsg 2>/dev/null || true
    fi
    if [ -c /dev/console ]; then
        printf '%s\n' "$*" > /dev/console 2>/dev/null || true
    fi
    if [ -c /dev/tty1 ]; then
        printf '%s\n' "$*" > /dev/tty1 2>/dev/null || true
    fi
}
minimal_state_init() { :; }
minimal_state_persist_enable() { :; }
minimal_state_write() { :; }
minimal_state_stage() {
    GTS9_MINIMAL_STAGE=$1
    minimal_emit "GTS9_MINIMAL_STAGE=$GTS9_MINIMAL_STAGE"
}
minimal_state_fail() {
    GTS9_MINIMAL_FAILURE=$1
    minimal_emit "GTS9_MINIMAL_FAIL=$GTS9_MINIMAL_FAILURE"
}

if [ -r "$MINIMAL_STATE_LIB" ]; then
    . "$MINIMAL_STATE_LIB"
else
    minimal_emit "GTS9_MINIMAL_WARN=state-library-missing:$MINIMAL_STATE_LIB"
fi

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
    minimal_emit "  $GTS9_MINIMAL_STAGE"
    minimal_emit "last failure: $GTS9_MINIMAL_FAILURE"
    minimal_emit "persistent record: ${GTS9_MINIMAL_RECORD:-not-available}"
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
    minimal_state_fail "$1"
    minimal_rescue_shell
}

# The handoff init defaults to the direct /sbin/init path that the full
# bring-up profile has already proven on this device.  The static trampoline
# (with its post-switch_root watchdog) is opt-in through
# gts9_minimal_init=/run/gts9-minimal-pid1 while it is still being validated:
# test 178 boot #3 hung the tablet hard enough that no key combination reached
# TWRP, so the default path must be the one with a working history.
MINIMAL_INIT=/sbin/init
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_rootfs=*) ROOTFS_DEVICE=${arg#gts9_rootfs=} ;;
        gts9_minimal_init=*) MINIMAL_INIT=${arg#gts9_minimal_init=} ;;
    esac
done
GTS9_MINIMAL_ROOT_DEVICE=$ROOTFS_DEVICE

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

minimal_state_init
minimal_state_stage kernel-userspace
minimal_state_stage waiting-root
waited=0
while [ ! -b "$ROOTFS_DEVICE" ] && [ "$waited" -lt "$ROOTFS_WAIT_SECONDS" ]; do
    sleep 1
    waited=$((waited + 1))
done

if [ ! -b "$ROOTFS_DEVICE" ]; then
    minimal_emit "root device missing: $ROOTFS_DEVICE (waited ${waited}s)"
    minimal_fail root-timeout
fi

minimal_state_stage root-found
mkdir -p /newroot || minimal_fail root-mount
minimal_state_stage mounting-root
if ! mount -t ext4 -o rw "$ROOTFS_DEVICE" /newroot; then
    minimal_emit "could not mount $ROOTFS_DEVICE as ext4"
    minimal_fail root-mount
fi
minimal_state_stage root-mounted
# The root filesystem is writable now: persist the whole history gathered in
# RAM (kernel-userspace, waiting-root, root-found, mounting-root, root-mounted)
# and keep the record updated for every later stage.
minimal_state_persist_enable /newroot/var/log

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

minimal_state_stage init-found
mkdir -p /newroot/dev /newroot/proc /newroot/sys /newroot/run || \
    minimal_fail root-mount
if ! cp /sbin/gts9-minimal-pid1 /run/gts9-minimal-pid1 ||
   ! cp /bin/busybox /run/busybox ||
   ! chmod 0755 /run/gts9-minimal-pid1 /run/busybox; then
    minimal_emit 'could not stage the minimal PID 1 rescue helper'
    minimal_fail switch-root-returned
fi

# Run the staged trampoline once, normally, before the handoff.  If it cannot
# execute or cannot append to the record, it would kill PID 1 inside
# switch_root with nothing on the disk to show for it - so fall back to the
# proven direct /sbin/init path instead of risking a silent dead device.
if [ "$MINIMAL_INIT" = /run/gts9-minimal-pid1 ]; then
    # The marker goes to its own file: the library rewrites the record
    # atomically, so a marker appended to the record now would be replaced by
    # the switch-root write a moment later.
    SELFTEST_FILE=$GTS9_MINIMAL_LOG_DIR/gts9-minimal-trampoline-selftest
    # Bounded: a trampoline that never returns must not freeze PID 1 in the
    # initramfs, which is what test 178 boot #3 did (the record stopped at
    # init-found and even the key combination could not reach TWRP).
    if timeout 5 /run/gts9-minimal-pid1 selftest "$SELFTEST_FILE"; then
        minimal_emit 'GTS9_MINIMAL_TRAMPOLINE=selftest-ok'
        minimal_state_stage switch-root-selftest-ok
    else
        minimal_emit 'GTS9_MINIMAL_TRAMPOLINE=selftest-failed'
        minimal_state_stage switch-root-selftest-failed
        minimal_emit 'falling back to /sbin/init for the handoff'
        MINIMAL_INIT=/sbin/init
    fi
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

# The staged helper must be reachable in the new root exactly as switch_root
# will resolve it: /run is the tmpfs that was just moved there.
if [ "$MINIMAL_INIT" = /run/gts9-minimal-pid1 ] &&
   [ ! -x /newroot/run/gts9-minimal-pid1 ]; then
    minimal_emit 'the staged PID 1 helper is not executable in the new root'
    minimal_fail switch-root-returned
fi

# Written and flushed before the only irreversible step: even if Debian's
# /sbin/init never reaches systemd, TWRP can still prove that the card mounted,
# /sbin/init was found and switch_root was about to run.
minimal_state_stage switch-root
sync
# A separate marker after the standalone sync: if the record stops at
# switch-root, the sync never returned; if it stops here, the handoff itself
# (switch_root or the exec of the new init) is what failed.
minimal_state_stage switch-root-synced
exec switch_root /newroot "$MINIMAL_INIT"

# The static PID 1 trampoline execs the already-validated /sbin/init. If that
# exec returns, it reports the failure and keeps a BusyBox rescue shell alive.
minimal_fail switch-root-returned
