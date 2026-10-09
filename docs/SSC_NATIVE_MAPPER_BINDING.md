# Native PD-mapper observation correction

Test365's `runtime-discovery/unit-state.stderr` records a failed lookup at
`/sys/bus/platform/drivers/qcom-pd-mapper`. That is the wrong bus/path for the
pinned Linux 7.2-rc3 implementation. Its empty `@@native-mapper` section does
not establish an absent driver. The historical command and STOP evidence stay
unchanged; no sensor discovery or rotation success is inferred.

The pinned source at a13c140cc289c0b7b3770bce5b3ad42ab35074aa establishes:

| Source | Observation |
| --- | --- |
| `drivers/soc/qcom/Makefile` | `CONFIG_QCOM_PD_MAPPER` builds `qcom_pd_mapper.o` |
| `drivers/soc/qcom/qcom_pd_mapper.c` | Auxiliary driver `.name = "qcom-pdm-mapper"`, ID `qcom_common.pd-mapper` |
| `drivers/base/auxiliary.c` | Registered driver name prefixes `KBUILD_MODNAME` |
| `drivers/remoteproc/qcom_common.c` | `pdm_notify_prepare()` creates an auxiliary device with `.name = "pd-mapper"`; unprepare removes it |

The resulting driver directory is
`/sys/bus/auxiliary/drivers/qcom_pd_mapper.qcom-pdm-mapper`; device entries are
`/sys/bus/auxiliary/devices/qcom_common.pd-mapper.<id>`. The native mapper already
has SM8550 root/sensor domain instance74. The board's compatible includes
`qcom,sm8550`. Do not start a second userspace mapper to compensate for the old
path error.

`userspace/sensors/native-mapper-snapshot.py --boot-id <current-boot-id>` captures
the actual device, modalias and driver links, registration state and boot identity
before/after reads. It reports bound, unbound, no-device or unexpected-binding;
missing data, broken links and changed boots fail evidence. Even a bound result
explicitly leaves service response and sensor discovery unverified. This helper
does not start remoteproc, services or QMI transactions and does not write sysfs.

Future independent SSC collection should pair this snapshot with the existing
bounded QRTR nameserver inventory and upstream verbose hexagonrpc trace. A driver
binding alone cannot prove Servreg answers, SSC service registration, accelerometer
samples or desktop rotation. Test365's `Could not open oemconfig.so` also remains
an observation, not a proved missing-library root cause. Fedora's same-model
hexagonrpc command and root/sensors PD ordering are already reflected in the
prepared isolated runtime; another wholesale runtime copy would not correct this
observer error.

The read-only check on current Test331 boot
`78ec1906-4713-4837-9acc-fe245647d7cf` finds the correct auxiliary driver
**registered**, with **no mapper device**. The independently captured current
ADSP state is offline. The source creates the auxiliary device during remoteproc
prepare, so this offline observation is consistent with that lifecycle; it is
not an active-ADSP binding failure or a sensor acceptance result. The command
returns2 to preserve the distinction from a bound result. Raw output, command
status, source hashes and 12 host fixture checks are archived under
`reference/desktop-bringup/ssc-native-mapper/`.

This change does not alter Test369's registered GPU/native-Escape scope, frozen
inputs, kernel, modules, DTB, device services or charging policy. Host filesystem
fixtures qualify observation behavior, not physical SSC operation. Deployment
and an actual SSC lookup remain future independent evidence after the corrected
kernel's normal desktop acceptance.
