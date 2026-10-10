# Test393 — standard PDR initial-state listener cycles

Test392's fresh unregister returned result1/error9 and no state. This scope
changes the observer to the actual Linux PDR lifecycle: register enable=1,
validate initial state and indications, ACK valid same-peer/exact-domain tokens,
unregister enable=0 on the **same** client, close. This is separately registered
use, not an automatic escalation or unchanged Test392 replay.

One attributed early-ADSP candidate boot, at most two independent listener cycles:
before and after one ordered root→sensor RPC startup/30s health observation.
Each cycle reserves2s for register/state/ACK and2s for cleanup; host command bound
8s. No listen retry or DSP restart. Initial absent/invalid state, LOCATOR_ERROR,
unverified ACK/unregister/closure or any other first fault stops before RPC.
The observer owns no PD resources and ACKs validated notifications promptly.
See `reference/desktop-bringup/ssc-pdr-listener/RESULTS.md` for schema and limits.

Reuse exact Test392 kernel/config/DTB/181 modules, Test382 early vendor/GLINK
geometry, native mapper, stock isolated assets, status69-corrected RPC daemon and
unchanged library/proxy. No wait/proxy repair, registry selector, firmware blob,
charging, USB, input or kernel change. Eight overlay files use Test393 paths;
one extra small Python tool is staged. No new kernel build or images.

Fresh gates: root ADB, noCode43, same enrolled accepted boot journal delta, exact
five partitions/181 modules/config/notes, battery20–100%,10–42°C, VBAT3.4–4.45V,
no new failed unit/kernel panic/Oops/CPU/RCU/CSD signature. Three bounded recovery
samples before transfer. Keep computer USB; no charging experiment or SSH wait.
PPS/pump/DCC OFF. Full journals at boundaries; no per-sample module rehash.

UP means only the registered domain's initial state. Preserve indication states
separately; do not claim SSC publication/sample/rotation from it. Only if SSC400
is actually advertised, issue one bounded accelerometer probe. No sensor PASS
or physical retry in this observation scope. Any first unknown/fault stops.
Always restore exact Test370, owned overlay/assets and normal GNOME; collect
failure evidence and perform cleanup before waiting for a network push.

86 observer/domain host cases qualified in35ec7062;14 new scope/real helper CLI/
canonical captured-identity/overlay tests pass. Reuse unchanged builds and
qualification; no full regression/Actions. Registration must be committed and
pushed to origin/test before device mutation. Retention384–393; the old numbered
early vendor artifact has an explicit current Test393 consumer, no extra copy.
