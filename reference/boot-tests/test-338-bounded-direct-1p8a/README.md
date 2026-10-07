# Test338 — one bounded1.8A charge-pump attempt

PREPARED only. Current hardware remains accepted Test331; Test337's pump-OFF
fixed-return/ordinary-charge repair is accepted. Registration is not execution
authorization. New pump-ON scope must be recorded separately before deployment.

Candidate `cf02c822`, same Linux7.2-rc3/config/DT and181 paired module files.
Only select `sm5440_fedora.direct_charge_once=1`; direct_charge/fixed_return_check/
pps_return_check remain false. One automatic kernel-owned attempt,<=30s software
budget,100ms scheduled raw-current monitoring, first fault terminal/no retries.
No5min/20min, higher current,45W,OTG/dock/DP or production acceptance.

## Sequence

1. One combined live331 identity/rescue/pack/OFF/fulljournal preflight; allfive/
   181 once. NativeADB, authenticatedWiFi, deviceNCM, noCode43, normalcmdline.
   Entry20–<80% (preparation<=75%),20–<38C,VBAT3.5–<4.3V/Good/realthermistor.
2. Push scope/registration first; TWRP paired boot/modules staging and readback,
   preserve original331 directory, clearBCB/unmount. Boot once on PC USB.
3. Verify unique candidateboot/config/notes/cmdline, pumpOFF/rescue. Start the
   device-local guardian before asking for C1; it reads stable registers/ADC,
   never IRQ latches or configuration data. Guardian finally unbinds the worker
   and proves OFF/fixed9; no raw PD or pump Request exists in the guardian.
4. Owner PC→LenovoYG65G C1(65W),C2empty,WiFi/no reboot. Wait<=240s. Kernel
   checks owned source/pack, traced init readback, OFF continuous ADC, then PPS
   <=1.8A and one pump start. Poll100ms; park/settle/ON on4s refresh with deadline
   re-arm refusal. Completion requires positive actual pump/gauge samples.
5. Capture complete source-timestamp kernel journal and unique native start/
   refresh/fixed-return/terminal sequence. After automatic return/guardian
   cleanup, allow<=10s healthy ordinary settle then30s fixed9 charging.
6. Owner unplug: sameboot15s Discharging/ONLINE0/negativecurrent. Owner PC return:
   essential ADB/NCM/WiFi/WindowsUSB check; unconditional exact331 allfive/181
   restore and one final normalboot identity/health acceptance. No retained opt-in.

## Stop conditions and limits

First serious kernel fault/stall, unexpectedboot/role/source generation,
Code43/lostWiFi rescue, I2C/readback/ADC/refusal, invalidtemperature/pack,
physicalIBUS>1800000uA, gaugeIBAT>3600000uA, runtimepack>=42C,die>=85C,
VBAT>=4.4V or ADC/gaugeVBAT mismatch>200mV, VBUS outside requested±500mV or
>10.8V, missing/late native proof or500ms monitor delivery gap stops.
No automatic second attempt. Preserve firstfailure/rawjournal. Hardwareunknown
OFF or failedfixedrestore requires unplug and PC/TWRP recovery, not continued PPS.

100ms/30s are software scheduling/observation budgets, not a hard-realtime cutoff
guarantee. Samsung explicitly requires software OCP for SM5440; inherited
CNTL2=0xf2 is not independent HW protection. Init readback/internalADC are not
physical protection qualification or calibrated power measurement. Do not
deliberately heat/overvolt/overcurrent to test limits. Overall port NOT_READY.

Unchanged ordinary input5V<=1.8A/9V<=1.5A, packfloat4.44V,SM5440regulation4.4V,
thermal/PM/ownership/DCC/USB/adbd/CPU policies. No rootfs service/config changes.
Offline qualification is in `reference/charging/sm5440-bounded-direct/`.
