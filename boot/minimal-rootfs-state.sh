#!/bin/sh
# Persistent boot-stage record for the gts9_minimal_rootfs=1 profile.
#
# Sourced by /minimal-rootfs-init (boot/minimal-rootfs-init.sh).  The record is
# written to the Debian root filesystem, so it is the only boot evidence that
# survives a black panel and an absent USB console.  Before the root filesystem
# is mounted there is nowhere to persist anything: the stage history is kept in
# RAM and emitted on /dev/kmsg and /dev/console, then written to Debian in one
# piece as soon as the mount succeeds.
#
# The write path is atomic: a temporary file next to the record is written,
# chmod'ed and synced, and only then renamed over the record.  The record is
# never truncated in place, so a reader (TWRP, or Debian after a later stage)
# always sees a complete file.
#
# Host tests source this file with GTS9_MINIMAL_LOG_DIR pointing at a writable
# directory; nothing here requires a real initramfs.

GTS9_MINIMAL_FORMAT_VERSION=${GTS9_MINIMAL_FORMAT_VERSION:-1}
GTS9_MINIMAL_LOG_DIR=${GTS9_MINIMAL_LOG_DIR:-/newroot/var/log}
GTS9_MINIMAL_RECORD=${GTS9_MINIMAL_RECORD:-$GTS9_MINIMAL_LOG_DIR/gts9-minimal-last-boot}
GTS9_MINIMAL_STAGE=${GTS9_MINIMAL_STAGE:-init-start}
GTS9_MINIMAL_STAGE_HISTORY=${GTS9_MINIMAL_STAGE_HISTORY:-}
GTS9_MINIMAL_FAILURE=${GTS9_MINIMAL_FAILURE:-none}
GTS9_MINIMAL_ROOT_DEVICE=${GTS9_MINIMAL_ROOT_DEVICE:-unknown}
GTS9_MINIMAL_PERSIST=${GTS9_MINIMAL_PERSIST:-0}
GTS9_MINIMAL_FIRST_TIMESTAMP=${GTS9_MINIMAL_FIRST_TIMESTAMP:-}
GTS9_MINIMAL_FIRST_UPTIME=${GTS9_MINIMAL_FIRST_UPTIME:-}
GTS9_MINIMAL_FROZEN=${GTS9_MINIMAL_FROZEN:-0}
GTS9_MINIMAL_BOOT_ID=${GTS9_MINIMAL_BOOT_ID:-}
GTS9_MINIMAL_KERNEL_RELEASE=${GTS9_MINIMAL_KERNEL_RELEASE:-}
GTS9_MINIMAL_CMDLINE=${GTS9_MINIMAL_CMDLINE:-}
GTS9_MINIMAL_MMC_DEVICES=${GTS9_MINIMAL_MMC_DEVICES:-}

# Emit one line on every channel that can be reached without DRM, fbcon, tty1
# or USB: stdout, the kernel log, /dev/console and (opportunistically) tty1.
#
# stdout is the panel VT now, not a serial console: the command line has carried
# nothing but `console=tty0` since 2026-09-26.  /dev/console is kept because this
# runs in the initramfs on failure paths where it is the most likely endpoint to
# exist at all, and it can no longer be a port that blocks - with no ttyGS
# console it resolves to tty0 or ttynull.
minimal_emit() {
    minimal_message=$*
    printf '%s\n' "$minimal_message"
    if [ -w /dev/kmsg ]; then
        printf 'gts9-minimal: %s\n' "$minimal_message" > /dev/kmsg 2>/dev/null || true
    fi
    if [ -c /dev/console ]; then
        printf '%s\n' "$minimal_message" > /dev/console 2>/dev/null || true
    fi
    if [ -c /dev/tty1 ]; then
        printf '%s\n' "$minimal_message" > /dev/tty1 2>/dev/null || true
    fi
}

minimal_state_now() {
    date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo unknown
}

minimal_state_uptime() {
    cut -d' ' -f1 /proc/uptime 2>/dev/null || echo unknown
}

minimal_state_boot_id() {
    cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown
}

minimal_state_kernel_release() {
    cat /proc/sys/kernel/osrelease 2>/dev/null || uname -r 2>/dev/null || echo unknown
}

minimal_state_cmdline() {
    cat /proc/cmdline 2>/dev/null || echo unavailable
}

# Every /dev/mmcblk* node that exists at write time.  This is what tells a
# reader in TWRP whether the card appeared at all, and under which name.
minimal_state_mmc_devices() {
    minimal_mmc_devices=''
    for minimal_mmc_device in /dev/mmcblk*; do
        [ -e "$minimal_mmc_device" ] || continue
        minimal_mmc_devices="${minimal_mmc_devices}${minimal_mmc_device},"
    done
    if [ -n "$minimal_mmc_devices" ]; then
        printf '%s' "${minimal_mmc_devices%,}"
        return 0
    fi
    minimal_mmc_hosts=''
    for minimal_mmc_host in /sys/class/mmc_host/*; do
        [ -e "$minimal_mmc_host" ] || continue
        minimal_mmc_hosts="${minimal_mmc_hosts}${minimal_mmc_host##*/},"
    done
    printf 'none(found:hosts=%s)' "${minimal_mmc_hosts%,}"
}

# Capture the boot facts once, as early as /proc is available.
minimal_state_init() {
    GTS9_MINIMAL_FIRST_TIMESTAMP=$(minimal_state_now)
    GTS9_MINIMAL_FIRST_UPTIME=$(minimal_state_uptime)
}

# The boot facts are read from /proc and /dev, which stop being reachable at
# those paths once /dev /proc /sys /run are moved into the Debian root.  Freeze
# them while they are still readable, so the switch-root write - which happens
# after the move - cannot replace real values with "unknown".
minimal_state_freeze_facts() {
    GTS9_MINIMAL_FROZEN=1
    GTS9_MINIMAL_BOOT_ID=$(minimal_state_boot_id)
    GTS9_MINIMAL_KERNEL_RELEASE=$(minimal_state_kernel_release)
    GTS9_MINIMAL_CMDLINE=$(minimal_state_cmdline)
    GTS9_MINIMAL_MMC_DEVICES=$(minimal_state_mmc_devices)
}

# Record a stage before the root filesystem exists: the value is kept in RAM
# and emitted, and nothing is persisted yet.
minimal_state_stage() {
    GTS9_MINIMAL_STAGE=$1
    case ",$GTS9_MINIMAL_STAGE_HISTORY," in
        *",$GTS9_MINIMAL_STAGE,"*)
            # The history is append-only; never grow it with a repeat.
            ;;
        *)
            if [ -n "$GTS9_MINIMAL_STAGE_HISTORY" ]; then
                GTS9_MINIMAL_STAGE_HISTORY="$GTS9_MINIMAL_STAGE_HISTORY,$GTS9_MINIMAL_STAGE"
            else
                GTS9_MINIMAL_STAGE_HISTORY=$GTS9_MINIMAL_STAGE
            fi
            ;;
    esac
    minimal_emit "GTS9_MINIMAL_STAGE=$GTS9_MINIMAL_STAGE"
    minimal_state_write
}

minimal_state_fail() {
    GTS9_MINIMAL_FAILURE=$1
    minimal_emit "GTS9_MINIMAL_FAIL=$GTS9_MINIMAL_FAILURE"
    minimal_emit "GTS9_MINIMAL_LAST_STAGE=$GTS9_MINIMAL_STAGE"
    minimal_state_write
}

# The Debian root filesystem is mounted: persist the whole stage history, then
# keep updating it on every later stage.
minimal_state_persist_enable() {
    GTS9_MINIMAL_LOG_DIR=${1:-$GTS9_MINIMAL_LOG_DIR}
    GTS9_MINIMAL_RECORD=$GTS9_MINIMAL_LOG_DIR/gts9-minimal-last-boot
    GTS9_MINIMAL_PERSIST=1
    minimal_state_freeze_facts
    minimal_emit "GTS9_MINIMAL_RECORD=$GTS9_MINIMAL_RECORD"
    minimal_state_write
}

minimal_state_write() {
    [ "$GTS9_MINIMAL_PERSIST" = 1 ] || return 0

    minimal_state_dir=${GTS9_MINIMAL_RECORD%/*}
    if [ ! -d "$minimal_state_dir" ]; then
        mkdir -p "$minimal_state_dir" 2>/dev/null || {
            minimal_emit 'GTS9_MINIMAL_WARN=state-directory-unavailable'
            return 0
        }
    fi

    minimal_state_tmp="${GTS9_MINIMAL_RECORD}.tmp"
    {
        if [ "$GTS9_MINIMAL_FROZEN" = 1 ]; then
            minimal_state_boot_id_value=$GTS9_MINIMAL_BOOT_ID
            minimal_state_kernel_value=$GTS9_MINIMAL_KERNEL_RELEASE
            minimal_state_cmdline_value=$GTS9_MINIMAL_CMDLINE
            minimal_state_mmc_value=$GTS9_MINIMAL_MMC_DEVICES
        else
            minimal_state_boot_id_value=$(minimal_state_boot_id)
            minimal_state_kernel_value=$(minimal_state_kernel_release)
            minimal_state_cmdline_value=$(minimal_state_cmdline)
            minimal_state_mmc_value=$(minimal_state_mmc_devices)
        fi
        printf 'format_version=%s\n' "$GTS9_MINIMAL_FORMAT_VERSION"
        printf 'origin=initramfs\n'
        printf 'boot_id=%s\n' "$minimal_state_boot_id_value"
        printf 'kernel_release=%s\n' "$minimal_state_kernel_value"
        printf 'cmdline=%s\n' "$minimal_state_cmdline_value"
        printf 'timestamp=%s\n' "${GTS9_MINIMAL_FIRST_TIMESTAMP:-unknown}"
        printf 'uptime_seconds=%s\n' "${GTS9_MINIMAL_FIRST_UPTIME:-unknown}"
        printf 'root_device=%s\n' "$GTS9_MINIMAL_ROOT_DEVICE"
        printf 'stage=%s\n' "$GTS9_MINIMAL_STAGE"
        printf 'stage_history=%s\n' "${GTS9_MINIMAL_STAGE_HISTORY:-$GTS9_MINIMAL_STAGE}"
        printf 'failure=%s\n' "$GTS9_MINIMAL_FAILURE"
        printf 'mmc_devices=%s\n' "$minimal_state_mmc_value"
    } > "$minimal_state_tmp" 2>/dev/null || {
        rm -f "$minimal_state_tmp" 2>/dev/null || true
        minimal_emit 'GTS9_MINIMAL_WARN=state-write-failed'
        return 0
    }

    chmod 0644 "$minimal_state_tmp" 2>/dev/null || true
    # Flush the temporary file before the rename, so the record never points at
    # data that is still only in the page cache.
    sync
    if ! mv -f "$minimal_state_tmp" "$GTS9_MINIMAL_RECORD" 2>/dev/null; then
        rm -f "$minimal_state_tmp" 2>/dev/null || true
        minimal_emit 'GTS9_MINIMAL_WARN=state-rename-failed'
        return 0
    fi
    sync
    return 0
}
