# Test337 — async fixed-charge return correction

Purpose: verify that the corrected asynchronous lease release restores ordinary
SM5714 fixed9 switching charging after one native pump-OFF PPS roundtrip.
Test336's STOP remains unchanged. This is a new correction candidate, not a
repetition of the unchanged failed profile. Offline qualification is in
`reference/charging/sm5714-async-fixed-restore/RESULTS.md`.

## Frozen baseline and variables

Accepted Test331 default OFF is the rollback. Linux7.2-rc3/config51/DT233a remain
unchanged;181 modules paired with the candidate. Only SM5714 pending restore and
standard USB type declaration changed in kernel source. No TCPM/DWC3/gadget,
DTS/config/adbd/rootfs/current/float/thermal policy change. New host runner uses
flat authenticated discovery results; fixed USB_TYPE may describe PPS-capable
source while TCPM ONLINE1 represents fixed charging.

This registration is **PREPARED, physical_executed=false**, and has no execution
scope. Do not stage/deploy/contact the device from an import or qualification.
Explicit Test337 pump-OFF authorization and fresh PC/WiFi preflight are needed.
No old Test336 authorization file is copied or interpreted as Test337 scope.

## Registered sequence

1. Fresh accepted331 PC/ADB/enrolled WiFi/deviceNCM/OFF/pack and baseline gates;
   verify exact rollback/package/allfive/181 at deployment boundaries.
2. One candidate install to boot and matched modules; owner C1-only then TWRP
   System once. Windows stage is gts9-test337, rollback is exact331.
3. Attribute unique new boot and candidate config/notes; preserve full journals.
   Native worker performs one owned PPS API operation at1800mA, physical OFF ADC
   sample, bounded fixed9 physical proof and authorization release. Pump stays OFF.
4. Healthy fixed9 ordinary charging must settle within10s, then remain healthy
   for30s. Source capability PD_PPS does not bypass actual ONLINE/voltage/current/
   status/temperature/identity/OFF/role/response gates.
5. Owner unplug; observe15s correct discharging. Unconditionally restore exact
   accepted331 allfive/181 and verify ADB/WiFi/deviceNCM/normal cmdline/OFF.

SOC20–<80, preparation≤75; VBAT3.5–<4.3V; real pack20–<38°C. PPS target8.2–10.5V,
20mV step/current≤1.8A; native physical sampling≤10.8V and±500mV target,3 samples
/100ms/range≤100mV/rawIBUS0/OFF. Fixed physical8.55–9.45V, same sampling/OFF rules.
Registered native wait/response bounds remain unchanged, no timeout extension.
Actual fixed5≤1.8A/fixed9≤1.5A, float4.44V and thermal failclosed retained.

First new fault, unknown identity, unexplained boot, missing evidence, Code43,
lost rescue, native failure, unbounded settling, charge loss or unsafe pack stops
and restores331. No pumpON, high-power/current advance, independent ADC/power
calibration or production reliability acceptance. Future active work needs a
separate candidate/test after this return path is accepted.
