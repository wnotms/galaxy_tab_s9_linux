#!/bin/sh
# Existing offline ARM64 builder only; no tablet or system-bus access.
set -eu
trap 'chown -R "$HOST_UID:$HOST_GID" /output' EXIT
mkdir -p /output/work /output/stage
cp -a /inputs/final/. /output/work/proxy
cp -a /libssc-stage/usr/include/libssc /usr/include/
cp -a /libssc-stage/usr/lib/aarch64-linux-gnu/libssc.so* /usr/lib/aarch64-linux-gnu/
cp /libssc-stage/usr/lib/aarch64-linux-gnu/pkgconfig/libssc.pc /usr/lib/aarch64-linux-gnu/pkgconfig/
cd /output/work
if test -f proxy-build/build.ninja; then
    meson setup --reconfigure proxy-build proxy --cross-file=/opt/ssc/cross-arm64.ini \
        --prefix=/usr --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
        -Dssc-support=enabled -Dudevrulesdir=/usr/lib/udev/rules.d -Dsystemdsystemunitdir=/usr/lib/systemd/system
else
    meson setup proxy-build proxy --cross-file=/opt/ssc/cross-arm64.ini \
        --prefix=/usr --libdir=lib/aarch64-linux-gnu --libexecdir=libexec --buildtype=release \
        -Dssc-support=enabled -Dudevrulesdir=/usr/lib/udev/rules.d -Dsystemdsystemunitdir=/usr/lib/systemd/system
fi
meson compile -C proxy-build -j 4
meson test -C proxy-build --print-errorlogs
DESTDIR=/output/stage meson install -C proxy-build
export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
for profile in original reference final; do
    source="/inputs/$profile/src"
    aarch64-linux-gnu-gcc -std=gnu11 -Wall -Wextra -Werror \
        -Wno-unused-parameter -Wno-unused-function -Wno-unused-variable \
        -Wno-missing-field-initializers \
        -ffunction-sections -fdata-sections \
        $(pkg-config --cflags gio-2.0 gudev-1.0 polkit-gobject-1) \
        -I/output/work/proxy-build/src -I"$source" \
        /fixtures/proxy_claim_harness.c "$source/orientation.c" "$source/accel-scale.c" \
        "$source/accel-attributes.c" "$source/utils.c" \
        /output/work/proxy-build/src/iio-sensor-proxy-resources.c \
        -Wl,--gc-sections $(pkg-config --libs gio-2.0 gudev-1.0 polkit-gobject-1) \
        -lm -o "/output/claim-$profile"
done
