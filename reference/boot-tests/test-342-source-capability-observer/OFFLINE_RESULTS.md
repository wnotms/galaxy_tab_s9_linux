# Test342 — host observer correction prepared

26 affected native/cleanup/thermal/activation/source-capability tests PASS/no skip,0.213s; Python/shell syntax and frozen inputs verify pass. Existing deployment-adapter qualification reused; no routing/full-suite/build/Actions. Exact Test339 kernel/config/DT/181 modules/boot remains the candidate, no hardware-driver/source/charging-policy change.

Before PD, TCPM can expose5V/3A Type-C source capability. Test341 source150.094937s and ordinary input programming150.122292s establish3A capability versus1.8A input. Old guard rejects that capability. New preentry check allows source<=3A at5V, still requires actual SM5714 input<=1.8A;9V source/input<=1.5A and any postentry physical fixed9 fallback stay strict. A3A actual input, source>3A,9V/input>1.5A, PPS-before-marker, role/thermal/identity/fault or reused entry all reject. Source capability is not a measurement or permission to program3A.

The rejected sample is now emitted before validation. Mock regression confirms the full bad3A-input tuple is recorded before firstfailure/cleanup and no bind occurs. Native1.8A/30s current/fault/parked-refresh/positive-current/physical-fixed-return gates unchanged. Test341 errors and missing rejected-tuple limitation are frozen; no retroactive PASS.

Prepared only; no scope file, stage, flash, bind, PPS request or pump. Fresh accepted331 preflight and subsequent owner continuation are required for execution. Overall charging port NOT_READY. The observation fix is host-tested, not hardware-tested; no false current/power/calibration or45W acceptance.
