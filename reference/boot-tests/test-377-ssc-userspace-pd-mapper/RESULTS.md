# Test377 results — SSC userspace mapper and accelerometer discovery

Test377 ran one fresh candidate boot using the unchanged Test370 kernel,
modules, DTS and charging policy. It installed only the qualified Fedora
userspace `pd-mapper` and `libqrtr1` packages, started the existing
`sensorsPD` path once, and kept PPS/direct charging disabled.

The candidate boot (`73eb05b9-b050-43ad-9d1f-3dc9883bb4b7`) passed the early
ADSP/FastRPC/native-SoC identity gate. `sensorsPD` remained active and its
bounded trace showed registry/configuration file access. However, all bounded
`ssccli --sensor accelerometer` probes returned `SSC QMI Service not found`.
The before/after QRTR inventories contain no newly exposed SSC QMI service.
Consequently no IIO proxy was started and no desktop or charging path was
changed.

The test stopped on the first bounded discovery failure and restored the
accepted Test370 baseline. The restored boot has GDM, SSH and ADB active,
ADSP offline as on the baseline, and no Test377 package or service remains.
This is a userspace SSC discovery failure, not evidence of a kernel, USB,
charging or CPU fault. Repeating the same `pd-mapper`/`libqrtr1` combination
is not justified; the next sensor investigation must explain the absent SSC
QMI service (for example by tracing the mapper/service registration path)
before enabling a persistent desktop sensor backend.
