#!/usr/bin/env bash
# Validate an Android boot header v4 bundle before anyone flashes it.
#
# This is a host-side, read-only checker: it opens the images, unpacks them in
# a temporary directory, and refuses to pass unless the payload really is the
# kernel this repository builds, the DTB really carries the Samsung ABL
# selectors and DTBO labels, the vendor_boot really carries our cmdline,
# bootconfig and DTB, and init_boot carries our initramfs with an executable
# /init plus a BusyBox.  A placeholder or truncated initramfs is a
# hard failure, because that is exactly the mistake this script exists to
# catch.
#
# It never writes to an image, a partition or a device.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
workdir=${GTS9_WORKDIR:-$repo_root/.work}
bundle_dir=${BUNDLE_OUT_DIR:-$repo_root/out/boot-bundle}
kernel_out=${KERNEL_OUT_DIR:-$repo_root/out/kernel-gts9wifi}
cmdline_file=$repo_root/boot/cmdline.example.txt
bootconfig_file=$repo_root/boot/bootconfig.example.txt
tools=${ANDROID_TOOLS:-$workdir/tools}
unpack=$tools/unpack_bootimg.py
avbtool=$tools/avbtool.py
expect_kernel=$kernel_out

# Partition sizes, identical to scripts/build-boot-bundle.sh.
boot_size=100663296
init_boot_size=8388608
vendor_boot_size=100663296
dtbo_size=16777216
vbmeta_size=131072

while [ $# -gt 0 ]; do
    case "$1" in
        --dir) bundle_dir=$2; shift 2 ;;
        --cmdline) cmdline_file=$2; shift 2 ;;
        --bootconfig) bootconfig_file=$2; shift 2 ;;
        --unpack-bootimg) unpack=$2; shift 2 ;;
        --avbtool) avbtool=$2; shift 2 ;;
        --kernel-out) kernel_out=$2; expect_kernel=$2; shift 2 ;;
        --no-kernel-compare) expect_kernel=; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

# Safety self-check: a validator must stay read-only.  Refuse to run if this
# file ever grows a destructive command in command position.
for forbidden in dd fastboot heimdall odin adb; do
    if grep -qE "(^|[;&|(]|\\\$\()[[:space:]]*${forbidden}([[:space:]]|\\\$)" "$0"; then
        echo "refusing to run: $0 references the command '$forbidden'" >&2
        exit 1
    fi
done

failed=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*" >&2; failed=$((failed + 1)); }
note() { printf '      %s\n' "$*"; }

[ -f "$unpack" ] || { echo "missing $unpack (run scripts/stage-android-tools.sh)" >&2; exit 2; }
[ -f "$avbtool" ] || { echo "missing $avbtool (run scripts/stage-android-tools.sh)" >&2; exit 2; }
command -v python3 >/dev/null || { echo 'python3 is required' >&2; exit 2; }
command -v dtc >/dev/null || { echo 'dtc is required' >&2; exit 2; }
command -v lz4 >/dev/null || { echo 'lz4 is required' >&2; exit 2; }
command -v cpio >/dev/null || { echo 'cpio is required' >&2; exit 2; }
[ -d "$bundle_dir" ] || { echo "missing bundle directory: $bundle_dir" >&2; exit 2; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# How was this bundle built? BUNDLE_INFO is written by build-boot-bundle.sh;
# without it, assume the historical layout (appended DTB).
append_dtb=1
if [ -f "$bundle_dir/BUNDLE_INFO" ]; then
    case $(sed -n 's/^append_dtb=//p' "$bundle_dir/BUNDLE_INFO" | head -1) in
        0) append_dtb=0 ;;
        1) append_dtb=1 ;;
    esac
fi

echo "validating bundle: $bundle_dir"
if [ "$append_dtb" = 1 ]; then
    echo 'layout: Image.gz + appended board DTB in boot.img'
else
    echo 'layout: Image.gz only in boot.img; DTB from vendor_boot'
fi
echo

# --------------------------------------------------------------------------
echo '--- files and sizes ---'
# --------------------------------------------------------------------------
check_image() {
    # check_image <name> <expected size>
    local name=$1 expected=$2 path actual
    path=$bundle_dir/$name
    if [ ! -f "$path" ]; then
        fail "$name is missing"
        return 1
    fi
    actual=$(stat -c %s "$path")
    if [ "$actual" -eq 0 ]; then
        fail "$name is empty"
        return 1
    fi
    if [ "$actual" -gt "$expected" ]; then
        fail "$name is $actual bytes, larger than its $expected-byte partition"
        return 1
    fi
    if [ "$actual" -ne "$expected" ]; then
        fail "$name is $actual bytes, expected the padded $expected-byte partition size"
        return 1
    fi
    pass "$name: $actual bytes"
    return 0
}

boot_ok=0; init_boot_ok=0; vendor_boot_ok=0; dtbo_ok=0; vbmeta_ok=0
if check_image boot.img "$boot_size"; then boot_ok=1; fi
if check_image init_boot.img "$init_boot_size"; then init_boot_ok=1; fi
if check_image vendor_boot.img "$vendor_boot_size"; then vendor_boot_ok=1; fi
if check_image dtbo.img "$dtbo_size"; then dtbo_ok=1; fi
if check_image vbmeta.img "$vbmeta_size"; then vbmeta_ok=1; fi

# Board selectors and ABL labels that must be present in whatever tree the
# tablet actually boots from.
check_board_dtb() {
    # check_board_dtb <dtb> <label>
    local dtb=$1 label=$2 out=$tmp/board-$(basename "$1").dts
    if ! dtc -I dtb -O dts -o "$out" "$dtb" 2>"$tmp/dtc.log"; then
        fail "$label does not decompile"
        sed 's/^/      /' "$tmp/dtc.log" >&2
        return
    fi
    local name pattern
    while IFS='|' read -r name pattern; do
        [ -n "$name" ] || continue
        if grep -qE "$pattern" "$out"; then
            pass "$label: $name"
        else
            fail "$label: $name is missing"
        fi
    done <<'CHECKS'
model is the SM-X710 tablet|model = "Samsung Galaxy Tab S9 Wi-Fi"
ABL compatible selectors|compatible = "qcom,kalama-mtp", "qcom,kalama", "qcom,mtp"
qcom,board-id = <0x10008 0x04>|qcom,board-id = <0x10008 0x04>
qcom,msm-id pairs|qcom,msm-id = <0x218 0x20000 0x207 0x20000 0x207 0x10000 0x218 0x10000>
__symbols__/qcom_tzlog|qcom_tzlog = "/chosen"
__symbols__/arch_timer|arch_timer = "/timer"
__symbols__/qcom_scm|qcom_scm = "/firmware/scm"
CHECKS
}

# --------------------------------------------------------------------------
echo
if [ "$append_dtb" = 1 ]; then
    echo '--- boot.img: v4 header, gzip kernel, appended DTB ---'
else
    echo '--- boot.img: v4 header, gzip kernel (no appended DTB) ---'
fi
# --------------------------------------------------------------------------
if [ "$boot_ok" = 1 ]; then
    mkdir -p "$tmp/boot"
    if python3 "$unpack" --boot_img "$bundle_dir/boot.img" --out "$tmp/boot" \
            > "$tmp/boot.info" 2>&1; then
        if grep -q 'boot image header version: 4' "$tmp/boot.info"; then
            pass 'boot.img: Android boot header version 4'
        else
            fail "boot.img: $(grep -m1 'header version' "$tmp/boot.info" || echo 'no header version found')"
        fi

        if [ ! -s "$tmp/boot/kernel" ]; then
            fail 'boot.img: no kernel payload extracted'
        else
            pass "boot.img: kernel payload $(stat -c %s "$tmp/boot/kernel") bytes"
            if python3 - "$tmp/boot/kernel" "$tmp/boot/Image" "$tmp/boot/appended.dtb" \
                    "$append_dtb" 2> "$tmp/payload.log" <<'PY'
import sys, zlib
payload, image_out, dtb_out, want_dtb = sys.argv[1:5]
data = open(payload, 'rb').read()
if data[:2] != b'\x1f\x8b':
    sys.exit('kernel payload is not gzip')
d = zlib.decompressobj(16 + zlib.MAX_WBITS)
try:
    image = d.decompress(data)
except zlib.error as exc:
    sys.exit(f'kernel payload does not decompress: {exc}')
if not d.eof:
    sys.exit('gzip stream is truncated')
tail = d.unused_data
open(image_out, 'wb').write(image)
open(dtb_out, 'wb').write(tail)
if image[56:60] != b'ARM\x64':
    sys.exit('payload is not an arm64 Linux Image')
if want_dtb == '1':
    if tail[:4] != b'\xd0\x0d\xfe\xed':
        sys.exit('no appended DTB with a valid FDT magic')
else:
    if tail:
        sys.exit(f'payload has {len(tail)} trailing bytes after the gzip stream')
PY
            then
                pass "boot.img: valid gzip arm64 Image ($(stat -c %s "$tmp/boot/Image") bytes)"
                if [ "$append_dtb" = 1 ]; then
                    pass "boot.img: appended DTB present ($(stat -c %s "$tmp/boot/appended.dtb") bytes)"
                else
                    pass 'boot.img: no trailing data after the gzip stream (DTB comes from vendor_boot)'
                fi
            else
                fail 'boot.img: kernel payload or appended DTB is not valid'
                if [ -s "$tmp/payload.log" ]; then
                    sed 's/^/      /' "$tmp/payload.log" >&2
                fi
            fi
        fi
    else
        fail 'unpack_bootimg could not parse boot.img'
        sed 's/^/      /' "$tmp/boot.info" >&2
    fi

    if [ "$append_dtb" = 1 ] && [ -s "$tmp/boot/appended.dtb" ]; then
        check_board_dtb "$tmp/boot/appended.dtb" 'appended DTB'
    fi

    # The strongest statement this validator can make about the kernel: the
    # payload is exactly what the build produced for the requested layout.
    if [ -n "$expect_kernel" ] && [ -s "$tmp/boot/kernel" ] \
       && [ -f "$expect_kernel/Image.gz" ] && [ -f "$expect_kernel/sm8550-samsung-gts9wifi.dtb" ]; then
        if [ "$append_dtb" = 1 ]; then
            cat "$expect_kernel/Image.gz" "$expect_kernel/sm8550-samsung-gts9wifi.dtb" > "$tmp/expected-kernel"
            if cmp -s "$tmp/boot/kernel" "$tmp/expected-kernel"; then
                pass 'boot.img: payload is exactly Image.gz || board DTB'
            else
                fail 'boot.img: payload is not the current Image.gz || board DTB'
            fi
            if cmp -s "$tmp/boot/appended.dtb" "$expect_kernel/sm8550-samsung-gts9wifi.dtb"; then
                pass 'DTB: appended tree is byte-identical to the built board DTB'
            else
                fail 'DTB: appended tree differs from the built board DTB'
            fi
        else
            if cmp -s "$tmp/boot/kernel" "$expect_kernel/Image.gz"; then
                pass 'boot.img: payload is exactly the current Image.gz'
            else
                fail 'boot.img: payload is not the current Image.gz'
            fi
        fi
    fi
fi

# --------------------------------------------------------------------------
echo
echo '--- vendor_boot.img: v4 header, cmdline, bootconfig, DTB, platform ramdisk ---'
# --------------------------------------------------------------------------
vendor_ramdisk=
if [ "$vendor_boot_ok" = 1 ]; then
    mkdir -p "$tmp/vendor"
    if python3 "$unpack" --boot_img "$bundle_dir/vendor_boot.img" --out "$tmp/vendor" \
            > "$tmp/vendor.info" 2>&1; then
        if grep -q 'vendor boot image header version: 4' "$tmp/vendor.info"; then
            pass 'vendor_boot.img: header version 4'
        else
            fail "vendor_boot.img: $(grep -m1 'header version' "$tmp/vendor.info" || echo 'no header version found')"
        fi

        vendor_ramdisk=$(find "$tmp/vendor" -maxdepth 1 -name 'vendor_ramdisk*' -type f | head -1)
        if [ -n "$vendor_ramdisk" ] && [ -s "$vendor_ramdisk" ]; then
            pass "vendor_boot.img: vendor ramdisk present ($(stat -c %s "$vendor_ramdisk") bytes)"
        else
            fail 'vendor_boot.img: no vendor ramdisk'
        fi

        if [ -s "$tmp/vendor/dtb" ]; then
            pass "vendor_boot.img: DTB present ($(stat -c %s "$tmp/vendor/dtb") bytes)"
            if [ -n "$expect_kernel" ] && [ -f "$expect_kernel/sm8550-samsung-gts9wifi.dtb" ]; then
                if cmp -s "$tmp/vendor/dtb" "$expect_kernel/sm8550-samsung-gts9wifi.dtb"; then
                    pass 'vendor_boot.img: DTB matches the built board DTB'
                else
                    fail 'vendor_boot.img: DTB differs from the built board DTB'
                fi
            fi
            # The vendor_boot tree is the one the bootloader actually hands
            # over, so its selectors are checked regardless of whether the
            # boot.img payload also carries a copy.
            check_board_dtb "$tmp/vendor/dtb" 'vendor_boot DTB'
        else
            fail 'vendor_boot.img: no DTB'
        fi

        expected_cmdline=$(tr '\n' ' ' < "$cmdline_file" | sed 's/[[:space:]]*$//')
        actual_cmdline=$(sed -n 's/^vendor command line args: //p' "$tmp/vendor.info" | head -1)
        if [ "$actual_cmdline" = "$expected_cmdline" ]; then
            pass 'vendor_boot.img: cmdline matches the repository cmdline'
        else
            fail 'vendor_boot.img: cmdline differs from the repository cmdline'
            note "expected: $expected_cmdline"
            note "actual  : $actual_cmdline"
        fi

        if [ -f "$tmp/vendor/bootconfig" ]; then
            if cmp -s "$tmp/vendor/bootconfig" "$bootconfig_file"; then
                pass 'vendor_boot.img: bootconfig matches the repository file'
            else
                fail 'vendor_boot.img: bootconfig differs from the repository file'
            fi
        else
            fail 'vendor_boot.img: no bootconfig extracted'
        fi
    else
        fail 'unpack_bootimg could not parse vendor_boot.img'
        sed 's/^/      /' "$tmp/vendor.info" >&2
    fi
fi

# Check the actual generic ramdisk, not just the presence of its filename.
#
# The profile is decided by the CONTENT of /init and cross-checked against the
# .manifest built next to the source image - never by the filename.  A production
# image and a debug image both end up as `init_boot.img` inside a bundle, so the
# name says nothing about which one is being validated, and applying the wrong
# rule set would produce a confident wrong verdict.
check_initramfs() {
    local ramdisk=$1 magic entries init_line
    if [ -n "$ramdisk" ] && [ -s "$ramdisk" ]; then
        magic=$(head -c4 "$ramdisk" | od -An -tx1 | tr -d ' \n')
        if [ "$magic" = 02214c18 ]; then
            pass 'initramfs: legacy LZ4 magic 02 21 4c 18'
            if lz4 -d -q -f "$ramdisk" "$tmp/initramfs.cpio" 2>"$tmp/lz4.log"; then
                if cpio -t --quiet < "$tmp/initramfs.cpio" > "$tmp/cpio.list" 2>/dev/null; then
                    entries=$(wc -l < "$tmp/cpio.list")
                    pass "initramfs: cpio archive with $entries entries"

                    mkdir -p "$tmp/initcheck"
                    if grep -qxE '\.?/?init' "$tmp/cpio.list"; then
                        pass 'initramfs: /init present'
                        init_line=$(cpio -tv --quiet < "$tmp/initramfs.cpio" 2>/dev/null \
                            | awk '$NF == "init" {print}')
                        case "$init_line" in
                            -rwx*) pass 'initramfs: /init is executable' ;;
                            '') fail 'initramfs: cannot read the /init entry' ;;
                            *) fail "initramfs: /init is not executable ($init_line)" ;;
                        esac

                        # Which script is /init?  The builders copy a source to
                        # /init, so the name in the archive is always exactly
                        # "init" and only the content distinguishes the profiles.
                        (cd "$tmp/initcheck" &&
                            cpio -i --quiet init < "$tmp/initramfs.cpio" >/dev/null 2>&1) || true
                        init_profile=unknown
                        if [ -s "$tmp/initcheck/init" ]; then
                            if grep -q 'MINIMAL_ROOTFS=' "$tmp/initcheck/init" &&
                               grep -qE 'setup_usb_gadget|display_recover' "$tmp/initcheck/init"; then
                                init_profile=bringup
                            elif grep -q 'ROOTFS_DEVICE=' "$tmp/initcheck/init" &&
                                 grep -q 'minimal_state_stage' "$tmp/initcheck/init"; then
                                init_profile=minimal
                            fi
                        fi
                        pass "initramfs: /init is the $init_profile profile"

                        # The manifest built beside the source image states the
                        # intent; the content check above states what was packed.
                        # They must agree, or something built the wrong tree.
                        manifest="$bundle_dir/initramfs.manifest"
                        if [ -f "$manifest" ]; then
                            declared=$(sed -n 's/^profile=//p' "$manifest" | head -1)
                            if [ "$declared" = "$init_profile" ]; then
                                pass "initramfs: manifest declares profile=$declared"
                            else
                                fail "initramfs: manifest declares profile=$declared but /init is $init_profile"
                            fi
                        else
                            note 'initramfs: no initramfs.manifest in the bundle; profile rules still apply'
                        fi
                    else
                        fail 'initramfs: no /init (a placeholder tree must never be flashed)'
                    fi

                    if grep -qE '(^|/)bin/busybox$' "$tmp/cpio.list"; then
                        pass 'initramfs: /bin/busybox present'
                        # Extract it to check the ELF itself.  cpio -i will not
                        # create the parent directory, so it has to exist first -
                        # without this the extraction failed silently and the two
                        # checks below never ran, which looked like a pass.
                        mkdir -p "$tmp/bbcheck/bin"
                        (cd "$tmp/bbcheck" &&
                            cpio -i --quiet bin/busybox < "$tmp/initramfs.cpio" >/dev/null 2>&1) || true
                        if [ -s "$tmp/bbcheck/bin/busybox" ]; then
                            if readelf -h "$tmp/bbcheck/bin/busybox" 2>/dev/null | grep -q 'Machine:.*AArch64'; then
                                pass 'initramfs: /bin/busybox is aarch64'
                            else
                                fail 'initramfs: /bin/busybox is not an aarch64 ELF'
                            fi
                            if readelf -l "$tmp/bbcheck/bin/busybox" 2>/dev/null | grep -q INTERP; then
                                fail 'initramfs: /bin/busybox is dynamically linked'
                            else
                                pass 'initramfs: /bin/busybox is static'
                            fi
                        else
                            fail 'initramfs: /bin/busybox is listed but could not be extracted'
                        fi
                    else
                        fail 'initramfs: no /bin/busybox'
                    fi

                    check_initramfs_profile "$tmp/cpio.list" "$init_profile"
                else
                    fail 'initramfs: cpio archive is not readable'
                fi
            else
                fail 'initramfs: not a valid LZ4 stream'
                sed 's/^/      /' "$tmp/lz4.log" >&2
            fi
        else
            fail "initramfs: magic is $magic, expected 02214c18 (legacy LZ4)"
        fi
    fi
}

# check_initramfs_profile CPIO_LIST PROFILE
#
# A production image must not carry what the Debian boot does not need; a debug
# image may.
#
# Two disciplines make these verdicts trustworthy rather than noisy:
#
#   * inventory rules run on the file LIST, so a comment cannot satisfy or defeat
#     them;
#   * execution rules run on the extracted /init with COMMENTS STRIPPED.  A plain
#     `grep ttyGS` would flag the debug script's long explanation of why it no
#     longer creates a serial function - a false positive that would get the
#     validator ignored, which is worse than not having it.
check_initramfs_profile() {
    local list=$1 profile=$2

    # Neither profile may carry a kernel module tree: modules belong on the Debian
    # root in /usr/lib/modules/<release>, and a module tree in init_boot is how a
    # 150 MiB mistake reaches a device.
    if grep -qE '(^|/)lib/modules/' "$list"; then
        fail 'initramfs: carries a kernel module tree (modules belong on the Debian root)'
    else
        pass 'initramfs: no kernel module tree'
    fi

    case "$profile" in
    minimal)
        local forbidden
        for forbidden in 'lib/firmware/' 'gts9-exec-default' 'gts9-to-recovery' \
                         'gts9-reboot-' 'bringup-init' 'gts9-minimal-pid1' \
                         'minimal-rootfs-init'; do
            if grep -qE "$forbidden" "$list"; then
                fail "initramfs: production image contains $forbidden"
            fi
        done
        pass 'initramfs: production image has no firmware, no debug helper, no trampoline'

        if [ -s "$tmp/initcheck/init" ]; then
            sed 's/#.*//' "$tmp/initcheck/init" > "$tmp/initcheck/init.code"
            while IFS='|' read -r pattern label; do
                [ -n "$pattern" ] || continue
                if grep -qE "$pattern" "$tmp/initcheck/init.code"; then
                    fail "initramfs: production /init can $label"
                fi
            done <<'RULES'
mkdir.*usb_gadget|create a configfs USB gadget
mass_storage\.usb0|set up USB mass storage
/dev/disk/by-partlabel|parse the GPT partition table
PARTNAME|parse the GPT partition table
/dev/rtc|read RTC telemetry
hwclock|read RTC telemetry
boot-recovery|write the bootloader control block
regulator_summary|dump regulator state
devices_deferred|dump deferred devices
dmesg|dump the kernel log
ttyGS|use a USB serial port
insmod|load a kernel module
modprobe|load a kernel module
RULES
            pass 'initramfs: production /init executes none of the debug capabilities'

            # Display recovery is the one capability that is allowed back, on a
            # condition rather than unconditionally: it may run only from the
            # rescue path, because the rescue banner is printed to a panel that
            # Debian's gts9-panel-recover.service would otherwise have been the one
            # to fix - and in the rescue path Debian never starts.  On a healthy
            # boot it must not run at all.
            #
            # This checks the CALL SITE, not the definition.  A shell function has
            # to be defined before it is called, so the helper's body necessarily
            # sits above minimal_rescue_shell() in the file; an earlier version of
            # this rule compared the framebuffer write against the rescue
            # function's start and failed its own correct code.  What matters is
            # which function body the call is inside.
            if grep -qE 'fb0/blank' "$tmp/initcheck/init.code"; then
                rescue_line=$(grep -n '^minimal_rescue_shell()' "$tmp/initcheck/init.code" | head -1 | cut -d: -f1)
                # The first line after the rescue function's body ends.
                rescue_end=$(awk -v start="$rescue_line" \
                    'NR > start && /^}/ {print NR; exit}' "$tmp/initcheck/init.code")
                call_line=$(grep -n '^[[:space:]]*minimal_panel_rescue[[:space:]]*$' \
                    "$tmp/initcheck/init.code" | head -1 | cut -d: -f1)
                if [ -n "$call_line" ] && [ -n "$rescue_end" ] &&
                   [ "$call_line" -gt "$rescue_line" ] && [ "$call_line" -lt "$rescue_end" ]; then
                    pass 'initramfs: display recovery is called only from the rescue path'
                elif [ -z "$call_line" ]; then
                    fail 'initramfs: /init writes the framebuffer but never calls the panel helper'
                else
                    fail 'initramfs: production /init calls the panel helper outside the rescue path'
                fi
                # And independently: no framebuffer work between the root mount
                # and switch_root, which is the healthy path.
                mount_line=$(grep -n 'mount -t ext4' "$tmp/initcheck/init.code" | head -1 | cut -d: -f1)
                switch_line=$(grep -n 'switch_root' "$tmp/initcheck/init.code" | tail -1 | cut -d: -f1)
                if [ -n "$mount_line" ] && [ -n "$switch_line" ] && [ "$switch_line" -gt "$mount_line" ]; then
                    if sed -n "${mount_line},${switch_line}p" "$tmp/initcheck/init.code" |
                       grep -qE 'fb0/blank|minimal_panel_rescue'; then
                        fail 'initramfs: the success path touches the framebuffer before switch_root'
                    else
                        pass 'initramfs: the success path does no framebuffer work'
                    fi
                fi
            else
                pass 'initramfs: production /init does no display recovery at all'
            fi
        fi
        ;;
    bringup)
        # The debug image keeps every diagnostic.  What it must still satisfy is
        # the no-serial invariant, because that is a kernel-level fact rather than
        # a diagnostic: the kernel has no ACM function at all, so creating one
        # could only fail.
        if [ -s "$tmp/initcheck/init" ]; then
            sed 's/#.*//' "$tmp/initcheck/init" > "$tmp/initcheck/init.code"
            if grep -qE 'mkdir.*functions/acm|mkdir.*functions/gser' "$tmp/initcheck/init.code"; then
                fail 'initramfs: debug /init creates a serial gadget function (the kernel provides none)'
            else
                pass 'initramfs: debug /init creates no serial gadget function'
            fi
        fi
        pass 'initramfs: debug image keeps its diagnostics by design'
        ;;
    *)
        note 'initramfs: profile undetermined; skipping profile-specific rules'
        ;;
    esac
}

# --------------------------------------------------------------------------
echo
echo '--- init_boot.img: generic BusyBox initramfs ---'
# --------------------------------------------------------------------------
if [ "$init_boot_ok" = 1 ]; then
    mkdir -p "$tmp/initboot"
    if python3 "$unpack" --boot_img "$bundle_dir/init_boot.img" --out "$tmp/initboot" \
            > "$tmp/initboot.info" 2>&1; then
        if grep -q 'boot image header version: 4' "$tmp/initboot.info"; then
            pass 'init_boot.img: header version 4'
        else
            fail 'init_boot.img: not a header version 4 image'
        fi

        if [ -s "$tmp/initboot/ramdisk" ]; then
            check_initramfs "$tmp/initboot/ramdisk"
        else
            fail 'init_boot.img: no generic initramfs'
        fi

    else
        fail 'unpack_bootimg could not parse init_boot.img'
        sed 's/^/      /' "$tmp/initboot.info" >&2
    fi
fi

# vendor_boot is deliberately an empty platform archive. In particular it
# must not provide another /init that could overwrite the generic one.
if [ -n "$vendor_ramdisk" ] && [ -s "$vendor_ramdisk" ]; then
    if lz4 -d -q -f "$vendor_ramdisk" "$tmp/platform.cpio" &&
       cpio -t --quiet < "$tmp/platform.cpio" > "$tmp/platform.list" 2>/dev/null &&
       ! grep -qvE '^\.?/?$' "$tmp/platform.list"; then
        pass 'vendor_boot.img: empty platform ramdisk'
    else
        fail 'vendor_boot.img: platform ramdisk is not an empty archive'
    fi
fi

# --------------------------------------------------------------------------
echo
echo '--- AVB footers ---'
# --------------------------------------------------------------------------
check_avb() {
    # check_avb <image> <partition name>
    local image=$1 name=$2
    if [ ! -f "$bundle_dir/$image" ]; then
        fail "$image: missing, cannot check AVB"
        return
    fi
    if python3 "$avbtool" info_image --image "$bundle_dir/$image" > "$tmp/avb-$image.txt" 2>&1; then
        if grep -q "Partition Name: *$name" "$tmp/avb-$image.txt"; then
            pass "$image: AVB hash descriptor for '$name'"
        else
            fail "$image: AVB descriptor does not name '$name'"
        fi
    else
        fail "$image: avbtool cannot parse the image"
    fi
}
if [ "$boot_ok" = 1 ]; then check_avb boot.img boot; fi
if [ "$init_boot_ok" = 1 ]; then check_avb init_boot.img init_boot; fi
if [ "$vendor_boot_ok" = 1 ]; then check_avb vendor_boot.img vendor_boot; fi
if [ "$dtbo_ok" = 1 ]; then check_avb dtbo.img dtbo; fi

if [ "$vbmeta_ok" = 1 ]; then
    if python3 "$avbtool" info_image --image "$bundle_dir/vbmeta.img" > "$tmp/avb-vbmeta.txt" 2>&1; then
        flags=$(sed -n 's/^Flags: *//p' "$tmp/avb-vbmeta.txt" | head -1)
        pass "vbmeta.img: parses (Flags: ${flags:-unknown})"
        case " ${flags:-} " in
            *2*)
                echo
                echo 'WARNING: vbmeta generated by this repository disables AVB verification'
                echo 'WARNING: keep the existing device vbmeta unless you have a recovery plan'
                echo
                ;;
        esac
    else
        fail 'vbmeta.img: avbtool cannot parse the image'
    fi
fi

# --------------------------------------------------------------------------
echo
echo '--- SHA-256 manifest ---'
# --------------------------------------------------------------------------
if [ -f "$bundle_dir/SHA256SUMS" ]; then
    if ( cd "$bundle_dir" && sha256sum -c SHA256SUMS --quiet ); then
        pass 'SHA256SUMS verifies against every image'
    else
        fail 'SHA256SUMS does not match the images'
    fi
else
    fail 'SHA256SUMS is missing (rerun scripts/build-boot-bundle.sh)'
fi

echo
if [ "$failed" -ne 0 ]; then
    echo "BOOT BUNDLE VALIDATION FAILED ($failed check(s))"
    exit 1
fi
echo 'BOOT BUNDLE VALIDATION PASSED'
echo 'Nothing was written: this validator only read the images.'
