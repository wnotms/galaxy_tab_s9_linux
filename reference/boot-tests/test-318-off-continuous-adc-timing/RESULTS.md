# Test318 — continuous READY timeout; accepted311 restored

**STOP_CONTINUOUS_READY_TIMEOUT_BASELINE_RESTORED**. One registered candidate
boot and one unconditional matched rollback, no repeated sampling or candidate.

Fresh NORMAL accepted311 preflight passed at22%/31.3C: exact five partitions,
181 modules, ordinary PC500mA controls/float4440, nativeADB/deviceNCM/authenticated
Wi-Fi/WindowsCode0. Unchanged qualified44c2190a candidate was installed boot-only
with181 matching files; allfive readback passed. No DTS/rootfs/USB/current/PPS change.

Candidate `df1ce8c0-a95e-42c4-8911-fb2c48b8a569` is uniquely attributed from
`8146a9cf-c160-4e13-a351-0db1a8f958a7`; config/notes and NORMALcmdline match.
Raw snapshot and full1065-row kernel journal independently prove the driver
stopped at3.289442s with `OFF continuous ADC diagnostic stopped: -110; cleanup=0`.
Native source/pack admission succeeded (fixed5V1800mA, pack22%/3.781V/27.8C).
Continuous control0x0f/channel0xdf readbacks pass, pumpmode0x01/OFF,
VBUSPOK and no consumed/live fault at last poll. No new INT4 READY observed:
0/8 samples,38 polls. Transaction2696..3285ms (589ms); enabled2779ms,
cleanup completed3285ms (506ms later). Last pending poll3260..3272ms has
INT=00 00 00 00. There is NO successful ADC raw read/valid conversion to classify.

The original host first-failure `services/role/DCC/failed` is retained unchanged.
Its6.31s packet has SSHinactive, adbd/gadgetactive, Sink/Device, DCCabsent and
no failed unit. This combined message obscured the earlier physical ADC timeout;
it does not turn this into merely a host-only defect or a passed device test.
No new kernel CPU-stall/panic signature is present in saved evidence, but candidate
full rescue/15s endpoint was not accepted. Known startup/display diagnostics stay
separate, with no general stability-clean claim.

Checked OFF succeeded; ADC cleanup/readback restored exactly0x0c/0xdf. Both
operation and cleanup outcomes are explicit. No ENHIZ/protection/current/Q4/PPS/
pumpON operation, no100ms active gate relaxation. The fail-closed driver stopped
its sample worker rather than restamping stale data as a healthy fresh sample.

Automatic rollback completed exact accepted311 boot and original181 files;
allfive hashes match, BCB cleared and root unmounted. Final normalboot
`e71954cf-fb78-4ee3-aa76-cbaafe5841fc` is uniquely attributed. Actual config/notes/
normalcmdline/ordinarycontrols/DCC/realthermal/nativeADB/deviceNCM/WindowsCode0/
NCM host probe match; authenticated Wi-Fi at10.139.153.184 proves sameboot/machine.
Final additional rescue packet22%/3.759V/31.4C/Good, pumpOFF/IBUS0/fault0.
No manual device operation or recovery was required. Full new/final/first-failure
journals and commands retained; full logs compressed losslessly where noted.

Build/host regression executed:false this physical round; reuse unchanged
qualified source/profile/toolchain/artifact/stage and16 parser/lifecycle tests.
No Actions. See ANALYSIS.md for source comparison and limits; current source
profile must not be flashed again unchanged. Overall charging port **NOT READY**.
