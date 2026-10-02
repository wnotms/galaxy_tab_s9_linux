# Test283 — offline startup ADC event classification and prompt recovery readiness

Scope: fix the host classification that stopped Test282, and the unnecessary
recovery wait, without changing hardware/software installed on the device.
This is offline replay/mock qualification, not a physical retry of Test282.

`gate.py` retains frozen275 identity/health and journal/CPU/SMMU rules. The only
startup register variation is INT4 bit0: Samsung ADCUPDATED, current ADC_READY.
INT4 must be exactly00 or01; watchdog/timer/unknown bits stop. All other literal
INT/STATUS/OFF/protection facts and original ADC decoding/ranges are unchanged.
One early REVBLK event, matching priorities, initial timestamp<=1s,
waiting-to-fault<=100ms and confirmation<=5s remain mandatory. The **same boot's
current complete identity and healthy OFF snapshot are required** before journal
admission. Incremental/new/repeated fault, missing confirmation or unsafe state
still stops. Retain the original event; no charge/timing/stability claim.

`host_flow.py` recognizes native ADB `recovery` as transport-ready immediately.
This is not permission to write: TWRP kernel/board/root/partition and backup
identity checks still follow. Duplicate/unauthorized/unexpected target states
stop; no automatic reboot, load or flash. Existing3s readiness polling is kept.

Tests replay sealed282 candidate/final raw evidence, reject all254 other INT4
values and adverse raw/state/time/CPU cases, compare old journal rules by AST,
and mock recovery transitions/deadline/no-repeat behavior. Source/fixtures are
sealed. Historical275/277/278/279/280/281/282 evidence and verdicts unchanged.

No device command, transfer, reboot, flash, tracefs write, observer load, PPS,
pumpON or current change. No kernel/config/DTB/ADC/deadline/USB/rootfs change.
Reuse unchanged272provider/276observer/build qualification; run affected host
tests/syntax only. No suite routing changes, full regression, build or CI.

Future physical acquisition needs its own pushed registration/new backup slots,
complete essential live admission and unconditional263 rollback. Reuse279
collector/280coordinator/276observer; first refusal stops; no automatic retry.
Active Stage3 remains NOT READY; device remains at last verified Test263.
