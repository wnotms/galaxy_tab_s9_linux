#!/bin/sh
set -eu
mkdir -p debian/out/system
mkdir -p debian/out/host-bin
ln -sf "$(command -v aarch64-linux-gnu-ar)" debian/out/host-bin/ar
export PATH="$PWD/debian/out/host-bin:$PATH"
for dir in packages/modules/adb/proto packages/modules/adb/fastdeploy/proto; do
    (cd "$dir"; protoc --cpp_out=. ./*.proto)
done
export CPPFLAGS='-DNDEBUG -UDEBUG -fno-exceptions -fno-strict-aliasing -D_FORTIFY_SOURCE=2'
for name in libadb libcrypto_utils adbd; do
    make -j"${ADBD_BUILD_JOBS:-4}" -f "debian/system/$name.mk" \
        CXX='clang++ --target=aarch64-linux-gnu' \
        CXXFLAGS='-O2 -g -fPIC -std=gnu++20 -fstack-protector-strong -Wno-narrowing' \
        DEB_HOST_MULTIARCH=aarch64-linux-gnu DEB_HOST_ARCH=arm64 \
        PLATFORM_TOOLS_VERSION=34.0.5 DEB_VERSION=34.0.5-12+gts9reconnect1 \
        AR=aarch64-linux-gnu-ar
done
aarch64-linux-gnu-strip --strip-unneeded debian/out/system/adbd
cp debian/out/system/adbd /output/gts9-adbd-reconnect
sha256sum /output/gts9-adbd-reconnect
aarch64-linux-gnu-readelf -d debian/out/system/adbd > /output/elf-dynamic.txt
aarch64-linux-gnu-readelf --version-info debian/out/system/adbd > /output/elf-versions.txt
dpkg-query -W > /output/build-packages.txt
