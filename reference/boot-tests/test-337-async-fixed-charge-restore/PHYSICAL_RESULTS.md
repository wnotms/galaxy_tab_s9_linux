# Test337 physical result — PASS, exact Test331 restored

Completed 2026-10-07. **PASS_RESTORED_ACCEPTED331** within the registered
single pump-OFF PPS/fixed-return, ordinary charge and unplug scope.
This accepts the Test336 ordinary-charge recovery correction in this bounded
round. It is not charge-pump activation, high-power or long reliability acceptance.

## Attribution and candidate identity

Owner connected PC, authorized continuation, then connected Lenovo YG65G C1
(C2 empty) and booted System once from TWRP; later unplugged and reconnected PC.
Source `86f7b6787f4d807f488f39818ae08f2b08f6f0eb`, Linux7.2-rc3 pin unchanged.
Test337 was registered/pushed before mutation and reused qualified build/tests.

| Identity | Value |
| --- | --- |
| Accepted331 preflight boot | `245457825f864f33ac57d81714ebb776` |
| Uniquely attributed candidate boot | `abf8901d246d4b65ab525f74b9379869` |
| Restored331 attributed boot | `6dc80750ebdf41e7a4a898befdec7c63` |
| Exact embedded config, both | `51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a` |
| Candidate notes | `39a825d12b9c4beb6a2cd2d8d7b5a62f120c00c4bc3d6da02382345e23e113d2` |
| Candidate boot image | `39bf84766d298eee444a2739ab24005a0ba37402d686aa4ab6928cba0cc4e2ab` |
| Restored331 notes | `03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95` |
| Restored331 boot | `025ebea4282524751bace461ce96beef85c01ea65a4d2b117106c7cdfe0ab815` |

New admission consumed the actual flat authenticated discovery result;
WiFi10.91.255.27 and complete journal histories proved unique attribution.
No extra candidate boot, repeated native operation or pump ON was used.

## Native roundtrip and ordinary restore

Full kernel journal/source timestamps and ordered events are retained in
[charge/kernel-json.txt](charge/kernel-json.txt) and
[charge/native-recovery-timeline.json](charge/native-recovery-timeline.json).

| Kernel-source boot seconds | Event |
| --- | --- |
| 10.715981 | PPS OFF negotiated, source generation9, lease1, target8940mV/1800mA |
| 10.894118 | Internal ADC9267mV,3 samples/151ms/range9267–9267mV/rawIBUS0/OFF |
| 11.201740 | Fixed return verified,9267000uV,3 samples/116ms/range9267–9267mV/rawIBUS0/OFF |
| 11.201766 | Native terminal complete,lease0/fixed_return1/pump_ON0 |
| 11.248754 | Verified ordinary charging reprogrammed,1500mA input/2100mA battery target |

Ordinary programming logged **0.046988 seconds** after the native terminal.
Internal ADC is not independently calibrated VBUS/power measurement. One owned
API operation may include multiple TCPM protocol Requests; this is not a claim
of exactly one wire message.

Ordinary fixed9 charging held **30.925363 seconds**,30 samples. Endpoint61%,
4.086V,25.3°C,net+2.067A; input limit1.5A, TCPMONLINE1/fixed9/1.5A, Sink/Device,
physical pump OFF and direct flagN. Real pack sensor matched25.3°C. Source
capability USB_TYPEPD_PPS was correctly retained while ONLINE1 denotes fixed
operation. No enum8 property warnings were observed (Test336 had412).
Full journal/failed-unit/identity/OFF/responsiveness gates passed.

## Unplug

Same candidate boot restored Discharging with USB/TCPM ONLINE0 and negative
battery current for **15.640536 seconds**.137 samples include pre-unplug wait;
only the measured discharging interval counts as the registered15-second window.
Endpoint62%,4.002V,24.9°C,net−0.628A, physical pump OFF, real thermistor valid.
Full [discharge journal](discharge/kernel-json.txt) retained; no new classified
kernel fault/suspect or failed-unit evidence. Native transaction was not replayed.

## Unconditional rollback and final acceptance

After PC reconnection, exact331 original181-file directory and boot were
restored. All five partitions and complete module hashes matched; BCB cleared,
root unmounted and one normal reboot uniquely attributed to final boot above.
The Test337 diagnostic module directory is retained separately, not active.

[Final acceptance](final-acceptance/summary.json):57%,3.965V,28.1°C,
net+0.954A on PC USB, input1.8A. ADB, strict authenticated WiFi10.91.255.166,
deviceNCM and Windows noCode43 passed. Captured SSH identity independently
matches the same final boot/machine/config/notes. Exact normal cmdline, physical
OFF and PPSfalse, full kernel journal and empty failed-unit gate passed.
SOC readings are raw driver telemetry across different boots; the difference
from the earlier62% is not a measured discharge amount or capacity experiment.
Mutation state `accepted331-restored`, `rollback_required=false`.

## Limits and next work

No CPU-stall/panic signature or new classified serious kernel fault was found
within these windows. This does not prove all historical wedges share one cause
or future long reliability. Fixed5/9 current ceilings1.8/1.5A, float4.44V and
fail-closed thermal/PM policy unchanged; no production deployment of the candidate.

This physical stage changed no source/config/DTS/rootfs/USB/adbd/current policy.
Tests/build `executed:false`; unchanged295+65 host/C and81.492s build/static
qualification reused, no fullrun/CI/Actions. Original Test336 STOP/evidence remains.

Next active-pump/high-power work requires a separately qualified candidate and
registered conservative scope; Test337 alone authorizes no pump/current advance.
Overall charging port remains **NOT READY**. Preserve exact331 rollback.

New machine-readable result: `physical-summary.json`; physical evidence hashes:
`PHYSICAL_SHA256.json`. Frozen original registration/results/INPUTS are unchanged.
Expired Windows327 image duplicates retired192MiB; canonical same-hash Image/boot
still used by in-window328/330 retained. See
[cleanup record](../../host-storage-cleanup/2026-10-07-test337-image-retirement/summary.json).
