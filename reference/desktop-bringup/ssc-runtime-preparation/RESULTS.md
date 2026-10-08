# SSC Debian runtime preparation — 2026-10-08

Verdict: **DEBIAN_ARM64_PACKAGES_NOT_DEPLOYED**. The qualified Fedora-derived
ARM64 outputs from `baa46693` were packaged without recompilation or source
changes. No sensor service, firmware, kernel, DT, input module, USB or charging
configuration was installed or changed on the tablet. No reboot or flash.

Four packages are in `out/ssc-debs/`; exact versions, dependencies, hashes and
payload files are in `PACKAGES.json`:

| Package | Version | Contents |
| --- | --- | --- |
| libssc2 | 0.4.4+gts9.1 | libssc.so.2 and ssccli |
| gts9-hexagonrpc | 0.4.0+gts9.1 | FastRPC daemon/library, original unit templates, permission rule and account declaration |
| pd-mapper | 1.1+gts9.1 | Mapper and original unit template |
| iio-sensor-proxy | 3.9+gts9.1 | Proxy linked to SSC, monitor-sensor, original unit/udev/D-Bus/polkit files |

The packager checks the exact qualified build manifest and every staged file,
uses the recorded Debian image with network disabled and an unprivileged UID,
and derives dependency minima using target ELF symbols through `dpkg-shlibdeps`.
The custom libraries have explicit local shlibs mappings. Generated packages are
reopened using `dpkg-deb`: root ownership, ARM64 metadata, exact payload hashes,
disjoint ownership and the reviewed control-file set all passed. No preinst,
postinst, prerm, postrm or enabled-unit links are present. Only the two library
packages request the standard `ldconfig` trigger. Runtime payload excludes
development headers/links, Python mocks and the unused CHRE client. Original
licenses are included.

The FastRPC udev rule matches Fedora
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9` byte-for-byte (SHA-256
`41dfc4e8c4fd88f461a5a6e4a4e86849eb302f8bcb2b5ce2efa9690f5415d52d`).
The new sysusers file declares `fastrpc`; it does not start a daemon. Original
daemon restart policies remain in these offline packages. Before deployment,
register one-attempt overrides, mask/inhibit activation during installation,
provision the account, and keep ADSP offline until a controlled boot experiment.
These are not yet physically qualified installation instructions.

The first packaging attempt failed before creating packages because a host
repository-parent lookup did not apply to `/recipe` inside the container.
`package-attempt-01.log` retains the error; fixing that path allowed packaging.
Later integrity verification used the final recipe recorded in `PACKAGES.json`.

30 affected host tests passed, no skips. They cover preparation/build admission
and Debian payload integrity, changed/missing/extra files, wrong architecture,
unexpected hooks/triggers, links, duplicate/unsafe paths and ownership.
Python/shell syntax checks passed. Full regression and kernel rebuild:
`executed: false`; unchanged compiler/source/DT/config qualifications remain
those in `ssc-offline/BUILD_RESULTS.md`. No CI was started.

Read-only device inventory:

- Two initial SSH banner timeouts occurred while the host used
  `10.30.115.64/16`; the owner confirmed tablet `10.175.236.134`.
  After the host returned to `10.175.236.63/24`, SSH succeeded. No CPU crash
  is inferred from those transport failures.
- Boot stayed `28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af`, Test331 release.
  Battery 53%, 26.5°C, Discharging at inventory. ADSP remains offline and the
  relevant firmware/HexagonFS roots are absent. No sensor runtime installed.
- Installed runtime library versions satisfy the observed generated minima for
  libc, GLib, GUdev, polkit, QMI/QRTR-GLib and xz. The two missing libraries are
  `libprotobuf-c1` and `libqrtr1`; stage Debian ARM64 dependency archives before
  any future installation. Both matching Debian archives have now been downloaded
  on the host into `out/ssc-debs/dependencies`; their hashes/control metadata are
  in `dependency-archives.json`. `dependency-assessment.json` records every
  generated constraint checked with Debian version comparison. No dependency
  was installed on the tablet. Candidate libssc2 satisfies the proxy's local
  dependency but is not yet installed.
- `blkid -p` confirms stock `apnhlos` = `/dev/sda17` (vfat), `dsp` =
  `/dev/sda16` (ext4), and `persist` = `/dev/sda5` (ext4). None was mounted by
  this package-preparation step. Layout and inventory stdout/stderr are raw
  evidence; missing packages explain dpkg-query's nonzero status.

Next: read only the required stock firmware/DSP/sensor files into a private
host staging directory, preserve per-file hashes and source mtimes, and check
MDT segment completeness. Keep firmware/calibration content out of Git and
do not expose the actual Android persist partition to HexagonRPC. Prepare the
isolated registry and controlled early boot/rollback registration before any
activation. Automatic rotation remains untested; Test363 pen-tip/pressure
coverage still awaits owner exercise. Test348 authorization remains unused.

Raw inventory/transport, package-attempt, shlibdeps, download and host-test logs
are preserved in `raw-logs.tar.gz`, under the original relative names referenced
above. `RAW_LOGS_SHA256.json` verifies each member; expanded duplicate logs are
removed. Summary/manifests and read-only collection code remain directly readable.
