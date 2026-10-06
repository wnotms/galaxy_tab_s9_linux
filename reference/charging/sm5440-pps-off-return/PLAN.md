# Pump-OFF PPS roundtrip candidate — preparation, no device activation

Test334 directly proved stable fixed9 OFF return; Test335 completed ordinary
fixed9 switching/unplug. Neither proves a PPS-to-fixed voltage transition.
Test330's phase-incompatible source coherence was corrected in Test331; its
fixed proof was corrected/qualified separately. Requested8.72V versus ADC9.268V
remains unresolved, not independently calibrated. Do not start the pump to
investigate that discrepancy or increase current.

Prepare one independent readonly boot opt-in `pps_return_check`, defaultfalse,
mutually exclusive with direct_charge and fixed_return_check. One existing
ordered worker, existing PM/remove drain, one300s fixed9 admission deadline;
no transaction retries after first outcome. Existing pack/source/lease/API
semantics own all operations. Default-OFF and historical fixed-check behavior
remain unchanged.

Sequence after a separately authorized Test336 installation/charger boot:

1. Wait read-only for fixed9 sink source and healthy pack; require SOC20–<80,
   VBAT3.5–<4.3V, pack20–<38°C, no fault/detach/suspend and original limits.
2. Verify physical pump OFF and existing ADCCNTL2=df. Acquire existing battery
   switching lease, recheck pack/source. Enable only already qualified Fedora
   continuous/averaged ADC; no reset, hw_init, frequency/current/protection
   programming or CHG_ON. No new register magic value.
3. Use existing TCPM owned request and unchanged target formula/current1.8A,
   clamp8.2–10.5V. During this one request use no automatic -EAGAIN retry loop.
   Read source/pack/physicalOFF/VBUS/rawIBUS repeatedly: active owned PPS,
   target budget exact, existing ±500mV envelope, ≥3 readings over≥100ms with
   entire range≤100mV and rawIBUSzero. Bounds/sensor/I2C/source/PM/identity errors
   fail immediately; voltage not settled fails within≤1.5s. Source-owned receipt
   is protocol evidence, ADC is uncalibrated physical telemetry, neither an
   independently calibrated VBUS guarantee.
4. Always run existing terminal pumpOFF→fixed9→physical fixed proof→release.
   Preserve primary and cleanup errors separately; emit success only after
   verified return/released lease. Worker completes once on success or failure;
   never start direct charging afterward. Unknown return keeps switching
   inhibited and triggers unplug/recovery in the later physical runner.

No TCPM/DWC3/USB/adbd/battery/config/DT changes; fixed5≤1.8A/fixed9≤1.5A,
4.44V/thermal/DCCn/container baseline unchanged. Ref source: same-model Fedora
ab123e7d ADC/settle, Samsung X710 register audit already recorded; use current
mainline TCPM APIs and lease rather than Fedora unowned power_supply writes.

Host-only fix: future ordinary-charge observation has WAIT→SETTLING→OBSERVE;
allow≤10s between first fixed9 and healthy Charging/current>0, based on the1s
battery poll and a bounded bring-up allowance (not a proven hardware latency).
All safety/OFF/identity/source/journal gates stay immediate. After OBSERVE any
loss stops; no resetting the settling deadline to hide a failure. Preserve335
sources and STOP, replay real negative-current sample in host tests. Do not run
another physical fixed9 cycle merely to qualify this parser.

Affected actual C lease/TCPC/PM/cleanup/fault tests plus helper tests, one cached
ARM64 Image/DT/modules build, changed-driver W=1+sparse, config/DT/module/protected
audit and offline boot packaging. No full regression/routing change or Actions.
Frozen331/334 formal inputs stay protected; use the same profile build cache
and a new artifact output namespace. This preparation performs no device writes,
flash/reboot/modules/rootfs or PPS/ON. Stop after candidate qualification;
Test336 physical scope needs its own registration and explicit PPS-OFF execution
authorization, not automatic escalation from335 or another high-power attempt.
