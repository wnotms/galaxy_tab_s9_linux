# Test275 — passive fresh-acquisition acceptance

Independent physical test registered before deployment. Owner renewed physical
authorization (continued “继续，允许实机测试” / “继续”) covers this passive step.
No PPS request, pump ON, charger swap or current increase is authorized here.

Reuse sealed Test272 provider399eb497 Image/config/DTB/181 modules and Test274
observer10d57da0/module9d66c080. Installed Test263 is the exact rollback baseline.
Only boot and matched181module directory change; vendor_boot/init_boot/dtbo/
vbmeta, rootfs services, Type-C/USB policy, hardware configuration and protection
remain unchanged. Observer stays outside the181module archive, copied to /tmp;
one explicit load, no autoload/rootfs installation/force-load.

One candidate boot on existing PC USB, Sink/Device, SDP500mA. Entry pack20..<38°C,
gauge3.5..<4.3V/Good/present, passiveGood/fault0/notpending/OFF/IBUS0, exact config/
notes/cmdline/DCCabsence, ADB/deviceNCM/Wi-Fi. One complete install identity check
and readback, not repeated during sampling. Preserve exact263boot/181modules and
all older rollback directories in new275slots.

After healthy entry, load observer once. Maximum8 fresh requests,1s between
successes, unchanged100ms API validity. Collect cached result/paired snapshot
in bounded30s window. First nonzero provider/consumer status stops requests and
ends collection; preserve/unload, NEVER reload/retry, clear latch, change ADC
averaging/cadence/deadline or startup voltage gate. A correct busy/timeout refusal
is a timing observation, not CPU wedge proof and not a successful acquisition.
Completed8calls require all genuine timestamps and deadline/voltage/current/
temperature gates. Cached reads cause no request. Independent accuracy unknown.

Save full kernel journal at entry/end/first fault and sameboot endpoint once;
ADB/Wi-Fi/deviceusb0/sshd normal is device acceptance. Host NCM TCP is not required
by owner. Acquisition outcome reported separately from device health. A host
collector defect preserves original STOP and permits only separately named
evidence completion, not an automatic hardware window/reflash. Genuine safety,
CPU/kernel/rescue/identity fault stops, safe recovery and exact263 rollback.

Unresolved startup SMMU variants from271/273 are **diagnostic attribution only**:
priority3, source first200ms, exactSID0x1c00/cb9/fsr0x402/fsynr0x660021/S1CBNDX102,
IOVA[0xb8000000,0xbab00000), at most10context+10syndrome records, equalcounts.
Keep every original suspect in local scan; do not change global parser, call
them fixed/harmless/CLEAN or accept later/different/increased errors. All CPU/
panic/RCU/CSD/passive faults and other suspects still stop. Existing accepted
startup register/FSR and boundedQCA classification reused without widening.
External unsigned .ko may produce expected O/E taints; actual faults still stop.

Qualification: reuse Test272 full1424/build and final Test274 full1475/module
W1/sparse, all unchanged. New local collector/gate tests + syntax only; no
kernel rebuild/full regression/CI for host-only registration/evidence changes.
Package exact appended Image/DTB/embedded config verified offline. Generated
unused vbmeta was replaced by accepted263exact copy and will not be flashed.

Timing success does not qualify nonzero-current ADC, hardware OCP, independently
calibrated VBUS, live PPS adapter or PM. ActiveStage3 remains NOT READY.
