# SSC Debian ARM64 offline compilation — 2026-10-08

Verdict: **ARM64_COMPILED_NOT_DEPLOYED**. This is an offline desktop-porting
step, not a physical sensor/rotation test. No tablet command, firmware copy,
remoteproc start, service change, reboot or flash was performed in this step.

The source baseline was test HEAD `1f566163`. The same four source versions and
five Fedora patches recorded in `prepared.json` were compiled without changing
their source. The builder verified all 205 prepared source files before copying
them into a disposable Debian trixie cross-build container. Compilation ran with
network disabled and read-only source/recipe mounts. `BUILD.json` binds the
compiler inputs, image ID, 68 staged regular files and two relative library links.
All eight staged ELF objects are little-endian ARM64.

| Component | Result |
| --- | --- |
| libssc 0.4.4 / SONAME libssc.so.2 / ssccli | ARM64 compiled |
| hexagonrpc 0.4.0 / libhexagonrpc.so.0.4 / hexagonrpcd | ARM64 compiled |
| pd-mapper 1.1 | ARM64 compiled |
| iio-sensor-proxy 3.9 / monitor-sensor | ARM64 compiled, `ssc-support=enabled` |

The pinned base is Debian image digest
`a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a`.
The final build image is
`sha256:1b148977ce4662a9d9a28e44b92d3499934ce08fc11f096e32d0fc911b5b79b0`.
Compiler: Debian AArch64 GCC 14.2.0-19; Meson 1.7.0. Exact dependency versions are
in `packages.tsv`, including ARM64 GLib 2.84.4, libqmi 1.36.0 and protobuf-c 1.5.1.
APT repositories were live; the package list records this build rather than
promising an immutable APT snapshot or byte-identical future builds.

Raw build/provisioning/Meson/test/dynamic-link logs are retained together in
`build-logs.tar.gz`; their original relative names and byte hashes are listed in
`RAW_LOGS_SHA256.json`. Paths below refer to members of that verified archive.
Expanded duplicate logs were removed from this reference directory.

The first dependency provisioning attempt was cancelled after slow direct
downloads; `builder-direct-slow.log` is retained. Provisioning through the existing
host proxy completed. The first component build then stopped at libssc's required
target Python dependency. `build-attempt-01/` preserves that failure. Adding
`libpython3.13-dev:arm64` to the container fixed it, with no upstream source change.
The same build output directory was reused after retaining the failure evidence.

Validation:

- 24 affected host tests passed, no skips: preparation identity, archive bounds,
  patch failure, source mutation, ARM64 admission, relative links, wrong unit
  location and accidental service enablement. No test routing changes.
- HexagonRPC: `iobuffer` and `hexagonfs` passed under QEMU AArch64.
- Proxy: orientation and mount-matrix executables passed under QEMU; polkit XML
  validation passed using native xmllint. The matrix executable's TAP output
  explicitly skips its French decimal-separator subcase because `fr_FR.UTF-8`
  is unavailable. Meson's executable-level zero-skip count does not cover this
  nested skip. Raw JSON/text logs are retained.
- libssc QRTR/mock runtime tests were compiled but **not run**. This networkless
  cross-build container is not a qualified QRTR service environment.
- Shell syntax checks passed. Full host regression and kernel build:
  `executed: false`, because only independent userspace build helpers changed;
  existing kernel/DT/config/input/charging/USB qualifications were not rerun.
- Two warnings remain in the unchanged source/tool path: resource generator GLib
  version detection defaults to 2.54, and the pinned proxy has an unused `i` at
  `iio-sensor-proxy.c:722`. Neither stopped compilation. No unrelated cleanup.

Offline staging archive:
`out/ssc-arm64/ssc-arm64-stage.tar.gz`, SHA-256
`d462146cb1c03a17789e61e86535c167fcf28ec54ccb0dbda72d853c7e90f7fb`.
It includes upstream installation outputs, mock/development files and licenses;
it is not yet a qualified Debian installation package. No firmware is included.
HexagonRPC service templates were relocated into `/usr/lib/systemd/system`;
no units are enabled. D-Bus/udev files are merely staged, not installed.

Remaining work: qualify Debian runtime dependencies/ABI and package ownership,
prepare owner-supplied signed ADSP/ADSP-DTB and sensor-PD firmware, isolate a copy
of the registry, and register boot-time activation with Test331 rescue. Do not
use Fedora's late-ADSP-start helper on the live desktop: its same-model known
issues record hang/reset risk. Sensor discovery, GNOME automatic rotation and
the mount matrix remain unverified on this device. Test363 pen tip/pressure/
buttons remain pending owner exercise; this offline result does not extend its
position/palm acceptance. Test348 authorization remains unused.
