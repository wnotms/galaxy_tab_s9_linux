# Test269 — offline PPS operating-point update

Port the next bounded higher-power policy component, not device activation.
Read docs/X710_PPS_RETARGET.md before implementation. Current device stays on
Test263 with Test267 STOP and Test268 discharge result unchanged. No device
command, flash/reboot, PPS, pumpON, current increase or startup fault gate change.

Add a separately callable unwired transaction to recompute PPS headroom from
fresh battery/source facts while pumpOFF, then reprogram the bounded pump-current
limit before any ON. Keep initial PPS<=1800mA, <=10500mV; never automatically
increase current on a bigger source offer. Retain fixed5V1800/9V1500mA, float4440mV,
thermal/USB/DCC/containers. This is not a CV/termination implementation or OCP
qualification. TCPM still owns protocol; the live TCPC still refuses PPS.

Qualify real C with mocked fault/time/source callbacks, retain all old tests;
one final policy-offline Image/DTB/modules build and full host suite, W=1/sparse,
exact config/DT/protected/artifact audit. Use isolated269 build/output directories,
no old outputs overwritten. Reuse qualification for results-only commits.

Physical gate remains NOT READY: full-pack passive startup fault, fresh ADC,
nonzero current calibration, protection/cutoff response and live PM/lifetime
adapter remain outstanding. Plan these separately; no hardware request from
this registration and no automatic physical test after offline qualification.
