# SSC userspace offline source preparation

Current Test331 boot `28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af` was inspected
read-only. ADSP is offline, its requested firmware directory is absent,
FastRPC ADSP has no device node, and the only IIO device is `spmi-adc5-gen3`.
The four SSC userspace components are not installed. `dpkg-query`'s `un` entry
for iio-sensor-proxy does not mean installed. No failed unit was present.

Prepared libssc 0.4.4, pd-mapper 1.1, hexagonrpc 0.4.0, and iio-sensor-proxy
3.9 with SHA-256-bound upstream archives and five unmodified same-model Fedora
patches. Remote Fedora HEAD remains ab123e7d1dbc0cbcd35661f9761197e977b15aa9.
All patches applied with zero fuzz; the proxy availability patch has a recorded
two-line offset. `prepared.json` records the complete resulting file hashes and
patch transcripts; source bytes stay in `out/ssc-sources/prepared-clean`.

Validation: 10 affected source-preparation host tests passed. No full regression
or kernel build was run: kernel/DTS/config/build routing was unchanged. The
preparer's real four-source invocation completed successfully. No ARM64
userspace component was compiled or installed; no sensor/rotation acceptance
is claimed. The next work is Debian ARM64 packaging and signed Samsung ADSP/
sensorspd/registry staging, followed by a separately registered controlled boot.
No remoteproc start, service/config change, flash, reboot, PPS or pump action
was performed. Test363's active desktop and Test348 scope remain unchanged.
