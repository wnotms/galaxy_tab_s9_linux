# Test334 — fixed-return OFF check with preparation SOC margin

## Purpose and status

Prepare a new fixed9 OFF-only scope after Test333 stopped at SOC80, before
physical proof. Its exact native ERANGE field remains unknown. This does not
rewrite333 or diagnose an ADC failure. **Preparation only: no recovery request,
flash, module swap or reboot is authorized by the preparation command.** A fresh
PC preflight and an execution instruction are required before physical run.

Reuse kernel48cc5d16/boot3fe4adf1/config51ba6a9c/notesff706409/DT233a9fee/181
qualification without rebuilding. Added host margin: SOC20–75 inclusive before
recovery request/writes, checked again at live boundary. Native and physical
entry20–<80/VBAT3.5–<4.3V/pack20–<38C remain unchanged. No kernel/config/DTS/
ADC/current/voltage/thermal/USB/rootfs change, no timer extension or retry.

## Registered physical sequence after execution instruction

1. One fresh PC identity/rescue/pack/allfive/181/Code0/OFF/history preflight;
   verify334 module slots absent, staged hashes and registered inputs. Preparation
   expires after600s; a later `preflight` writes a new timestamped namespace,
   binds it via summarySHA and preserves older raw evidence. Installation uses
   only the latest valid snapshot. If SOC>75,
   wait for natural discharge; do not impose heat/high CPU load.
2. Paired install/readback in TWRP, BCBclear/root unmount, then remain there.
3. Owner attaches LenovoYG65G USB-C2 18W/C1empty before selecting System once.
   Native one-shot owns its300s wait. Host finds only the enrolled private /24,
   pins actual registered hostkey and machine/config/notes, attributes new boot.
4. Pump remains OFF. Require one native fixed9 source/lease-bound proof: zero
   rawIBUS, >=3 reads/>=100ms/range<=100mV/VBUS8.55–9.45V, successful native
   release, then >=30s healthy fixed9 switching with complete kernel journal.
   Existing read-only observer, native fresh proof/OFF/health and fault gates
   remain. No PPS/request/ON/reset/init, no manual ADC setup or offset.
5. First fault/refusal/evidence/identity/transport gap stops, no replay. After
   owner returnsPC, unconditionally restore exact accepted331 boot/181/allfive,
   one normal reboot, one final identity/health/rescue/fulljournal admission.
   Restoration-only ordinary SOC<=100/VBAT<=4.44V is not a candidate gate.

## Interpretation and rollback

Only return while the source is already fixed9 is tested. This is not a
PPS-to-fixed transition, ADC calibration, active pump/high-power acceptance or
proof of full charging reliability. Fullport remains NOT READY. No automatic
PPS/current escalation even on PASS. Accepted331 rollback is primary; explicitly
recorded accepted323/331-original remains secondary. New334 module slots isolate
all historical results. Shared formal artifacts and offline qualification stay
unchanged. No Actions/full regression/repeated build for host workflow changes.
