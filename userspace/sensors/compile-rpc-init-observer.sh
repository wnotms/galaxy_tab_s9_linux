#!/bin/sh
# Offline ARM64 build plus exact listener and localctl C/QEMU boundary cases.
set -eu
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
mkdir -p /output/work /output/stage
cp -a /inputs/final/. /output/work/hexagonrpc
aarch64-linux-gnu-gcc --version > /output/compiler.txt
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > /output/packages.tsv
meson setup /output/build /output/work/hexagonrpc \
    --cross-file=/recipe/cross-arm64.ini --prefix=/usr \
    --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
    -Dhexagonrpcd_verbose=true
meson compile -C /output/build -j 4
meson test -C /output/build --print-errorlogs
DESTDIR=/output/stage meson install -C /output/build
source=/inputs/final
for fixture in rpc_return rpc_localctl; do
    aarch64-linux-gnu-gcc -std=gnu11 -Wall -Wextra -Werror \
        -Wno-unused-function -Wno-unused-parameter \
        -ffunction-sections -fdata-sections -DHEXAGONRPC_BUILD_METHOD_DEFINITIONS=1 \
        -I"$source/include" -I"$source/hexagonrpcd" \
        "/fixtures/${fixture}_harness.c" "$source/hexagonrpcd/iobuffer.c" \
        -Wl,--gc-sections -o "/output/$fixture"
done
for budget in default 8388608; do
    for mode in normal large transport-error frame-limit null-frame budget; do
        if test "$budget" = default; then
            unset HEXAGONRPC_RETURN_TRACE_BUDGET
        else
            export HEXAGONRPC_RETURN_TRACE_BUDGET="$budget"
        fi
        HEXAGONRPC_RETURN_TRACE=1 timeout --signal=KILL 5s \
            qemu-aarch64 -L /usr/aarch64-linux-gnu /output/rpc_return "$mode" \
            > "/output/$budget-$mode.stdout" 2> "/output/$budget-$mode.stderr"
    done
done
unset HEXAGONRPC_RETURN_TRACE_BUDGET
for name in sns_registry apps_std other; do
    timeout --signal=KILL 5s qemu-aarch64 -L /usr/aarch64-linux-gnu \
        /output/rpc_localctl "$name" > "/output/localctl-$name.stdout" \
        2> "/output/localctl-$name.stderr"
done
