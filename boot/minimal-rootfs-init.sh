#!/bin/sh
# Minimal PID 1: hand PID 1 to the Debian root filesystem on the microSD card.
#
# This script is a complete /init on its own.  It does NOT need bringup-init.sh
# to have run first, and the production initramfs installs it as /init directly.
#
# Order matters, and getting it wrong is silent rather than loud: /proc must be
# mounted BEFORE /proc/cmdline is read, or the read fails and every gts9_* option
# is dropped without a message.  This script used to rely on bringup-init.sh
# having mounted procfs already, which was true as a branch of that script and
# false the moment it became /init.  The sequence below is therefore:
#
#   1. PATH
#   2. mount /proc                      <- so the next step can work
#   3. parse /proc/cmdline
#   4. mount /sys, /dev, /run
#   5. state library
#   6. root wait / mount / switch_root
#
# Every stage is reported on /dev/kmsg and the console, and - once the Debian root
# filesystem is mounted - persisted to
#
#	/newroot/var/log/gts9-minimal-last-boot
#
# by boot/minimal-rootfs-state.sh.  That file is the evidence a later TWRP
# session reads when the panel stays black and there is no network yet; losing it
# would make a failed boot indistinguishable from a boot that never ran.

PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

ROOTFS_DEVICE=/dev/mmcblk1p1
ROOTFS_WAIT_SECONDS=30
MINIMAL_INIT=/sbin/init
MINIMAL_STATE_LIB=${GTS9_MINIMAL_STATE_LIB:-/minimal-rootfs-state.sh}

# Fallbacks, replaced by the state library below.  A hand-built initramfs that
# forgot the library still boots and still reports; it only loses the persistent
# record.
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

# ---------------------------------------------------------------------------
# 1 and 2.  /proc first, unconditionally and before anything reads cmdline.
#
# This cannot itself depend on /proc/mounts (the mount may not be there yet), so
# it is a plain mount with the "already mounted" case inferred from the mount's
# own failure.  A kernel always provides procfs, so a failure here means the
# kernel is not what we think it is and the rescue shell is the right answer.
# ---------------------------------------------------------------------------
mkdir -p /proc 2>/dev/null || true
if ! grep -q ' /proc ' /proc/mounts 2>/dev/null; then
    mount -t proc proc /proc 2>/dev/null || true
fi
if [ ! -r /proc/cmdline ]; then
    minimal_emit 'GTS9_MINIMAL_FAIL=proc-mount'
    minimal_emit 'ERROR: /proc/cmdline is unreadable after mounting procfs'
    minimal_emit 'gts9_* options cannot be read; the built-in defaults apply'
fi

# ---------------------------------------------------------------------------
# 3. cmdline, now that it can actually be read.
# ---------------------------------------------------------------------------
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in
        gts9_rootfs=*) ROOTFS_DEVICE=${arg#gts9_rootfs=} ;;
        gts9_minimal_init=*) MINIMAL_INIT=${arg#gts9_minimal_init=} ;;
        # Ask for the verbose boot record: the full kernel command line and the
        # mmc device inventory.  Off by default because the record is read by a
        # person in TWRP and the cmdline alone is over half its size; on when
        # diagnosing a handoff that ignored an option.
        gts9_initramfs_debug=*) GTS9_INITRAMFS_DEBUG=${arg#gts9_initramfs_debug=} ;;
    esac
done
GTS9_INITRAMFS_DEBUG=${GTS9_INITRAMFS_DEBUG:-0}
# The state library reads this, so it has to be exported rather than merely set.
export GTS9_INITRAMFS_DEBUG
GTS9_MINIMAL_ROOT_DEVICE=$ROOTFS_DEVICE

# Bring the panel back, but ONLY when the handoff has already failed.
#
# Why this exists at all: Debian's gts9-panel-recover.service is what cycles the
# framebuffer when the panel's cold-boot enable reads a dead DDIC
# (`ana38407 panel id: 00 00 00`), and it runs at ~3.7 s on a healthy boot.  In the
# rescue path Debian never starts, so that service never runs - and on a cold boot
# that hit the zero-ID case the rescue shell would be printed to a screen nobody
# can see.  The failure test on 2026-09-26 walked into exactly that hole.
#
# Why it is gated rather than simply restored: display recovery is a diagnostic
# capability and it puts a full DPU modeset on the critical path, where test 178
# once caught an intermittent hang (enc35 frame done timeout -> vblank wait
# timeout -> workqueue lockup -> RCU stall).  Running it only after the root mount
# has already failed means a healthy boot pays nothing - not a byte of I/O, not a
# millisecond - and the one boot that needs it is the one that has nothing left to
# lose.
#
# Deliberately minimal, and deliberately quieter than the debug version: it waits
# for fb0, cycles blank/unblank a few times, and gives up.  It does not parse
# dmesg (the production image has no dmesg applet), so it cannot check for the
# driver's zero-ID line and does not try to.
minimal_panel_rescue() {
    panel_fb=/sys/class/graphics/fb0/blank
    panel_waited=0
    while [ ! -w "$panel_fb" ] && [ "$panel_waited" -lt 5 ]; do
        sleep 1
        panel_waited=$((panel_waited + 1))
    done
    if [ ! -w "$panel_fb" ]; then
        minimal_emit 'panel: no writable framebuffer; cannot try to recover it'
        return 0
    fi
    minimal_emit 'panel: cycling the framebuffer so the rescue shell can be seen'
    panel_cycle=0
    while [ "$panel_cycle" -lt 3 ]; do
        printf '1' > "$panel_fb" 2>/dev/null || true
        sleep 1
        printf '0' > "$panel_fb" 2>/dev/null || true
        sleep 1
        panel_cycle=$((panel_cycle + 1))
    done
    return 0
}

# ---------------------------------------------------------------------------
# Ask the bootloader for TWRP, so a failed handoff ends somewhere useful.
#
# This is the answer to the hole the failure test on 2026-09-26 exposed.  The
# rescue shell was a dead end: no network (no gadget, no Wi-Fi), no serial port,
# and at first not even a reboot applet - the tablet had to be recovered with a
# physical key combination.  A rescue shell that strands the device is not a
# rescue.
#
# The mechanism is the Android bootloader control block, and it is the one this
# board is known to honour.  ABL reads the first bytes of the `misc` partition on
# every boot and starts recovery when it finds the ASCII command "boot-recovery":
#
#     gts9_proof_action=recovery-bcb
#
# was confirmed end to end by test 028 - 33 s from `adb reboot` to TWRP,
# unattended.  `reboot recovery` cannot be used instead: it goes through
# nvmem-reboot-mode into the PMK8550's SPMI SDAM, and an SPMI write blocks this
# kernel uninterruptibly (tests 024/025).  So the BCB is written and then a PLAIN
# restart is requested - docs/REBOOT_MODES.md has the full reasoning.
#
# Three properties keep it safe, and all three matter because this writes to a
# partition:
#
#   * the device is found by the kernel's OWN GPT label, through the PARTNAME the
#     EFI partition parser publishes in sysfs.  Nothing is guessed from a device
#     number, so this cannot land in somebody else's partition.  The debug image
#     cross-checks start/size against a GPT it parses itself; here the kernel has
#     already done that, which is why this needs no GPT parser and no `od`.
#   * it is ONE SHOT.  If `misc` already asks for recovery, the bootloader has
#     ignored the request once already, so this powers off instead of resetting
#     into a loop - the same rule boot/bringup-init.sh uses.
#   * it fails open.  Any problem - no misc partition, an unreadable header, a
#     failed write, a read-back that does not match - is reported and the rescue
#     shell still runs.  A shell on a dark tablet beats a tablet that rebooted
#     into nothing.
# ---------------------------------------------------------------------------
minimal_misc_device() {
    misc_want=${1:-misc}
    for misc_dir in /sys/class/block/sd* /sys/class/block/mmcblk*p*; do
        [ -r "$misc_dir/uevent" ] || continue
        # PARTNAME is the GPT volume label as the kernel parsed it.  The
        # comparison is exact and an empty label cannot match.
        misc_label=$(sed -n 's/^PARTNAME=//p' "$misc_dir/uevent" 2>/dev/null | head -1)
        [ -n "$misc_label" ] || continue
        [ "$misc_label" = "$misc_want" ] || continue
        misc_name=$(basename "$misc_dir")
        # Never the microSD: misc lives on the UFS, and an mmcblk partition with a
        # coincidental label would put the BCB on the card instead.
        case "$misc_name" in mmcblk*) continue ;; esac
        for misc_dev in "/dev/$misc_name" "/dev/block/$misc_name"; do
            if [ -b "$misc_dev" ]; then
                printf '%s\n' "$misc_dev"
                return 0
            fi
        done
    done
    return 1
}

minimal_bcb_asks_recovery() {
    misc_dev=$(minimal_misc_device) || return 1
    misc_head=$(timeout 5 head -c 16 "$misc_dev" 2>/dev/null | tr -d '\0')
    [ "$misc_head" = boot-recovery ]
}

# Clear a recovery request left over from an earlier boot.
#
# "One request, one boot" is the property that makes the recovery path safe, and
# without this the production image does NOT have it.  The sequence it prevents:
#
#   1. the handoff fails, writes the BCB, and reboots;
#   2. ABL reads it and starts TWRP - the goal;
#   3. the owner fixes the card in TWRP and reboots to system;
#   4. if nothing cleared the block, ABL reads boot-recovery AGAIN and goes back
#      to TWRP, and the only way out is from TWRP.
#
# TWRP may or may not clear it - that is somebody else's implementation and not
# something to depend on - so this clears it itself.  The debug image has always
# done this (clear_stale_bcb in boot/bringup-init.sh, before boot_rootfs); this is
# the same rule, and it runs BEFORE the root handoff so a normal boot always
# consumes any stale request.
#
# A failure here is not fatal and must not be: the boot is otherwise healthy, and
# the worst case of leaving the block set is one extra trip through TWRP.
minimal_clear_stale_bcb() {
    misc_dev=$(minimal_misc_device) || return 0
    misc_head=$(timeout 5 head -c 16 "$misc_dev" 2>/dev/null | tr -d '\0')
    [ "$misc_head" = boot-recovery ] || return 0
    if timeout 5 head -c 2048 /dev/zero > "$misc_dev" 2>/dev/null; then
        sync
        minimal_emit "cleared a stale recovery BCB in $misc_dev (one request, one boot)"
    else
        minimal_emit "WARN: could not clear the stale recovery BCB in $misc_dev"
    fi
    return 0
}

minimal_reboot_to_recovery() {
    if minimal_bcb_asks_recovery; then
        minimal_emit 'WARN: misc already asks for recovery and the bootloader did not act; powering off instead of looping'
        poweroff -f 2>/dev/null || reboot -f 2>/dev/null || true
        return 1
    fi
    misc_dev=$(minimal_misc_device) || {
        minimal_emit "WARN: no 'misc' partition; cannot ask for recovery"
        return 1
    }
    # One zeroed 2048-byte block with the command at offset 0, written the same way
    # the debug image and boot/gts9-debian-to-recovery.sh write it, so all three
    # are byte-identical requests.
    if ! timeout 5 head -c 2048 /dev/zero > "$misc_dev" 2>/dev/null; then
        minimal_emit "WARN: could not clear the BCB in $misc_dev"
        return 1
    fi
    if ! printf 'boot-recovery' | timeout 5 dd of="$misc_dev" bs=1 conv=notrunc 2>/dev/null; then
        minimal_emit "WARN: could not write the BCB to $misc_dev"
        return 1
    fi
    sync
    minimal_emit "BCB written to $misc_dev: command=boot-recovery"
    # Read back through the same path the bootloader will use.  A request that did
    # not land is worse than no request: the reset would look like a boot loop.
    misc_check=$(timeout 5 head -c 13 "$misc_dev" 2>/dev/null)
    if [ "$misc_check" != boot-recovery ]; then
        minimal_emit 'WARN: the BCB read-back does not match; not rebooting'
        return 1
    fi
    minimal_emit 'rebooting into recovery (TWRP)'
    sync
    # A PLAIN restart: no mode string, because the request is already in the BCB.
    reboot -f 2>/dev/null || poweroff -f 2>/dev/null || true
    return 0
}

minimal_rescue_shell() {
    minimal_emit 'GTS9_MINIMAL_RESCUE=BusyBox shell'
    minimal_emit 'root device missing or handoff failed; inspect the block state below'
    # Lead with the practical consequence.  There is no USB serial port any more
    # and this initramfs has no network at all, so an owner who lands in this shell
    # and then looks for an ssh session or a COM port on their host will find
    # neither - and the message must say so before they spend time looking.
    minimal_emit 'network may not be available before Debian starts;'
    minimal_emit 'use tty1 or offline TWRP inspection'
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
    # No network and no serial port here, so the only ways on are the shell below
    # and the escape hatches.  Say so, because someone staring at a tablet that
    # will not boot needs to know what their options actually are.
    minimal_emit 'rescue shell: /bin/sh -i (type exit to restart it)'
    minimal_emit 'to leave: reboot   (or: poweroff)'
    minimal_emit 'to fix the root device: reboot into TWRP and check gts9_rootfs='
    # This is the only boot where the panel might be dark, so try to light it
    # before anything reads the screen.
    minimal_panel_rescue
    # Then hand the device somewhere it can actually be repaired.  Clear the BCB
    # first so the request is exactly one boot: if this loop is ever re-entered
    # with a stale request, minimal_reboot_to_recovery() sees it and powers off
    # rather than looping.
    if [ "${GTS9_MINIMAL_RESCUE_ACTION:-reboot-recovery}" = reboot-recovery ]; then
        minimal_emit 'rescue: asking the bootloader for recovery so this is fixable'
        if minimal_reboot_to_recovery; then
            # Only reached if the reset did not happen; fall through to the shell
            # rather than spin.
            minimal_emit 'WARN: recovery reboot returned; continuing in the shell'
        fi
    else
        minimal_emit "rescue: GTS9_MINIMAL_RESCUE_ACTION=${GTS9_MINIMAL_RESCUE_ACTION}; staying in the shell"
    fi

    # Keep PID 1 alive if an owner exits the interactive shell.  This path does
    # not depend on USB: it uses the panel VT, with /dev/console only as a
    # fallback.  Preferring tty1 over /dev/console is deliberate - see the long
    # note at the end of boot/bringup-init.sh: /dev/console used to be the USB ACM
    # gadget port, and writing to it from PID 1 blocks once nobody drains it.
    # With the serial consoles removed it can no longer resolve to ttyGS, but the
    # rescue shell is the last line of defence and must not depend on that.
    #
    # Bounded, not busy: each branch either runs an interactive shell (which blocks
    # until the owner exits it) or sleeps, and the no-console fallback emits one
    # heartbeat line per iteration rather than spinning.  It never waits for a
    # ttyGS - that device cannot appear - and never tries to create a gadget shell.
    while :; do
        if [ -c /dev/tty1 ]; then
            /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
        elif [ -c /dev/console ]; then
            /bin/sh -i </dev/console >/dev/console 2>&1
        else
            minimal_emit 'no usable console for the rescue shell; waiting'
            sleep 5
            continue
        fi
        sleep 1
    done
}

minimal_fail() {
    minimal_state_fail "$1"
    minimal_rescue_shell
}

# ---------------------------------------------------------------------------
# 4. the remaining pseudo filesystems.  /proc is already mounted above.
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 5. the state library.  It is sourced after /proc and /run exist because it
#    writes its first record into /run and reads /proc/uptime; sourcing it
#    earlier would leave those readings empty rather than failing.
# ---------------------------------------------------------------------------
if [ -r "$MINIMAL_STATE_LIB" ]; then
    . "$MINIMAL_STATE_LIB"
else
    minimal_emit "GTS9_MINIMAL_WARN=state-library-missing:$MINIMAL_STATE_LIB"
fi

# ---------------------------------------------------------------------------
# 6. root handoff.
# ---------------------------------------------------------------------------
minimal_state_init
minimal_state_stage kernel-userspace

# Consume any recovery request left over from an earlier failed boot, so that a
# normal boot is never sent back to TWRP by a stale block.  This sits on the
# healthy path on purpose: it is the only place that runs on every boot, and the
# request must be consumed by exactly one boot.  It costs one sysfs read and, in
# the overwhelmingly common case where the block is already clear, nothing else.
minimal_clear_stale_bcb

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

# The static trampoline (boot/gts9-minimal-pid1.c) is OPT-IN and defaults to off.
# It exists to leave a post-switch_root watchdog trace, and test 178 boot #3 showed
# it can hang the tablet hard enough that no key combination reaches TWRP, so the
# direct /sbin/init path is the proven default.
#
# Staging it is therefore conditional, and that is a reliability fix rather than a
# size one.  This block used to run unconditionally: with MINIMAL_INIT=/sbin/init
# the helper and BusyBox were still copied into /run, and - worse - if either copy
# or the chmod failed, the boot was aborted with `minimal_fail
# switch-root-returned`.  So a normal, otherwise perfectly healthy boot could fail
# because a helper it was never going to execute could not be staged.  Now the
# default path skips all of it: no copy, no BusyBox copy, no selftest, no
# existence check later on.
if [ "$MINIMAL_INIT" = /run/gts9-minimal-pid1 ]; then
    if ! cp /sbin/gts9-minimal-pid1 /run/gts9-minimal-pid1 ||
       ! cp /bin/busybox /run/busybox ||
       ! chmod 0755 /run/gts9-minimal-pid1 /run/busybox; then
        minimal_emit 'could not stage the minimal PID 1 rescue helper'
        minimal_emit 'falling back to the direct /sbin/init handoff'
        MINIMAL_INIT=/sbin/init
    fi
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
