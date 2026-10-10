#!/bin/sh
# Runs only in the existing networkless Debian ARM64 builder.
set -eu
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
mkdir -p /output/work /output/stage
cp -a /inputs/final/. /output/work/libssc
cd /output/work
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > /output/packages.tsv
aarch64-linux-gnu-gcc --version > /output/compiler.txt
if test -f libssc-build/build.ninja; then
    meson setup --reconfigure libssc-build libssc --cross-file=/opt/ssc/cross-arm64.ini \
        --prefix=/usr --libdir=lib/aarch64-linux-gnu --buildtype=release
else
    meson setup libssc-build libssc --cross-file=/opt/ssc/cross-arm64.ini \
        --prefix=/usr --libdir=lib/aarch64-linux-gnu --buildtype=release
fi
meson compile -C libssc-build -j 4
DESTDIR=/output/stage meson install -C libssc-build
export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
for profile in original reference final; do
    aarch64-linux-gnu-gcc -std=gnu11 -Wall -Wextra -Werror -Wno-unused-parameter \
        $(pkg-config --cflags gio-2.0 qmi-glib) \
        -I"/inputs/$profile/src" /fixtures/libssc_wait_harness.c \
        "/inputs/$profile/src/libssc-common.c" \
        $(pkg-config --libs gio-2.0 qmi-glib) -o "/output/wait-$profile"
done
python3 /fixtures/run_libssc_wait.py /output
aarch64-linux-gnu-readelf -d /output/stage/usr/lib/aarch64-linux-gnu/libssc.so.2 > /output/elf-dynamic.txt
mkdir -p /output/stage/usr/share/doc/gts9-libssc-wait
cp /inputs/final/LICENSE /output/stage/usr/share/doc/gts9-libssc-wait/
