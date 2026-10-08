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
Source preparation alone is **not ARM64 compilation or hardware acceptance**.

## Offline Debian ARM64 build

```sh
docker build -t gts9-ssc-builder:trixie-arm64 \
  -f userspace/sensors/builder.Dockerfile userspace/sensors
python3 userspace/sensors/build.py \
  --sources out/ssc-sources/prepared-clean --output out/ssc-arm64
python3 -m unittest tests.test_ssc_cross_build tests.test_ssc_source_preparation -v
```

The base Debian image is pinned by digest. The image's installed package versions,
compiler version, image identity, recipe hashes and prepared-source hashes are
recorded with the output; apt repositories themselves are not a frozen snapshot.
On hosts where Docker needs the existing local proxy, build the image using
`--network=host --build-arg http_proxy --build-arg https_proxy`. This is only for
dependency provisioning; component compilation runs with `--network=none`.

The builder checks prepared source identity, copies it into an isolated working
directory, explicitly enables SSC in the proxy, and checks all staged ELF files
for ARM64. The sources remain mounted read-only. HexagonRPC unit templates are
relocated from multiarch libdir to Debian's standard unit directory. No units are
enabled. `ssc-arm64-stage.tar.gz` is an **offline staging archive**, not an
installation command or a qualified Debian package. Keep it on the host until
runtime dependencies, firmware, registry isolation and boot ordering are qualified.
Existing output is refused; preserve build logs/manifests before cleaning the
same working output for a new build.

The build runs HexagonRPC's buffer/filesystem tests and the proxy's orientation,
mount-matrix and XML tests under QEMU as applicable. These do not exercise an ADSP.
libssc's QRTR/mock-service tests are not run: a cross-compiled binary in the
networkless container is not a qualified QRTR/SSC runtime environment. Their
compilation does not establish that sensor discovery or GNOME rotation works.

## Remaining integration

### Debian runtime packages

```sh
python3 userspace/sensors/package.py --build out/ssc-arm64 --output out/ssc-debs
python3 -m unittest tests.test_ssc_debian_packaging tests.test_ssc_cross_build -v
```

The packager requires the exact qualified `BUILD.json` in
`reference/desktop-bringup/ssc-offline`, and compares every staged file/link before
using the recorded build image. It creates four ARM64 packages in a networkless,
unprivileged container: `libssc2`, `gts9-hexagonrpc`, `pd-mapper`, and
`iio-sensor-proxy`. Runtime dependency minima come from Debian `dpkg-shlibdeps`
and target symbol metadata, including the local libssc dependency. Mock servers,
headers, Python test modules, unversioned development links and the unused CHRE
client are excluded. Upstream licenses accompany each package.

The FastRPC permission rule is byte-identical to the pinned Fedora
`specs/hexagonrpcd-samsung/patches/10-fastrpc.rules`; the new sysusers file only
declares its service account. There are no maintainer scripts or enabled-unit
links. The two library packages request the standard `ldconfig` trigger.
The wrapper reopens all four generated `.deb` files and verifies their metadata,
root ownership, exact payload hashes, disjoint file ownership and absence of
unexpected control scripts. It does not run `dpkg -i`, `apt install`, udev reload,
service start, remoteproc start, firmware copy or any tablet command.

These packages are prepared outputs, **not an installed or hardware-qualified
sensor stack**. Original daemon units still carry their upstream restart policy;
the eventual one-attempt physical registration must override it and inhibit
activation during installation. The sysusers account must be provisioned before
FastRPC permission rules are applied. Check existing package/file ownership and
runtime dependency availability before deployment, retain an installation manifest,
and reverse only newly owned files/packages on rollback. Detailed results are in
`reference/desktop-bringup/ssc-runtime-preparation/RESULTS.md`.

libssc needs GLib, libqmi >=1.33.4 and protobuf-c; the proxy needs
GUdev, systemd and polkit development inputs as well as libssc. Configure it
with `-Dssc-support=enabled`, so a missing dependency cannot silently select
the kernel-IIO-only backend. Use Debian's `/usr/lib/systemd/system` for unit
templates rather than the architecture library directory. Inspect package
maintainer scripts before installation; keep ADSP/RPC units inactive until the
separate physical registration. Actual compilation status and logs are recorded
in `reference/desktop-bringup/ssc-offline/BUILD_RESULTS.md`.

The owner's stock `adsp.mdt` and `adsp_dtb.mdt` and all required data segments
have now been collected read-only and structurally verified on the host. See
`reference/desktop-bringup/ssc-stock-assets/RESULTS.md`; TrustZone authentication
and runtime acceptance remain untested. Reproduce host verification using the
archive hash recorded in that directory's `validation.json`:

```sh
python3 userspace/sensors/verify-stock-assets.py \
  --archive out/ssc-stock-assets/source.tar.gz --sha256 RECORDED_SHA256 \
  --report out/ssc-stock-assets/VERIFIED.json
python3 -m unittest tests.test_ssc_stock_assets -v
```

The copied stock registry cache's 35 Android vendor config inputs have also been
collected read-only, all with the exact cached input mtime. See
`reference/desktop-bringup/ssc-vendor-config/RESULTS.md`. The offline asset tar
has 328 verified files and preserves stock content/timestamps. Reproduce it
using both recorded source archive SHA-256 values:

```sh
python3 userspace/sensors/stage-assets.py \
  --stock out/ssc-stock-assets/source.tar.gz --stock-sha256 RECORDED_STOCK_SHA256 \
  --vendor out/ssc-vendor-config/source.tar.gz --vendor-sha256 RECORDED_VENDOR_SHA256 \
  --output out/ssc-assets
python3 -m unittest tests.test_ssc_asset_staging tests.test_ssc_vendor_layout -v
```

Existing output is refused. This archive has no installer, units, enabled links
or activation command. Stock `sns_reg_config` also references soc0 identity
paths absent in current Debian; qualify their HexagonFS mapping and controlled
early-boot ordering before deployment. Runtime discovery is not verified.

Map stock paths relative to `persist/sensors/registry/` into `PREFIX/sensors/`
to match this exact HexagonFS implementation, and preserve the cache's input
mtimes. Do not copy an extra registry directory or apply S9 Ultra's zero-mtime
normalization to this X710 cache. Firmware/registry content stays private in
ignored host staging; it is not installed on the tablet.

For future fresh stock collection prepare **Samsung X710 signed** `adsp.mdt` and `adsp_dtb.mdt` plus every
referenced segment from owner firmware, recording hashes. Both names are
already requested by the current DTS. Also prepare sensorspd libraries and a
device-specific **copy** of the registry; do not expose or chmod the actual
Android persist partition. Fedora's registry permission helper is deliberately
not installed. Firmware authentication and complete runtime discovery remain
unverified here; vendor config availability and cache mtimes are now verified.

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
