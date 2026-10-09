# Native QRTR inventory — actual socket path qualified, SSC not tested

On Test331 boot78ec the frozen helper failed with EINVAL/no replies. Pinned
qrtr_bind requires the socket-local node, not guessed node0. The separate
corrected helper reads getsockname before requesting an ephemeral port.

The corrected same-boot command exits0 with explicit complete marker, two
raw control packets and one advertised numeric service69/instance257/node7/
port1. Localnode1/port16387, query0.0107s. This is nameserver inventory, not
QMI method response or ADSP sensor discovery. ADSP was left offline; no service
start, rootfs installation, flash, reboot, PPS or pump operation.

8 affected tests PASS/0skip. No kernel or full host build executed: no kernel/
config/DT/routing change. Frozen old helper and Test366/369 inputs untouched;
next independent SSC registration must use corrected helper. Source patch is
limited to kernel-assigned bind node plus explanatory comments/docstring.

The earlier oemconfig lookup remains unresolved rather than a proven root
cause: actual bounded X710 vendor audit and captured stock DSP manifest had
no such file. Use already compiled upstream verbose Fedora-derived RPC daemon
for the next active-ADSP trace instead of inventing another-device library.
