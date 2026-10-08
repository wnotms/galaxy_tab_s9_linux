# X710 SSC userspace source preparation

The next desktop component is automatic rotation. The current Test331 desktop
has no accelerometer backend: its only IIO device is the PMIC ADC, ADSP is
offline, Samsung ADSP firmware is absent, `/dev/fastrpc-adsp` is absent, and
the SSC userspace packages are not installed. See the read-only inventory in
`reference/desktop-bringup/ssc-offline/`.

This directory reuses the same-model Fedora source versions and five patches
from commit `ab123e7d1dbc0cbcd35661f9761197e977b15aa9` (remote HEAD confirmed
unchanged during preparation). `sources.json` binds every upstream archive and
imported patch by SHA-256. Upstream archives stay in ignored `out/`; upstream
licenses remain in the prepared source trees. Patch provenance:

| Component | Fedora source | Purpose |
| --- | --- | --- |
| libssc 0.4.4 | Codeberg release | Qualcomm SSC sensor discovery and measurements |
| pd-mapper 1.1 | andersson release | Remote service domain discovery |
| hexagonrpc 0.4.0 | linux-msm release | FastRPC userspace service |
| large-inbufs patch | `specs/hexagonrpcd-samsung/patches/` | Samsung reverse-RPC buffers and extended method IDs |
| registry-writes patch | same | Writable **copied** sensor registry through HexagonFS |
| systemd-services patch | same; upstream c4109b45023f7dcc5ef20f68b9bebffc6736da7b | Source templates for the daemon units |
| iio-sensor-proxy 3.9 | freedesktop release | GNOME sensor D-Bus interface; build with SSC explicitly enabled |
| notify-slow-discovery patch | `specs/iio-sensor-proxy-libssc/patches/` | Notify clients after delayed SSC discovery |
| start-polling-claimed patch | same | Honor claims received before sensor discovery finished |

Download the four exact `url` entries in `sources.json` to their `filename`
under a host cache, then run:

```sh
python3 userspace/sensors/prepare.py \
  --cache out/ssc-sources/cache \
  --output out/ssc-sources/prepared
python3 -m unittest tests.test_ssc_source_preparation -v
```

The preparer verifies all inputs before staging, rejects unsafe archive paths,
links and duplicates, applies patches with zero fuzz, and publishes a new source
directory only after all patches succeed. Existing output is preserved and
refused. `PREPARED.json` contains patch transcripts and all resulting file hashes.
The tool has no download, device, build or installation command.

The verified local output for this preparation is
`out/ssc-sources/prepared-clean`; its manifest is preserved in the reference
directory. The proxy availability patch applies with a two-line offset and
zero fuzz. All five patch inputs match the pinned Fedora commit byte-for-byte.
These are prepared sources, **not ARM64 binaries or hardware acceptance**.

## Remaining integration

Build Debian ARM64 packages in a host sysroot/container with matching runtime
dependencies. libssc needs GLib, libqmi >=1.33.4 and protobuf-c; the proxy needs
GUdev, systemd and polkit development inputs as well as libssc. Configure it
with `-Dssc-support=enabled`, so a missing dependency cannot silently select
the kernel-IIO-only backend. Use Debian's `/usr/lib/systemd/system` for unit
templates rather than the architecture library directory. Inspect package
maintainer scripts before installation; keep ADSP/RPC units inactive until the
separate physical registration. Current host compilation dependencies have
not been provisioned and no component was compiled in this step.

Next prepare **Samsung X710 signed** `adsp.mdt` and `adsp_dtb.mdt` plus every
referenced segment from owner firmware, recording hashes. Both names are
already requested by the current DTS. Also prepare sensorspd libraries and a
device-specific **copy** of the registry; do not expose or chmod the actual
Android persist partition. Fedora's registry permission helper is deliberately
not installed. Firmware content/availability remains unverified here.

Fedora's `docs/Known-Issues.md` records that starting ADSP late may hang/reset
the SoC and leaves its ADSP-start service disabled. Do not copy or invoke its
25-second-delay remoteproc `echo start` service in the active desktop. Select
and register a controlled boot-time firmware-loading experiment with Test331
rollback/rescue before any ADSP activation. Adding firmware to a running rootfs
alone does not prove that ADSP will retry or start at the desired boot stage.

Once ADSP/FastRPC/SSC is proven, test accelerometer readings, D-Bus availability,
claims during discovery, and GNOME rotation with pen/touch coordinates in all
four orientations. Fedora's `ACCEL_MOUNT_MATRIX="0,1,0;-1,0,0;0,0,1"` is a
same-model reference; it must be physically qualified here. Do not change
charging, speaker routing, suspend or input calibration during that experiment.

Imported source locations and licenses are retained in the patch headers and
upstream archives. Fedora repository: https://github.com/nacht20-de/gts9wifi-fedora-linux
