# Test327 — Fedora source default-OFF device acceptance

2026-10-06. Registration `bd4251e6`, kernel source `376693d7`, unchanged offline
qualification `f105ffed`. Owner authorized flash and test. This first stage
checks the new actual Fedora charging provider while its boot opt-in is OFF.

## Physical result: PASS within registered default-OFF scope

Exact paired boot/181 modules installed through verified TWRP. Allfive partition
readback matched PACKAGE.json; onlyboot changed. Original Test323 modules saved
in `.gts9-test327-original`, exact323 boot remains the rollback image. BCB cleared,
root unmounted; one normal newboot uniquely attributed from accepted323:
`3f4cf492bb2f4d8c89e805c6ec499642` → `7f9c0caac4ae471a95f492941ceb7ccc`.

Embedded config/kernel notes matched candidate. Driver `sm5440-fedora` bound
hub3/0-0063; DEVICE_ID0x21 in complete kernel journal. Read-only boot parameter
wasN and stableCNTL5=0x01, pumpOFF, at admission and four samples. This driver
has a compiled active path, but it was not activated. No custom ADC_READY or
single-shot deadline acceptance was required or claimed.

PC ordinary source/inputlimit1.8A, Sink/Device, ADB/deviceNCM normal. Observed
30.480s, endpoint SOC84%, VBAT4.296V, pack31.9C, positive packcurrent1.192A.
4.296V is a gauge value within this ordinary switching stage, not SM5440 ADC
calibration or evidence of direct charging. SM5714 float4.44V unchanged.
Full kernel journal preserved; no detected CPU-stall/panic/new kernel fault,
no new failed unit or Code43. Newboot WiFi SSH authenticated10.139.153.224.
Candidate retained after actual device gates PASS, rollback_required=false.

Before mutation, first hostWiFi attempt to old163 was unreachable fromWSL;
Windows later read its SSHbanner and USB NCM authenticated the same device.
Second preflight stopped because the new read-only reader assumed the old
provider name wassm5440-direct; actual accepted provider wassm5440-passive.
These original host-only errors remain in preflight01/02 with no device writes.
Corrected reader/provider tests and PC-only authenticatedNCM rescue were included
in the pushed registration. No failed physical run was rewritten or replayed.

## Reused qualification and next stage

21 new runner/gate tests passed; unchanged final155 affected tests, kernel
build75.858s, W1/sparse and config/DT/module/protected audit reused. No new
kernel/full-suite run for registration or results. No changes to DTS, SM5714,
USB/DWC3/adbd/rootfs/CPU, protections or ordinary fixed5/9 ceilings.

PPS and pumpON **not tested**. Full higher-power port remains **NOT READY**.
Current SOC84 exceeds the separate direct-entry SOC<80 limit. Requested owner
USB unplug for discharge, preservingWiFi; no forced workload or threshold change.
After fresh entry conditions, separately register/hash1.8A boot opt-in and a
short LenovoC1/C2empty run. No newADC repair, 3A/45W acceptance or current ramp
is inferred from this default-OFF result.

Artifacts and exact Test323 fallback are recorded in PACKAGE.json; raw command,
full journal/source timestamps/history/readback/endpoint evidence sealed in
SHA256.json. The current native build cache is Fedora source, not an old native
ADC provider. Historical Test326 timeout remains unchanged.
