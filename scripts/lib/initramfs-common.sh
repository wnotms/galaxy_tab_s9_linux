#!/usr/bin/env bash
# Shared helpers for the two initramfs builders.
#
# Sourced, not executed: scripts/build-bringup-initramfs.sh (debug) and
# scripts/build-minimal-initramfs.sh (production) both need the same pinned
# BusyBox, the same static-ELF checks and the same applet-symlink logic.  Keeping
# one copy means the two images cannot drift in how they are built, which is the
# whole point of splitting them by responsibility rather than by script.
#
# Every function here assumes the caller has set up:
#   repo_root, workdir, download_dir, tmp
# and, for the BusyBox ones, that `bb_bin` is the verified static aarch64 binary.

# Every failure in this library goes through gts9_fail, defined here rather than by
# the caller.  The two builders each used to define their own `fail`, and one of
# them lost it during the refactor into this file - which is not a shell syntax
# error, so the script would have failed at its first error path instead, on the
# device.  Defining it here removes that class of mistake.
gts9_fail() {
    echo "error: $*" >&2
    exit 1
}

# The pinned BusyBox: Ubuntu 24.04 arm64 busybox-static 1.36.1-6ubuntu3.1,
# verified by the SHA-256 of both the .deb and the extracted /bin/busybox.
# Nothing here ever fetches "latest"; a mismatch fails closed.
gts9_busybox_url=https://ports.ubuntu.com/ubuntu-ports/pool/main/b/busybox/busybox-static_1.36.1-6ubuntu3.1_arm64.deb
gts9_busybox_deb_sha256=d96535e0402c011e0ee43449799df2f4504d44b842e4f2b3a6cbc845508eaafc
gts9_busybox_bin_sha256=52151e7f322f926b64049cdaa1410dc3ea6485525e0624b05813791c219ae933

# gts9_verify_busybox BIN EXPECTED_SHA256 LABEL
#
# Rejects a dynamic binary and a non-aarch64 one, and checks the SHA-256 unless
# the expected value is "-" (the caller passed --busybox explicitly and takes
# responsibility for it).  Applet presence is checked separately, because the two
# builds need different applet sets.
gts9_verify_busybox() {
    local bin=$1 expected=$2 label=${3:-$1} actual

    [ -f "$bin" ] || gts9_fail "busybox not found: $bin"
    if [ "$expected" != - ]; then
        actual=$(sha256sum "$bin" | cut -d' ' -f1)
        [ "$actual" = "$expected" ] || {
            gts9_fail "$label SHA-256 mismatch (expected $expected, got $actual)"
        }
    fi
    readelf -h "$bin" | grep -q 'Machine:.*AArch64' || \
        gts9_fail "$label is not an aarch64 ELF"
    if readelf -l "$bin" 2>/dev/null | grep -q 'INTERP'; then
        gts9_fail "$label is dynamically linked; a static BusyBox is required"
    fi
}

# gts9_obtain_busybox LOCAL_ARG
#
# Sets bb_bin to a verified static aarch64 BusyBox.  With LOCAL_ARG empty it uses
# the pinned .deb from the cache or downloads it; either way the extracted binary
# is checked against the pinned hash.
gts9_obtain_busybox() {
    local local_arg=$1 deb member

    if [ -n "$local_arg" ]; then
        echo "using local busybox: $local_arg"
        gts9_verify_busybox "$local_arg" - "$local_arg"
        bb_bin=$local_arg
        return 0
    fi

    deb=$download_dir/$(basename "$gts9_busybox_url")
    mkdir -p "$download_dir"
    if [ -f "$deb" ] && \
       [ "$(sha256sum "$deb" | cut -d' ' -f1)" = "$gts9_busybox_deb_sha256" ]; then
        echo "using cached $(basename "$deb")"
    else
        command -v curl >/dev/null || gts9_fail 'curl is required to download BusyBox'
        echo "downloading $(basename "$gts9_busybox_url")"
        curl -fsSL -o "$deb.tmp" "$gts9_busybox_url" || \
            gts9_fail "cannot download $gts9_busybox_url (failing closed)"
        local actual
        actual=$(sha256sum "$deb.tmp" | cut -d' ' -f1)
        [ "$actual" = "$gts9_busybox_deb_sha256" ] || {
            rm -f "$deb.tmp"
            gts9_fail "downloaded BusyBox archive has SHA-256 $actual, expected $gts9_busybox_deb_sha256"
        }
        mv "$deb.tmp" "$deb"
    fi

    mkdir -p "$tmp/deb"
    if command -v dpkg-deb >/dev/null 2>&1; then
        dpkg-deb -x "$deb" "$tmp/deb"
    else
        command -v ar >/dev/null || gts9_fail 'need dpkg-deb or ar to unpack the BusyBox archive'
        member=$(ar t "$deb" | grep '^data\.tar' | head -1)
        [ -n "$member" ] || gts9_fail "no data.tar member in $deb"
        ar p "$deb" "$member" | tar -x -C "$tmp/deb"
    fi

    bb_bin=$(find "$tmp/deb" -type f -path '*/bin/busybox' | head -1)
    [ -n "$bb_bin" ] || gts9_fail "no */bin/busybox inside $deb"
    gts9_verify_busybox "$bb_bin" "$gts9_busybox_bin_sha256" "packaged busybox"
}

# gts9_busybox_applets BIN OUTFILE
#
# Dump BusyBox's packed applet-name string table.  This is how applet presence is
# checked without executing a foreign-architecture binary: the names are present
# as strings in every BusyBox build.
gts9_busybox_applets() {
    local bin=$1 outfile=$2
    strings -a -n 1 "$bin" > "$outfile"
}

# gts9_require_applets APPLETS_FILE "applet list" LABEL
#
# Fails when a required applet is missing.  A silently absent applet is exactly
# the kind of failure that only shows up mid-boot on the device, so anything the
# script cannot do without is required here instead.
gts9_require_applets() {
    local applets_file=$1 list=$2 label=${3:-this build} applet
    for applet in $list; do
        grep -Fqx -- "$applet" "$applets_file" || \
            gts9_fail "$label does not provide the required applet '$applet'"
    done
}

# gts9_link_applets TREE "applets" "sbin-applets"
#
# Creates the applet symlinks, putting the ones that belong in /sbin there.
# Returns the list of applets this BusyBox does not have on stdout, so the caller
# can report them without failing.
gts9_link_applets() {
    local tree=$1 list=$2 sbin_list=$3 applet dir target missing=

    for applet in $list; do
        if grep -Fqx -- "$applet" "$tmp/applets.txt"; then
            dir=bin
            target=busybox
            case " $sbin_list " in
                *" $applet "*) dir=sbin; target=../bin/busybox ;;
            esac
            ln -sf "$target" "$tree/$dir/$applet"
        else
            missing="$missing $applet"
        fi
    done
    printf '%s\n' "$missing"
}

# gts9_write_manifest ...
#
# Writes <image>.manifest next to the image.  Both profiles use the same key set
# so a reader (or a test) can compare them mechanically instead of inferring the
# profile from the filename - which is the mistake this is here to prevent.
#
# Usage: gts9_write_manifest IMAGE PROFILE TREE BUSYBOX MODULES_DIR FIRMWARE_DIR
gts9_write_manifest() {
    local image=$1 profile=$2 tree=$3 busybox=$4 modules=$5 firmware=$6
    local manifest="${image}.manifest"
    local compressed unpacked regs links dirs bb_sha

    compressed=$(stat -c %s "$image")
    unpacked=$(du -sb "$tree" | awk '{print $1}')
    regs=$(find "$tree" -type f | wc -l)
    links=$(find "$tree" -type l | wc -l)
    dirs=$(find "$tree" -type d | wc -l)
    bb_sha=$(sha256sum "$busybox" | cut -d' ' -f1)

    # Does the packed tree carry a module directory or firmware blobs?  Both are
    # recorded as facts so a validator can refuse them in a production image
    # without having to unpack and guess.
    local has_modules=no has_firmware=no fw_bytes=0
    [ -d "$tree/lib/modules" ] && has_modules=yes
    if [ -d "$tree/lib/firmware" ] && [ -n "$(find "$tree/lib/firmware" -type f 2>/dev/null | head -1)" ]; then
        has_firmware=yes
        fw_bytes=$(du -sb "$tree/lib/firmware" | awk '{print $1}')
    fi

    # Capability probes.  Each looks for the OPERATION rather than the noun, so
    # the comments that explain why a capability is gone do not read as evidence
    # that it is present.
    local init_file=$tree/init
    local gadget=no msc=no gpt=no rtc=no bcb=no display=no report=no
    # Creating a configfs gadget means creating the directory or writing the UDC.
    if grep -qE 'mkdir.*usb_gadget' "$init_file" 2>/dev/null ||
       grep -qE '> *"\$(G|GADGET)/UDC"' "$init_file" 2>/dev/null; then
        gadget=yes
    fi
    grep -q 'mass_storage\.usb0' "$init_file" 2>/dev/null && msc=yes
    grep -qE '/dev/disk/by-partlabel|PARTNAME' "$init_file" 2>/dev/null && gpt=yes
    grep -qE '/dev/rtc|rtc-state' "$init_file" 2>/dev/null && rtc=yes
    grep -qiE 'boot-recovery' "$init_file" 2>/dev/null && bcb=yes
    grep -qE 'fb0/blank|display_recover' "$init_file" 2>/dev/null && display=yes
    grep -qE 'regulator_summary|devices_deferred|bringup-report' "$init_file" 2>/dev/null && report=yes

    # Which source script is /init, identified by content: the builders copy a
    # source to /init, so the name in the image is always "init" and tells you
    # nothing.
    local init_source=unknown
    if grep -q 'MINIMAL_ROOTFS=' "$init_file" 2>/dev/null &&
       grep -q 'setup_usb_gadget\|display_recover' "$init_file" 2>/dev/null; then
        init_source=bringup-init.sh
    elif grep -q 'ROOTFS_DEVICE=' "$init_file" 2>/dev/null &&
         grep -q 'minimal_state_stage' "$init_file" 2>/dev/null; then
        init_source=minimal-rootfs-init.sh
    fi

    {
        printf 'profile=%s\n' "$profile"
        printf 'compressed_size=%s\n' "$compressed"
        printf 'unpacked_size=%s\n' "$unpacked"
        printf 'regular_files=%s\n' "$regs"
        printf 'symlinks=%s\n' "$links"
        printf 'directories=%s\n' "$dirs"
        printf 'busybox_sha256=%s\n' "$bb_sha"
        printf 'contains_modules=%s\n' "$has_modules"
        printf 'contains_firmware=%s\n' "$has_firmware"
        printf 'firmware_bytes=%s\n' "$fw_bytes"
        printf 'contains_usb_gadget=%s\n' "$gadget"
        printf 'contains_msc=%s\n' "$msc"
        printf 'contains_gpt_parser=%s\n' "$gpt"
        printf 'contains_rtc_telemetry=%s\n' "$rtc"
        printf 'contains_bcb_write=%s\n' "$bcb"
        printf 'contains_display_recovery=%s\n' "$display"
        printf 'contains_hardware_report=%s\n' "$report"
        printf 'init_source=%s\n' "$init_source"
        printf 'sha256=%s\n' "$(sha256sum "$image" | cut -d' ' -f1)"
    } > "$manifest"

    # `modules`/`firmware` are accepted so callers read naturally; the facts above
    # come from the tree, which is what actually got packed.
    : "$modules" "$firmware"
    printf 'manifest: %s\n' "$manifest"
}

# gts9_fail is defined by the caller so the message prefix matches the script.
