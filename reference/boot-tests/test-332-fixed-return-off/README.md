# Test332 — one-shot fixed9V OFF-only return proof

Purpose: qualify the actual fixed return producer/source-bound release with
pump always OFF. This does not test a PPS-to-fixed voltage transition, ADC
calibration, pump activation, high power or PPS entry.

Baseline: accepted Test331 boot025ebea4/config51ba6a9c/notes03c9c46e/paired181,
normal cmdline, direct_charge=N, SM5714 ordinary charge and Test253/254 retained.
Candidate: source48cc5d16, same config/DTB/protected hardware policy, new notes
ff706409. Single boot-only `sm5440_fedora.fixed_return_check=1`; direct_charge
must remainN. Defaultfalse/check readonly; simultaneous direct opt-in refused.
The existing worker waits read-only on PC fixed5V, ends by300s from probe.
One healthy fixed9V9V/1–1.5A/SOC20–<80/VBAT3.5–<4.3V/pack20–<38C admission
triggers one OFF/ADC-channels-existing0xdf/switching-lease/coherent-pack/physical
stability/release transaction. No reset/hwinit, PPS or ON or current increase.
One attempt only; any refusal ends scheduling. PM/remove use existing drain.

Preflight once: identity/allfive/181, OFF, native ADB/Code0, deviceNCM,
authenticatedWiFi, pack sensor, services/roles, fulljournal/unique history,
fresh332 backup slots; formal331 and323 rescue remain intact.
Commit/push registration before one paired TWRPboot/module install/readback,
BCBclear/unmount/normal boot. Admit unique candidate PCboot/rescue/OFF.
Start a read-only persistent WiFi observer; owner detaches PC and connects
LenovoYG65G C2 18W,C1 empty. No reboot or simultaneous PC connection.
Wait≤240s, then observe≥30s after kernel reports successful native release.
Kernel maximum300s starts at probe; host failure cannot extend that deadline.

PASS requires unique complete/proof events in complete same-boot kernel JSON,
source epoch and lease positive, ≥3 consecutive zero-raw-IBUS measurements over
≥100ms, entire range≤100mV inside8.55–9.45V, checked OFF and source-bound fresh
release. Every observer sample OFF/sameboot/healthy pack. Endpoint fixed9V,
SM5714 USB PD online/input≤1.5A, positive battery current, no new kernelfault.
ADC/register observations are not claimed to be calibrated or independent
conversions. Full journal/source timestamps retained, not grep-only evidence.

First failure: stop collection/test, no repeat; owner immediately disconnects
charger and returns PC. Unconditionally restore exact Test331 OFF boot+paired181
from fresh332original, allfive/module readback and one final normal startup.
This occurs after PASS too: do not retain boot-only check opt-in. If rescue is
lost, request manualTWRP; do not blindly write an unknown partition layout.
Keep accepted323 as secondary known-good ordinary/fixed-PD rescue; existing
`.gts9-test331-original` is untouched. No automatic new PPS/pump/current scope.

Host tests cover opt-in/token identity, realfailure vs logerror, physical proof
bounds/completeness/finalswitching, OFF/rescue/stop and collision-safe module swap.
Reuse253affected kernel tests/build80.69s/sparse12.81s/config+DT/181 qualification;
no full suite, Actions or repeated build for runner/docs. Retention window becomes
Test323–332; retire expired Test322 image copies after completion with manifest.
