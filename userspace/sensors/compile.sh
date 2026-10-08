#!/bin/sh
# Runs only inside the disposable Debian cross-build container.
set -eu
test "$(id -u)" = 0
test -f /opt/ssc/cross-arm64.ini
cmp /opt/ssc/cross-arm64.ini /recipe/cross-arm64.ini
test -f /inputs/PREPARED.json
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
mkdir -p /output/work /output/stage
cp -a /inputs/. /output/work/
cd /output/work
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > /output/packages.tsv
aarch64-linux-gnu-gcc --version > /output/compiler.txt

meson setup libssc-build libssc --cross-file=/opt/ssc/cross-arm64.ini \
    --prefix=/usr --libdir=lib/aarch64-linux-gnu --buildtype=release
meson compile -C libssc-build -j 4
# Install target libraries into this disposable container, for proxy linking.
meson install -C libssc-build
DESTDIR=/output/stage meson install -C libssc-build

meson setup hexagonrpc-build hexagonrpc --cross-file=/opt/ssc/cross-arm64.ini \
    --prefix=/usr --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release
meson compile -C hexagonrpc-build -j 4
meson test -C hexagonrpc-build --print-errorlogs
DESTDIR=/output/stage meson install -C hexagonrpc-build
# Fedora's upstream unit template follows libdir; Debian units are not multiarch.
mkdir -p /output/stage/usr/lib/systemd/system
mv /output/stage/usr/lib/aarch64-linux-gnu/systemd/system/* \
    /output/stage/usr/lib/systemd/system/
rmdir /output/stage/usr/lib/aarch64-linux-gnu/systemd/system \
    /output/stage/usr/lib/aarch64-linux-gnu/systemd

make -C pd-mapper -j4 CC=aarch64-linux-gnu-gcc prefix=/usr
make -C pd-mapper CC=aarch64-linux-gnu-gcc prefix=/usr DESTDIR=/output/stage install

meson setup proxy-build iio-sensor-proxy --cross-file=/opt/ssc/cross-arm64.ini \
    --prefix=/usr --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
    -Dssc-support=enabled -Dudevrulesdir=/usr/lib/udev/rules.d \
    -Dsystemdsystemunitdir=/usr/lib/systemd/system
meson compile -C proxy-build -j 4
meson test -C proxy-build --print-errorlogs
DESTDIR=/output/stage meson install -C proxy-build
for component in libssc hexagonrpc pd-mapper iio-sensor-proxy; do
    destination="/output/stage/usr/share/doc/gts9-ssc-sources/$component"
    mkdir -p "$destination"
    for license in COPYING LICENSE; do
        if test -f "$component/$license"; then
            cp "$component/$license" "$destination/$license"
        fi
    done
done
find /output/stage -type f -exec sh -c '
    for file do
        if head -c 4 "$file" | grep -q ELF; then
            printf "\n%s\n" "$file"
            aarch64-linux-gnu-readelf -d "$file"
        fi
    done
' sh {} + > /output/elf-dynamic.txt
# No firmware, service activation, device access or package installation on tablet.
