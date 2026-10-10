#!/bin/sh
# Offline ARM64 protocol-status qualification; never installs on the tablet.
set -eu
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
mkdir -p /output/work /output/stage
cp -a /inputs/final/. /output/work/hexagonrpc
cp /inputs/final/OPEN_ERROR_SOURCE.json /output/OPEN_ERROR_SOURCE.json
aarch64-linux-gnu-gcc --version > /output/compiler.txt
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > /output/packages.tsv
if test -f /output/build/build.ninja; then
    meson setup --reconfigure /output/build /output/work/hexagonrpc \
        --cross-file=/recipe/cross-arm64.ini --prefix=/usr \
        --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
        -Dhexagonrpcd_verbose=true
else
    meson setup /output/build /output/work/hexagonrpc \
        --cross-file=/recipe/cross-arm64.ini --prefix=/usr \
        --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
        -Dhexagonrpcd_verbose=true
fi
meson compile -C /output/build -j 4
meson test -C /output/build --print-errorlogs
DESTDIR=/output/stage meson install -C /output/build
printf private-payload > /output/payload
for profile in original final; do
    root="/inputs/$profile"
    source="$root/hexagonrpcd"
    aarch64-linux-gnu-gcc -std=gnu11 -Wall -Wextra -Werror \
        -Wno-unused-function -Wno-unused-parameter \
        -ffunction-sections -fdata-sections -DHEXAGONRPC_VERBOSE \
        -I"$root/include" -I"$source" /fixtures/rpc_open_error_harness.c \
        "$source/hexagonfs.c" "$source/hexagonfs_virt_dir.c" \
        "$source/hexagonfs_mapped.c" -Wl,--gc-sections \
        -o "/output/open-$profile"
    for mode in missing present permission io-error readonly-write unknown-env bad-mode missing-dir repeat-missing; do
        timeout --signal=KILL 5s qemu-aarch64 -L /usr/aarch64-linux-gnu \
            "/output/open-$profile" "$mode" /output/payload \
            > "/output/$profile-$mode.stdout" 2> "/output/$profile-$mode.stderr"
    done
done
