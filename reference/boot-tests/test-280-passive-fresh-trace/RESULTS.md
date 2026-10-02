# Test280 — offline coordinator qualified; physical preflight stopped

Registration/evidence commit `a6d38d51` is pushed to origin/test. Task baseline
`e68c9f7f`; no source/build or hardware policy change.

## Actual device facts

Read-only boot `31e9a2127e7c41909c8ddd601badc85b` has exact Test263 embedded config
`f2891de2…` and notes `fea0613f…`. Owner subsequently confirmed manual power-on
or reboot: this is **not an unexplained reboot**. No agent reboot was issued.
However `/proc/cmdline` includes `lpcharge=1` and related additions, unlike the
accepted normal boot. Raw `/proc/cmdline`, chosen bootargs and exact token diff
are preserved. The identity gate correctly refuses it; manual boot attribution
does not silently exempt the runtime-input mismatch.

ADB responds, Wi-Fi SSH10.125.29.166 authenticates the same boot, device usb0/
sshd and existing ADB services are active. Battery69%/4.050V/27.7C/Good; net
current -286mA on PC SDP500mA (Charging status is not net battery gain). Passive
monitor healthy/fault0/OFF01/01/IBUS0, cached VBUS4.918V/die22.5C; DCC absent and
no systemd failed units. Full kernel journal passes the unchanged diagnostic
gate with no detected CPU fault. These are bounded read-only facts, not fresh
ADC qualification or uninterrupted stability proof.

Existing tracefs and Python3.13.5 are available; workqueue format/boot clock and
private formatting options were inspected read-only. Six recorded read-only
commands plus initial ADB discovery were used. No observer load, tracefs write,
file transfer, reboot, flash, module replacement, PPS/pump enable or current
change. Windows Code43 probe and partition/module hash repetitions were omitted
after the early identity stop; neither is claimed passed. Device remains on263;
rollback is unnecessary because no deployment occurred. No retry of280.

## Actual offline work

`coordinator.py` directly owns the qualified279Session, eliminating separate
collector-process/ready-file races. The future flow is setup/start, one276load,
cached terminal result, fixed500ms tail, evidence/owned cleanup, then unload.
Load ambiguity, first refusal, cancellation, deadline and every cleanup error
stop the operation without another load/request. Initial preflight/ownership
refusal never unloads somebody else's observer.

`observer_gate.py` copies only the frozen275pure parser/constants; host tests
verify identical ASTs. Trace entries/returns are bound to cached observer count,
provider errno and its outer BOOTTIME-ms envelope. This establishes which request
records belong to the observer, not which worker caused them or ADC duration.
Hardware/timing/endpoint acceptance stays false until separately qualified.

**24 affected mock tests and syntax passed**, zero failure/error/skip in the final
run. An initial mock fixture emitted fields before `row=` and was corrected;
the frozen parser was not weakened. Tests include unknown/preloaded module,
cmdline/boot mismatch, setup/load/read/deadline/interruption/cleanup/unload errors,
counter loss, single-load behavior and clock/count/errno binding. Synthetic result
is explicitly labeled mock evidence.

All198 tracked protected files match e68c9f7f;275380/277417/27825/27943 historical
sealed files verified. Reuse unchanged27950 and272/2761481/W=1/sparse qualification.
Kernel build/full regression executed:false; no routing change or Actions/CI.

## Remaining work

The coordinator is a library, **not a deployment command**. A future physical
wrapper still needs accepted normal-boot preflight, paired installation readback,
recorded bounded ops, same-boot battery/journal/rescue endpoint and exact263
rollback under a separately pushed registration. Test280 remains
STOP_READONLY_PREFLIGHT_CMDLINE_IDENTITY even after the owner explanation.
No automatic reboot/identity exemption/retry. Actual trace attribution and the
four -110 branches remain UNKNOWN; active Stage3 remains NOT READY.
