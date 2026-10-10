#!/bin/sh
# Offline ARM64 daemon/readdir qualification. No device operations.
set -eu
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
mkdir -p /output/work /output/stage
cp -a /inputs/final/. /output/work/hexagonrpc
cp /inputs/final/READDIR_SOURCE.json /output/READDIR_SOURCE.json
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
for profile in original final; do
    source="/inputs/$profile"
    aarch64-linux-gnu-gcc -std=gnu11 -Wall -Wextra -Werror \
        -Wno-unused-function -Wno-unused-parameter \
        -ffunction-sections -fdata-sections -DHEXAGONRPC_VERBOSE \
        -I"$source/include" -I"$source/hexagonrpcd" \
        /fixtures/rpc_readdir_harness.c -Wl,--gc-sections \
        -o "/output/readdir-$profile"
    modes="name max-name eof error repeat"
    if test "$profile" = final; then
        modes="$modes short-in long-in short-out long-out null-in null-out"
    fi
    for mode in $modes; do
        timeout --signal=KILL 5s qemu-aarch64 -L /usr/aarch64-linux-gnu \
            "/output/readdir-$profile" "$profile" "$mode" \
            > "/output/$profile-$mode.stdout" 2> "/output/$profile-$mode.stderr"
    done
done
