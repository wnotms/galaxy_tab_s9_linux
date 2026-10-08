# Test348 — confirmed-C1 twenty-minute PPS acceptance

**REGISTERED OFFLINE; execution not authorized, device stays TWRP.**
Purpose: one independently attributed1200000ms conservative PPS/pump window,
followed by fixed9 ordinary charging, discharge, PC rescue and exact331 paired
restoration to TWRP. It is not a higher-current or vendor-equivalent charging test.

## Qualified identity and limits

Reuse source0b731b4a and charging/test347-twenty-minute-followup:167 affected tests,
ARM64/modules84.982s, W=1/sparse13.493s; config/DT/release unchanged from331,
181 matching module files. This runner requires both once=1 and once_ms=1200000.
Hardware1700mA, PPS/raw stop1800mA; fixed5V<=1.8A/9V<=1.5A, float4.44V unchanged.
Preparation/activationSOC20..60; natural target58 reservesPC/install headroom.
Test347 went69→71 over300s plus ordinary charge;60 is a conservative bring-up
margin, not a rate estimate. Entrypack20..<38C/VBAT3.5..<4.3V; runtimeSOC<80,
pack<42C/die<85C/VBAT<4.4V. Source/APDO, epoch/lease, physical measurement,
thermal, I2C/fault/PM/detach and fixed-return gates remain unchanged.

## Future sequence after explicit authorization

The device currently contains exact331 and remainsTWRP per owner instruction.
After a new physical authorization, first boot331 normally for fresh baseline
identity/rescue/telemetry and natural discharge if needed; do not flash directly
from an unverified recovery state. FreshPC preflight verifies allfive/181/config/
notes/journal/DCC/OFF/rescue. One paired install and attributedPCcandidateboot;
drain readiness worker and proveOFF/unbound. Wait for ownerC1 handoff with **no
guardian running**. Fresh boot-bound reply<=120s and fixed9 admission precede
sole launch. Persist launch request/PID; lost response means adopt original PID,
never relaunch/rebind. Kernel1200s, guardian1260s, hostmonitor1300s/outer1500s;
fault/sample/transport/park timeouts are unchanged. Live observation timeout
re-polls the same confirmed process, never grants another attempt.

Collect full sameboot journal/native duration and raw telemetry. Then fixed9
ordinary charge30s, ownerunplug/discharge15s, onePCADB/deviceNCM/noCode43 check,
exact331/allfive/original181 restore, Debian unmounted, verified finalTWRP.
No restored Debian reboot/runtime acceptance is performed at this endpoint.
Any actual failure stops the attempt, preserves primary+cleanup separately and
restores331; no second activation. Unknown evidence cannot be promoted toPASS.

## Evidence and exclusions

Separate namespaces for preparation, installation/admission, owner confirmation,
guardian handle/raw events, collection, charge/discharge, PCreturn and restoration.
No full partition/module rehash per sample. Raw journal at boundaries/firstfault;
grep summaries are derived. Preserve Test347 and older failures unchanged.
No higher-current/45W/calibration/hard-realtime/long-term/full-port claim. No
Windows staging or device operation during registration. See OFFLINE_RESULTS.md.
