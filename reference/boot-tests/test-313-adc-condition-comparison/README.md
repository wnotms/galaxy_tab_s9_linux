# Test313 — one OFF-mode ENHIZ/ADC comparison on accepted ordinary recovery

Question: does one vendor-backed ADC operating-condition conversion differ from
Test311's inherited pump-OFF/ENHIZ-set condition? Previous adjacent gauge/ADC
pairs differ263/211/329mV. Cause remains UNKNOWN; neither sensor is independent
calibration. Reuse qualified Test312 diagnostics with the SM5714 ordinary-program
recovery accepted in Test311. Do not deploy older305/306 kernel sources.

One PC-USB candidate boot,15-second same-boot endpoint, then unconditional exact
accepted311(Test308) boot+181-module restoration and one final health check.
Allfive partition hashes and exact181 baseline modules before mutation/readback;
only boot+paired modules written. Fresh normal baseline config/notes/boot history,
Good/present pack,SOC5..<80,VBAT3.5..<4.3V,20..<38C,real pack thermal,SDP/AICL cap,
ADB/services/usb0/SinkDevice and Code0 required. No charger swap/replug is needed.
Use approved recovery helper/ordinary reboot, native validated TWRP, unique313
module slots, exact write/readback, clearBCB; unknown recovery never blind writes.

The diagnostic kernel itself verifies pumpOFF, records CNTL6/read-validity,
disables ADC, clears only ENHIZ bit7, performs one bounded conversion, then
restores/verifies ADC-off and original bit7. First I2C/ADC/provenance/control/
restoration error stops. Preserve original fault and cleanup error separately.
No second conversion/reschedule/companion/calibration/freshness grant. Source
condition gate is byte-identical to306; ordinary witness/reader byte-identical311.

Collector uses corrected Debian by-partlabel/PARTNAME checks. Device operations
are serial; controls and real pack thermal before full kernel/history, one20s
history query, then Windows and one host NCM probe. Unique attribution mandatory.
Candidate condition error in partial readiness stops immediately. Actual ordinary
controls checked at preflight, candidate admission, endpoint and restored baseline.
Device NCM mandatory; a host-only TCP255 is separately recorded without repeated
waiting. Save full raw journal and original ADC/gauge timestamps, not grep alone.

First actual failure: preserve raw evidence and restore accepted311 once when
safe. Successful acquisition also restores accepted311 once; diagnostic kernel
never retained. Incomplete cleanup requires manual recovery, no blind retry.
No PPS/APDO request, pumpON, protection/current/thermal changes, forced drift,
reset, USB/adbd/rootfs/DTS/TCPM change. Fixed5V<=1.8A/9V<=1.5A/4.44V maintained.
No additional kernel build/full regression/Actions; qualified312 artifacts reused.

Windows stage D:\android\gts9-active\gts9-test313: reuse old311 files by exact
content via hardlinks; copy only new candidate image/modules/helper as needed.
Hardlinks are not independent backups. Source/artifact/evidence seals mandatory;
commit/push registration before physical mutation. Import/package/host tests do
not contact a device. Physical status remains NOT EXECUTED at registration.

```sh
python3 reference/boot-tests/test-313-adc-condition-comparison/host_flow.py preflight
python3 reference/boot-tests/test-313-adc-condition-comparison/host_flow.py run
```

Capture is an operating-condition experiment, not a cause proof or direct-charge
acceptance. ADC/physical freshness/protection/actuator/PPS/handoff/fallback/PM
qualification still needed. Full Stage3 remains NOT READY.
