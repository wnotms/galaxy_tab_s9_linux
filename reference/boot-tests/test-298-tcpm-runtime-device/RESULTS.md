# Test298 — real TCPM runtime observation

**RUNTIME_DEVICE_DIAGNOSTIC_COMPLETED; exact263 restored.**
Sourceeefef33f/Test297, registration15f1bae6 pushed before physical mutation.
ONE PCUSB candidate boot `1b47865f2f8644be8c2d664dd9db9858`, one0400 current-port call at
17.275s boot uptime. APIret0, instance1/sourcegeneration9/budgetgeneration14,
one SourcePDO0x3701912c (fixed5V/3A offer), current fixed TCPM budget5V/1.8A;
standard supply agrees. No controller pointer escape/extra raw I2C/observermodule/
PSY setter/PPS/pump/current increase. Reading completed in the same millisecond;
this timestamp resolution does not establish a zero-duration atomic transaction.

15-second sameboot device endpoint passed: ADB/device ssh/adbd/gadget/usb0,
Sink/Device, config/notes/DCC absence/Goodbattery/WindowsCode0 and full kernelJSON.
No detected CPU/panic/RCU/CSD signature within this bounded window. Known bounded
startup display messages remain diagnostic; this is not broad stability acceptance.
This candidate's passive startup fault0, cachedIBUS0/OFF. Earlier startup refusal
and physical ADC/OCP/PM uncertainties remain unresolved; no direct-charge grant.

TCPM voltage/current are negotiated policy observations, not physical VBUS or
measured charging power. SM5714 actual PC input limit remained500mA/SDP; endpoint
pack42%,3.825V,31.1C,IBAT-389mA. Do not call5V*1.8A a measured9W charge rate.

One host NCM probe per boundary: preflight authenticated sameboot; candidate
and final probes status255, while device NCM/services/ADB and WindowsCode0 were
healthy. Recorded host limitation, no retry/extended wait or CPU-wedge inference.

Unconditional nativeTWRP rollback verified allfive exact263 partition hashes and
181module files; original/tested298 slots/olderbackups retained, BCB cleared and
root unmounted. Final attributed263 boot `acdd2dfc7f8a4970aa57d71edab99df6`;
packGood,43%,3.817V,
29.8C,IBAT-802mA.
No new failed unit/kernel signature/Code43. Device boot/config/notes and roles
normal; no rootfs/USB/adbd/configDT/hardware charge-policy changes.

## Scoped checks and next step

Reuse297119affected/ARM64/W1sparse/exactconfigDT/protected181 qualification;
10runner cases pass. Initial runner fixture PDO typo retained and corrected
before registration. Initial read-only preflight partition alias error retained;
Debian by-partlabel read verifies allfive before mutation. Full/build repeat
executed:false for host/evidence-only changes; no CI/Actions.

The missing live read prerequisite is now implemented/compiled/host-tested and
once device-exercised. It does not implement a live PPS setter/coordinator or
pump operation. Next advance actual TCPM/PPS coordination behind lifecycle,
source-generation, battery/physicalADC/OCP/PM gates; no more same delay-only
ADC trials and no guessedoffset/threshold waivers. Active Stage3 NOT READY,
full wired-port goal remains active.
