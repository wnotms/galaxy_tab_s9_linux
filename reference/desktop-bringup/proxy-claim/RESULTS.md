# Early sensor-proxy claims — compiled, not deployed

Test389 remains the latest physical sensor observation: no SSC400 publication
or real sensor samples. This change repairs a separate, reproduced userspace
race. It does not explain the firmware's absent sensor service, and does not
establish automatic rotation on the tablet.

## Composition

The byte-identical S9 Ultra reference is
[`fix-early-ssc-claim-race.patch`](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/32273b0a410b3e73b20a3a2451e24260fb2a36bd/packaging/sensors/fix-early-ssc-claim-race.patch).
Its provenance/hash and the check of newer HEAD916e2f13 are retained in
`../libssc-wait/UPSTREAM_CHECK.json`. The local original remains the pinned
Fedora-derived iio-sensor-proxy3.9, including its two existing patches.

Fedora already starts a previously claimed sensor after opening it. Importing
the reference's whole startup block would duplicate that behavior. The adapted
patch preserves the single start and sets the delayed first-reading event flag.
It also prepares every client table and delayed-invocation array before exporting
D-Bus objects, and defers polling until the selected driver has an opened device.

A local addition guards Release/client disappearance before open. Merely fixing
Claim leaves this second NULL-device path: the reference-semantics comparison
reproduces both failures. Only `src/iio-sensor-proxy.c` changes. D-Bus XML,
authorization policy, sensor drivers, hardware discovery and measurement logic
are unchanged. The public patch copy is evidence; the adapted patch is applied.
`proxy-claim.json` pins all67 base files and both patches. Preparation rejects
drift, extra files, links, overlapping/existing output and unexpected changes.
Default `sources.json`, base prepared sources and historical qualifications stay
unchanged; this is an explicit, separate candidate profile.

## Executed verification

- 38 affected host tests PASS,0skip:6 new composition cases,7 shared libssc
  preparation cases and25 existing source/build admission cases. No routing
  change, full regression, kernel build or GitHub Actions.
- Complete ARM64 proxy and monitor compile with SSC support explicitly enabled,
  using the previously qualified blocking-wait libssc and the unchanged pinned
  networkless Debian builder. Three upstream tests PASS: policy XML,
  orientation and mount matrix. This does not include hardware/SSC integration.
- 12 real private-D-Bus/ARM64 cases qualify: three expected fatal-critical
  controls, one adapted-reference positive control and eight final cases.

| Profile/case | Observation |
| --- | --- |
| Original,claim during discovery | NULL delayed array, fatal `g_ptr_array_add` |
| Adapted reference,claim during discovery | One polling start, no critical |
| Adapted reference,release or vanished client before open | NULL device, fatal `sensor_device` |
| Final,no clients | No polling start/stop; availability broadcast |
| Final,claim before discovery/during discovery/during open | One start; duplicate claim does not restart; first reading clears delayed state |
| Final,release or vanished client before open | No polling start/stop; no critical |
| Final,claim after open | Reply waits for the first synthetic reading, then completes |
| Final,open failure | No device/driver or polling; normal no-sensor exit |

The harness compiles the actual proxy C handlers, resource XML and real
GLib/GIO/GUdev/Polkit libraries. Messages, properties, name watches, nested main
context dispatch, delayed method replies and measurement callback dispatch use
real private D-Bus IPC. GUdev identity/location, hardware discovery/open/polling,
the input reading and authorization decision are mocked. This is not a sensor,
orientation, firmware, system-bus permissions or device acceptance test.
Fatal controls exit133; they are not accepted as deadline timeouts. Each case
has a test-only deadline, owned container cleanup and a separately owned bus.
The final bus and containers were removed. No tablet bus or service was touched.

Host fixture failures remain separate: the first harness compile stopped on
GLib vtable padding under `-Werror`; the first IPC attempt could not obtain a
GUdev loopback identity inside the isolated namespace and its QEMU abort left a
container after the CLI timeout; a second identity attempt also failed before
testing the race. The fixture now explicitly mocks hardware identity and removes
only its own named container even on timeout. These are host failures, not device
faults or successful race controls. Final qualification uses the same incremental
build directory; no repeated kernel builds were needed.

## Reproduction

Prepare an absent independent output:

```sh
python3 userspace/sensors/proxy_claim_profile.py \
  --source out/ssc-sources/prepared-clean/iio-sensor-proxy \
  --output out/proxy-claim/sources
```

For the reference-semantics control, copy that output into a separate directory
and remove only `DEVICE_FOR_TYPE(driver_type) != NULL &&` from `client_release`;
do not remove the Claim guard. `REFERENCE_SOURCE.json` identifies the expected
resulting C hash. This is an adapted control, not an assertion that the raw S9
Ultra patch applies unchanged over Fedora's existing patches.

`BUILD.json` records the exact networkless Docker argv, read-only source/recipe/
fixture/libssc mounts, input hashes and output mount. The committed
`compile-proxy-claim.sh` builds the entire proxy, runs upstream tests and compiles
all three real C comparison harnesses. Then run:

```sh
python3 tests/fixtures/run_proxy_claim.py --build out/proxy-claim/build
```

Preserve any prior raw qualification before reusing outputs. `RUNTIME.json`
identifies the three-file binary/license archive; it contains no installer or
systemd/udev/D-Bus policy files. The previously qualified libssc library is a
separate dependency. Neither archive has been installed.

## Device boundary and next step

The owner's PC connection now exposes ADB. A short read finds the same accepted
Test370 boot `0f360b00-4f24-43cf-8ce5-1aa135c5f7a3`, active GDM and100%/31.5°C.
No flash, reboot, rootfs replacement, sensor RPC/ADSP activation, registry reset
or charging/USB/kernel/config/DTS/input change occurred. PPS/pump/DCC stay OFF.
Test389 evidence and Test370 restoration remain authoritative.

The two independent client fixes are now offline-qualified. Next resolve the
actual firmware-initialization/X710 prerequisite boundary before registering a
new meaningful physical sensor test; these client fixes alone do not justify
replaying Test389's unchanged failed startup. SSC publication, real samples and
GNOME automatic rotation remain unverified. The porting goal remains active.
