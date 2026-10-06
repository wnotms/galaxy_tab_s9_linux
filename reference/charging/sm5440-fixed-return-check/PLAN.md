# One-shot OFF-only fixed9V return check

2026-10-06. Retain fixed-return-window policy9901200d. No PPS or pump ON.

Add defaultfalse/read-only boot flag `sm5440_fedora.fixed_return_check=1`.
Mutually exclusive with direct_charge; direct activation also independently
rejects fixed-check mode. Only the existing delayed worker owns operations;
PM/remove drain it as before. Wait read-only for fixed9V for at most300s
from probe, then stop. A 5V PC source or temporarily absent/transitioning
provider may wait; other errors end the one-shot. A new attach is not retried.

Admission uses actual native fixed source/epoch and coherent pack snapshots:
fixed9V1–1.5A,SOC5–<80,VBAT3.5–<4.3V,pack15–<38°C,healthy/normal/present.
After checked pump OFF, require existing ADC channel register0xdf (Fedora
setup, current device measured223); do not change channels or ADC arithmetic.
Acquire the existing switching lease, recheck coherent pack, execute existing
fixed return producer/release. No reset, HW init, PPS request, pump enable,
frequency/IBUS/float/thermal programming. Completion/failure stops scheduling;
log physical proof only after source-bound release succeeds. Keep all existing
bounded cleanup and failure-inhibition semantics, including partial acquire.

Affected actual-C tests and same-config incremental build, config/DT/module
identity and W1/sparse only. Frozen Test331 and fixed-window formal artifacts
remain unchanged. Build a separate default-OFF package; Test332 adds the single
boot-only fixed-check flag and supplies exact Test331 paired rollback.

Test332 purpose: on a fixed9V charger, prove pump-OFF voltage stability and
successful switching release. It is not a PPS transition/pump/current test.
Preflight once with fresh rescue/identity/thermal, then one install and startup;
owner connects C2 18W while WiFi records kernel/pack/OFF/source. Stop at first
fault, proof refusal or missing evidence. Collect complete kernel journal with
source timestamps, one proof and complete event, endpoint ordinary charge.
Restore Test331 OFF boot/pairedmodules after completion or first failure;
keep exact323 backup as secondary rescue. Do not increase current or advance
PPS scope as a consequence of this test. No physical execution before separate
registration/tests and push.
