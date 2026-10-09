#!/bin/sh
# Isolated networkless ARM64 diagnostic. No installation or service activation.
set -eu
test "$(id -u)" = 0
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
test -f /inputs/SOURCE.json
mkdir /output/work
cp -a /inputs/hexagonrpc /output/work/
cp /inputs/SOURCE.json /output/SOURCE.json
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > /output/packages.tsv
aarch64-linux-gnu-gcc --version > /output/compiler.txt
meson setup /output/build /output/work/hexagonrpc \
    --cross-file=/recipe/cross-arm64.ini --prefix=/usr \
    --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
    -Dhexagonrpcd_verbose=true
meson compile -C /output/build -j 4
meson test -C /output/build --print-errorlogs
DESTDIR=/output/stage meson install -C /output/build
mkdir -p /output/stage/usr/lib/systemd/system
mv /output/stage/usr/lib/aarch64-linux-gnu/systemd/system/* \
   /output/stage/usr/lib/systemd/system/
rmdir /output/stage/usr/lib/aarch64-linux-gnu/systemd/system \
       /output/stage/usr/lib/aarch64-linux-gnu/systemd
aarch64-linux-gnu-readelf -h -d /output/stage/usr/bin/hexagonrpcd > /output/elf.txt
