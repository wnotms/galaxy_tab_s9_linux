# Test300 — retained passive thermal registration fix

**PASSIVE_THERMAL_FIX_DEVICE_ACCEPTED; candidate retained.**
Source9173df11 qualified299, registrationfe9ca9ce pushed before mutation.
ONE PCUSB boot `57535beda62648d0aaaa3071ac8332e5`; no cable action/PPS/pump activation.
Onlypassive descriptor.no_thermal=true corrects a noncontinuous diagnostic cache
being registered as a thermal sensor. Temperature read errors remain errors;
no stale/fabricated values, fault reset, global thermal suppression or threshold
change. Pack IIO/safety/ordinary charging/current/4440mV/configDT/USB/adbd unchanged.

After admission and15sdevice endpoint, complete thermal enumeration shows NO
`sm5440-passive` zone and one enabled `sm5714-battery` zone (nowzone37 by dynamic
name lookup). Real pack temperature31.1C→31.5C matches standard power_supply
within registered consecutive-read tolerance. No224s wait required: absence
of registration prevents that passive zone's later disable warning. This does
not guarantee all future sensors/readings or longterm kernel stability.

ADB/device ssh/adbd/gadget/usb0/SinkDevice/confignotes/DCC absence/Goodbattery/
WindowsCode0/full kernelJSON and unique boot attribution pass. No detected new
CPU/panic/RCU/CSD signature in the registered window. Known bounded display
startup diagnostics retained. Pack41%,
3.821V,31.5C,
IBAT-416mA; PC input remains ordinary500mA.
HostNCM candidate probe status255 with device services/WindowsCode0 healthy;
recorded once, no prolonged retry/host authentication claim or CPU-wedge inference.

SM5440 passive startup remains REFUSED/fault1/pending1, cache unavailable for
active decisions; pumpOFF/IBUS0. This fix does not repair ADC calibration/startup
qualification or prove continuous die temperature/OCP/PM/direct-charge safety.
Removing automatic thermal registration does not waive any charging admission.

Allfive partitions read back at installation; onlyboot changed,181candidate
module files verified before and after atomic replacement. BCBclear/rootunmounted.
Registered PASS retains the qualified candidate to fix owner symptom and avoid
unnecessary flash/rollback cycles. Exact263boot +unique300original181modules and
older rescue backups remain available; rollback executed:false because PASS.
Currentdevice is source9173df11, NOT Test263. See CURRENT_STATUS/PACKAGE/summary.

## Validation and next

Reuse2995registration+24passive/ARM64/W1sparse/exactconfigDT/protected181;
8runner tests pass, including dynamic zone numbering and prevention of reusing
old263warning exemption on a new candidate/battery zone. Full/build repeat
executed:false for runner/evidence-only edits; no Actions/CI. Raw preflight/source
incident/photo/newkernel/thermal/device/write evidence retained and hashed.

Resume liveTCPM/PPS coordination next with unchanged fixed baseline fallback.
PPS-capable source USB_TYPE must be distinguished from ONLINE2 activePPS; fixed
source may advertise PDPPS while ONLINE1 remains fixed. ADC/OCP/PM and actual
PPS/pump backend remain separate unresolved requirements; activeStage3NOTREADY,
fullport goalactive. No repeat of the failed delay-only ADC hypothesis.
