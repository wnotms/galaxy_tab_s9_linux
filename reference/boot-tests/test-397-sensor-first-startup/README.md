# Test397 — sensor-first startup hypothesis

Test396 retained-listener startup still produced no SSC400 despite complete
registry reads and UP domain snapshots. This scope changes only explicit launch
order: sensors-PD first, then root-PD. Actual X710 stock sscrpcd is early_hal,
root adsprpcd is main; Fedora has no root-before-sensors dependency. These are
source-supported grounds for comparison, not proof of required mainline timing.
Fedora remote HEAD confirmed unchanged ab123e7; its three patches already reused.
Its suspend restart loop is not copied as a firstboot fix.

Fresh namespace; one early ADSP candidate boot, same exact396 retained daemon/
library/stock assets/kernel/config/DT/181 modules/382vendor trace geometry. Two
PDRcycles2s+2s/8shost;30s health observation and SSC inventory; only if400 appears,
one accelerometer probe. Start intent persists before each operation; either
first failure consumes the attempt, no attachment retry/DSP restart. Historical
root-first helper and registrations unchanged. No proxy/wait repair mixed in.

Preflight ADBroot/Code43/fivepartitions/181modules/config/notes/currentboot health;
battery20–100%,10–<42°C,VBAT3.4–4.45V,4.44Vfloat unchanged. PPS/pump/DCC OFF.
No new kernel/image/build/fullrun/Actions, USB/input/charging changes. Unknown/
new fault stops with raw evidence, mandatory Test370 assets/eightoverlay/vendor
restore and ordinary GNOME return. Keep original396 hostnamed startup anomaly;
current restored desktop has no failed units, no waiver of a new startup fault.

Record SSC_ABSENT/SSC_PRESENT_NO_SAMPLE/SSC_PRESENT_WITH_SAMPLE separately from
physical rotation acceptance. Registration pushed before device mutation. Reuse
unchanged component/observer qualification; execute new scope, actual runtime
wiring and sensor-first lifecycle mocks. Retention388–397, existing382vendor has
explicit current consumer; remove hash-verified Windows stage at completion.

39 affected tests passed,0skips (31 new scope/runtime/lifecycle +8 retained root-first). Fresh accepted5b93e963 fullfive/181/config/notes/ADB/deviceNCM/noCode43/nofailedunit preflight passed.
