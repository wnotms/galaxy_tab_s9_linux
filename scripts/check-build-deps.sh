#!/usr/bin/env bash
# Report which host tools the SM-X710 kernel build and boot-image packaging
# need, and which are missing.  Read-only: it installs nothing and touches no
# device.
#
# Adapted for this repository from the SM-X910 reference port
# (ubuntu-galaxy-tab-s9-ultra, scripts/check-build-deps.sh), with the kernel
# half of the list extended for ARCH=arm64 LLVM=1 and the packaging half kept
# to what scripts/build-boot-bundle.sh actually runs.
set -uo pipefail

missing=0

need() {
    if command -v "$1" >/dev/null 2>&1; then
        printf 'OK    %-22s %s\n' "$1" "$(command -v "$1")"
    else
        printf 'MISS  %-22s (%s)\n' "$1" "$2"
        missing=$((missing + 1))
    fi
}

need_file() {
    if [ -f "$1" ]; then
        printf 'OK    %-22s %s\n' "$2" "$1"
    else
        printf 'MISS  %-22s (%s)\n' "$2" "$3"
        missing=$((missing + 1))
    fi
}

echo '=== source control and shell ==='
need git 'apt install git'
need bash 'apt install bash'
need curl 'apt install curl (AOSP tools and pinned BusyBox)'
need readelf 'apt install binutils (BusyBox ELF checks)'
need strings 'apt install binutils (BusyBox applet checks)'

echo
echo '=== kernel build (ARCH=arm64 LLVM=1) ==='
need make 'apt install make'
need clang 'apt install clang'
need ld.lld 'apt install lld'
need llvm-ar 'apt install llvm'
need llvm-nm 'apt install llvm'
need llvm-objcopy 'apt install llvm'
need llvm-strip 'apt install llvm'
need bc 'apt install bc'
need bison 'apt install bison'
need flex 'apt install flex'
need python3 'apt install python3'
need rsync 'apt install rsync'
need base64 'apt install coreutils'
need gzip 'apt install gzip'
need openssl 'apt install openssl (module signing)'
need pahole 'apt install dwarves (CONFIG_DEBUG_INFO_BTF)'
need dtc 'apt install device-tree-compiler'
need depmod 'apt install kmod (modules_install)'
need_file /usr/include/openssl/ssl.h 'libssl-dev' 'apt install libssl-dev'
need_file /usr/include/libelf.h 'libelf-dev' 'apt install libelf-dev'
need ccache 'apt install ccache (optional, speeds up rebuilds)'

if command -v clang >/dev/null 2>&1; then
    clang_major=$(clang --version | sed -n 's/.*version \([0-9][0-9]*\).*/\1/p' | head -1)
    if [ -n "$clang_major" ] && [ "$clang_major" -lt 17 ]; then
        printf 'FAIL  %-22s clang %s is too old for Linux 7.2 (needs >= 17)\n' \
            'clang version' "$clang_major"
        missing=$((missing + 1))
    else
        printf 'OK    %-22s clang %s\n' 'clang version' "${clang_major:-unknown}"
    fi
fi

echo
echo '=== Android boot v4 packaging ==='
need python3 'apt install python3'
need cpio 'apt install cpio'
need lz4 'apt install lz4 (Samsung ABL needs the legacy LZ4 stream)'
need sha256sum 'apt install coreutils'
need stat 'apt install coreutils'
need dpkg-deb 'apt install dpkg (unpack the pinned BusyBox)'

repo_root=$(cd "$(dirname "$0")/.." && pwd)
tools=${ANDROID_TOOLS:-${GTS9_WORKDIR:-$repo_root/.work}/tools}
for tool in mkbootimg.py avbtool.py; do
    if [ -f "$tools/$tool" ]; then
        printf 'OK    %-22s %s\n' "$tool" "$tools/$tool"
    else
        printf 'MISS  %-22s (run scripts/stage-android-tools.sh)\n' "$tool"
        missing=$((missing + 1))
    fi
done

echo
if [ "$missing" -eq 0 ]; then
    echo 'all dependencies present'
else
    echo "$missing dependency/dependencies missing"
fi
exit "$([ "$missing" -eq 0 ] && echo 0 || echo 1)"
