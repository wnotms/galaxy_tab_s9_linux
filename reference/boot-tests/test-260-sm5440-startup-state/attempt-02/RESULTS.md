# Test260 attempt02: bounded passive acceptance passed

Qualified source6fbafede was installed as paired boot/vendor_boot +181 modules,
with readback of all five partitions and current/fallback module verification.
Boot `18bce160ddda4c5b9f27f8429f204b59` uniquely follows accepted Test255 in
persistent Debian journal history. Registration34649dc5 and recovery inspection
were pushed before permanent writes; install record92d7e5b0 was pushed before
normal Debian boot. First candidate ADB identity at uptime8.29s matches the sealed
config/notes. No new kernel build/full regression was needed.

The first source event is retained, not masked:

- Passive SM5440 revision2 probes at0.151885s, pump activation unavailable.
- Startup confirmation pending at0.290025s.
- Raw first fault0x80 at0.290045s: INT=00 00 62 00, STATUS=00 00 20 00,
  mode01/01, protectionsCNTL2=f2/VBUSCNTL=e7/VBATCNTL=37/PRTNCNTL=fe,
  reported VBUS4.767V/VBAT3.6005V/IBUS0A/die29C.
- Two new safe conversions complete confirmation at2.609795s,2.319770s after
  pending, within the5s bound. Same protections, inactive live fault/mode,
  startup warning/classification retained. Admission HealthGood/OFF-backed ADC.
- Final complete kernel journal has the same single startup classification;
  no repeated/live REVBLK or VBAT_OVP. Test2580x82 remains a historical failure.

ADB-first hardware evidence preceded any NCM authentication. Windows preferred
APIPA changed from baseline169.254.74.160 to169.254.59.206/16 after this boot.
The explicit readiness gate found matching direct WSLeth2 route and NIC9 in its
first sample (12.879s metadata capture, not measured APIPA recovery). One bound
Windows TCP/banner and one source-bound SSH authentication passed, no retry or
observed unready state. This is one new-boot observation, not proof of the old
Test259 timeout's cause or general startup/reconnect reliability.

Observation completed **150.197s /30 samples**, same boot:

| Reported quantity | Range |
| --- | --- |
| Battery temperature |28.7–29.3C |
| Battery voltage (SM5714 gauge) |3.921–3.941V |
| Battery SOC |56% |
| SM5440 VBUS |4.906–4.913V |
| SM5440 IBUS |0A throughout |
| SM5440 die temperature |26.5–27.5C |

All sample battery/passive health gates passed; Sink/Device, no failed systemd
unit, no new kernel fault/CPU stall/panic, no Code43. ADB throughout periodic
checks, final NCM and Wi-Fi authentication pass; all181 actual candidate module
hashes match. Full kernel journals at admission/initial/final, incremental
journals per sample and command stdout/stderr/UTC/status are preserved. Known
startup/aux bridge/regulator warnings remain known warnings, not erased evidence.

Device remains on the passed Test260 **passive** candidate. Exact Test255
fallback boot/vendor/module files are retained; .gts9-test260-original is the
new original-module slot, older Test258/Test259 tested modules and prior backups
are preserved. Rollback was not needed. No PPS request, pumpON, input-current/
protection/float/thermal/USB/adbd/rootfs configuration change occurred.

Host-only adapter6 and actual Test260 archive install/restore5 pass. Reuse source
6fbafede full1290/driver23, unchanged artifacts; no repeated build/full/CI. Attempt01
unsupported journal option is preserved as a STOP before device deployment;
attempt02 inherited its original runtime capture timestamps and freshly checked
sameboot/config/notes/battery/failedunit/history before maintenance. Raw Windows
locale/CRLF/blank lines/trailing spaces are retained byte-for-byte; source/JSON
whitespace checks and archived hash checks are separate from raw-log formatting.

Limits: this accepts one bounded ordinaryPCUSB passive startup/observation only.
It is not physical ADC calibration, OCP/protection qualification, PPS/direct
charging, suspend/resume, charger reconnect, high-current or long-term reliability
acceptance. SM5440 startup VBAT versus SM5714 gauge requires a separate physical
ADC audit before any active handoff; the raw startup value is not calibrated.
No inference that Test2580x82 was benign or all historical CPU stalls are fixed.

Next is separately registered ADC/protection/PM/transaction validation planning;
no automatic additional physical attempt, PPS adapter or pump activation.
**Passive bounded acceptance: PASS with retained startup warning.**
**Active Stage3: NOT READY.**
