# Test331 — corrected PPS candidate default-OFF acceptance

2026-10-06: **device scope PASS**, candidate retained. Registered/pushed
`c1a10d2c` before mutation. Kernel source`1f1d8568`, offline qualification
`11c5967f`. This is a default-OFF startup/ordinary PC charging acceptance;
**PPS and the charge pump were not enabled or hardware-validated.**

Preflight accepted Test323, boot`67673895d2d042879ffbbb2d293ce339`,61%/4.053V/32.3C,
physical OFF, ordinary charging, exactallfive/181, authenticatedWiFi/ADB and
WindowsCode0. Fresh331 original/stage/tested module slots were absent.

Verified TWRP install: paired181 swap, original181 retained in
`/usr/lib/modules/.gts9-test331-original`, onlyboot rewritten, allfive partition
readback, staged hashes, BCBclear and rootunmount. One uniquely attributed
normal candidate boot`6b76a591f91648c0917d207b772175b4` from the baseline above; all
ordered cmdline tokens/duplicates retained. Config51ba6a9c/notes03c9c46e exact;
DCC absent, real pack thermal enabled, no failed unit, Sink/Device, direct
parameterN, boundsm5440-fedora and CNTL5=0x01 OFF. Readiness waited for actual
ADB/services/NCM/WiFi rather than treating disconnect as successful reboot.

Observed30.508s with four independent read-only
CNTL5 samples, all0x01/OFF and sameboot. End:62%,
4.059V, 31.9C, pack current
+1.264A, input ceiling1.8A.
These are battery telemetry and policy input limit, not externally measured
adapter power. Full source-timestamped kernel JSON at admission/endpoint,
no new kernel fault or unexplained reboot. Windows composite/ADB/NCM Code0,
NCM adapterUp, nativeADB and authenticatedWiFi10.139.153.193/deviceNCM healthy.

27 new host tests passed in0.245s. A real temporary-module fixture exposed an
old shell compound-and collision check bypassing`set -e`;331 uses three
separate refusals before any rename. The initial failing host log remains.
The original327/330 runner/results were not changed. Kernel build/187 affected
tests/W1+sparse/config/DT pairing were reused; no duplicate build/full suite,
Actions, USB/adbd/rootfs/SM5714/charging policy edits. Config/DT match the
previous tested Fedora candidate; exact fresh module archive is paired here.

Rollback not needed after scopePASS. Exact Test323 boot/archive and saved331
original181 remain available. Do not reuse consumed327-original or restore
failed327-tested as an accepted baseline. `mutation-state.json` explicitly
records retaineddefaultOFF and rollback_required=false.

The corrected leased PPS path is host-tested but unexercised here. Independent
fixed9 physical return proof timeout remains unresolved: no relaxation, ADC
repair, PPS replay, current escalation or new pump scope occurred. Full direct
charging remains **NOT_READY**; subsequent PPS scope needs a justified physical
return policy and separate registration.
