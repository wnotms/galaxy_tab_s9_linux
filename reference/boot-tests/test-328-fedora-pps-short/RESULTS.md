# Test328 — STOP before PPS: host command-line whitespace bug

Eligible52% PC preflight passed. Boot-only opt-in c064e61a installed with five
partition readbacks and unchanged181 module pairing. Candidate4d64e996 runs
exact config51ba6a9c/notes5ec694b4, direct parameterY, stock5V Sink/Device.
The loader places the opt-in between compiled/default and loader parameters;
removing it produces one separator where recorded default had two. Ordered
parameter tokens are exactly identical after removing only that opt-in, but
host byte comparison raises `release/cmdline`. The original host exception,
full candidate journal and raw command line are preserved. No new kernel
fault/suspect found. No charger attachment/PPS30s/guardian/pump observation
was executed; do not report a physical PPS pass.

Registered install exception handling already restored the exact default-OFF
Test327 boot, allfive readbacks/181 pairing/BCBclear/rootunmount. Final normal
222efdcc, config/notes unchanged, independent CNTL5 OFF, parameterN, healthy
ADB/Windowsno43/deviceNCM/authenticatedWiFi10.139.153.150,52%/3.937V/29.4°C.
Rollback_required=false. Original high-SOC and Code43 incoming incidents remain
separate; Test329 recovery did not qualify PPS or relax its gates.

This is a host parser defect, not evidence of device instability. Repair only
opt-in token comparison; preserve ordering/duplicates/exact configuration,
notes and all safety gates. New independent Test330 registration may reuse
identical payload/guard. No kernel rebuild/full test suite/source change;
existing qualification reused. Full PPS/direct-charge port remains NOT_READY.
