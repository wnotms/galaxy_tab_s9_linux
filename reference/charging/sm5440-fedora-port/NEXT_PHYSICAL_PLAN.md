# Next physical registration — Fedora source implementation

This is a plan, not a registration or an authorization to deploy/activate.
Use a new Test327 registration and push it before any device mutation. Keep
Test326 unchanged and do not repeat the custom single-shot ADC diagnosis.

1. Default-OFF candidate: one combined rescue/battery/identity preflight, verify
   exact Test323 rollback boot/modules, install only paired candidate boot/modules
   through the existing recovery workflow, then verify readback. One normal
   startup: config/notes/boot attribution, pack telemetry, default pump OFF, fixed
   charging and one device-side ADB/NCM/Wi-Fi check. Preserve full kernel journal
   at the stage boundary. No PPS or pump ON in this stage.
2. Separately register the boot opt-in `sm5440_fedora.direct_charge=1`; generate
   and hash its distinct boot package before deployment. Require SOC5–<80%,
   VBAT3.5–<4.3V, real pack15–<38C, healthy fixed9V and working Wi-Fi rescue.
   Lenovo YG65G USB-C1 with C2 empty has recorded APDO5–11V3A (Test273).
   Initial PPS cap1.8A; no current ramp. Capture source epoch, negotiated request,
   physical SM5440 VBUS/IBUS/VBAT/die temp, pack current/temp/SOC and mode/fault.
   First bounded pump run30s; if clean, separately registered5min then20min.
3. Verify unplug/fixed fallback and charger-to-PC reconnect once each. Record
   pump OFF proof and lease release; device-side transport is the completion
   criterion, host-only transient defects are recorded separately.

Stop at the first unknown safety/identity state, unexpected restart/kernel fault,
source disappearance, I2C error, ADC invalidity, repeated REVBLK/PD reset,
unsettled VBUS, pack>=42C, VBAT>=4.4V, die>=85C or actual input over1.8A. Expected
VBUS must match the bounded requested value/source range, with upper9V fixed
limit9.5V and PPS target ceiling10.5V. Do not request an out-of-range value or
heat the pack to test protection. Failure preserves the raw first evidence and
stops further PPS attempts. Verify pump OFF, exit PPS/fixed restore, release
switching lease only on verified safe state; unknown OFF keeps watchdog and
switching inhibited. Use recovery for exact Test323 boot/181 module restoration
if the driver cannot prove safe fallback or device rescue is lost.

Reuse this offline qualification for unchanged source/artifacts. No full-suite
repeat or long ADC audit per stage. Higher2.0/2.25/2.5/3.0A work is outside this
candidate and requires a later policy change plus separate acceptance.
