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

Future independent SSC collection should pair this snapshot with the corrected
`qrtr-native-snapshot.py` nameserver inventory and upstream verbose hexagonrpc trace. A driver
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

## Native QRTR local-node correction

A separate same-boot inventory attempt with the frozen `qrtr-snapshot.py`
returned `EINVAL`, before receiving any reply. Pinned `net/qrtr/af_qrtr.c`
initializes a fresh socket with the actual local node; `qrtr_bind()` rejects an
address whose node differs. Node0 is not a wildcard. `qrtr_getname()` exposes the
node before binding, so the corrected helper reads it and requests only an
ephemeral port. It still checks the exact local nameserver origin, retains every
raw reply, requires an explicit end marker, limits time/packet count and sends
DEL_LOOKUP before closing. No QMI method is invoked.

On the same Test331 boot with ADSP offline, the corrected helper completes in
about11ms, local node1/port16387. It records one advertised service69/instance257
at node7/port1 plus the explicit end marker. These numeric values are retained
without claiming this is SSC or that it responds to a QMI method. Eight fixture
tests pass, including a kernel-style bind guard for local node7 (neither a
hardcoded0 nor1 is acceptable), timeout, malformed/foreign replies, bind failure
cleanup and packet limits. Full raw before/after evidence lives in
`reference/desktop-bringup/ssc-qrtr-offline-adsp/`.

The old script remains byte-for-byte unchanged because Test366/369 registered
inputs include it. Use the separate corrected helper in future SSC registration;
do not reinterpret old stopped tests or change an already started scope.
