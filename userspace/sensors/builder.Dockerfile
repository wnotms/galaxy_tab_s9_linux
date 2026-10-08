FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture arm64
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc-aarch64-linux-gnu meson ninja-build pkgconf \
    python3 python3-packaging protobuf-compiler protobuf-c-compiler \
    libglib2.0-dev-bin libxml2-utils qemu-user \
    libglib2.0-dev:arm64 libqmi-glib-dev:arm64 libprotobuf-c-dev:arm64 \
    libgudev-1.0-dev:arm64 libpolkit-gobject-1-dev:arm64 \
    libqrtr-dev:arm64 liblzma-dev:arm64 libudev-dev:arm64 systemd-dev

# libssc's always-built Python mock module requests a target Python dependency.
RUN apt-get install -y --no-install-recommends libpython3.13-dev:arm64

COPY cross-arm64.ini /opt/ssc/cross-arm64.ini
