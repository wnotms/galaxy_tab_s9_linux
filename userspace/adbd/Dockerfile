FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
RUN dpkg --add-architecture arm64 && apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates \
      crossbuild-essential-arm64 protobuf-compiler \
      libprotobuf-dev:arm64 libsystemd-dev:arm64 liblz4-dev:arm64 \
      libzstd-dev:arm64 libbrotli-dev:arm64 android-libboringssl-dev:arm64 \
      android-libbase-dev:arm64 android-libcutils-dev:arm64 android-liblog-dev:arm64 && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends make clang && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /source
