# Test293 — software refusal cause proved; physical voltage cause unresolved

**OFFLINE_STARTUP_SAMPLE_REFUSAL_ATTRIBUTED.** No new device commands or boot.
The exact Test292 final boot b06bb6c2/config f2891de2/notes fea0613f was replayed.

| Captured source fact | Result |
|---|---|
| startup REVBLK waiting / confirmation failure | 297987 /2602086 source BOOTTIME us |
| delta |2304099us |
| retained startup / final-sample jiffies |4294892370 /4294892946 |
| delta at resolved CONFIG_HZ=250 |576ticks=2304000us |
| five-second startup deadline |not expired; timestamp checks agree within99us |
| final ADC VBAT bytes |5a a8 |
| actual C13-bit raw |2901 |
| actual C VBAT |2048000+2901*500=3498500uV |
| unchanged startup minimum |3500000uV; sample is1500uV below |
| remaining startup predicates |OFF01/01,ready,online,VBUS4.905V,IBUS0,die25.5C,no new fault,all four protections match |

Actual Test263 sm5440_startup_matches() rejects the sample. The sole failing
sample predicate is **VBAT_outside_startup_window**, not the5s deadline or a
reported I2C read failure (last_sample_error0). This explains the driver's
software refusal; it does not explain why that physical channel read low.
Startup REVBLK was retained, not reset or declared harmless. f2/e7/37/fe remain
raw protection provenance, not an OCP acceptance certificate.

[VENDOR] sm5440_convert_adc() VBAT uses the same13-bit layout and2048+raw/2 mV.
Its integer result is3498mV; the mainline microvolt result preserves the extra
0.5mV. This rounding difference is not a cause of crossing the3.5V threshold.
Vendor also declines ordinary OFF-state ADC use below CHECK_VBAT; this is an
important acceptance limitation, not proof of the channel/wiring/root cause.
The current explicit OFF-mode converter can produce evidence, but cannot claim
independent accuracy from that formula alone. No guessed bit2/averaging fix.

The fuel gauge reported3879000uV in the packet at uptime283.59s, whereas the
retained sample was published near2.602s. The arithmetic difference-380500uV
is **not a simultaneous comparison or calibration offset**. Sensor acquisition
instants and node equivalence are not independently established. An invalid/stale
retained sample cannot authorize PPS or be restamped as a fresh measurement.

## Local validation

21affected tests PASS/0failure/error/skip, actual immutable C compiled with
-Wall/-Wextra/-Werror. Boundary cases,512combined predicate vectors and1024
single-byte fault vectors agree with the actual C implementation. Real replay,
ADC-byte mismatch, conflicting uevent, duplicate/missing journal transitions,
wrong boot/notes/config/HZ/DCC, time disagreement/rollover/expiry and refusal
profiles are covered. CLI replay and syntax pass. Initial test run exposed real
uevent identical TYPE duplication and a fixture-added blank JSON line; parser
handles only identical uevent repetition and fixture appends a valid record.
Initial failure log retained. The later oracle was pinned to263 rather than
introducing a source-text freeze on future drivers, and final21tests passed.
263/290/291/292 evidence seals unchanged. Kernel/full regression executed:false;
no source/build input/routing change, no new full-regression claim or Actions.

## Next porting step

Do not replay Test292 or lower the3.5V/100ms gates. We now know which startup
condition blocks this boot, so a future sensor qualification can target genuinely
new same-window SM5440/gauge provenance and the PC-vs-fixed9V condition already
seen in Test264. A separately registered test must state that changed hypothesis,
keep current fixed5V<=1.8A/9V<=1.5A/4440mV and pumpOFF/PPSoff, and collect essential
rescue/identity/health at one boundary. Existing263cached data cannot prove active
freshness or calibration. Fullport still needs live TCPM/PPS coordination, checked
SM5440 protection/cutoff, actual ADC/current acceptance and PM/handoff qualification.
**ActiveStage3 NOT READY.** No new physical test is authorized by this analysis.
