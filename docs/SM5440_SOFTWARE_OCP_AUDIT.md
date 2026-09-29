# X710 software OCP and transaction evidence admission

Test257 continues offline work from a3ddd0de. This design precedes code.
No device access, PPS request, pump activation or configuration/DT change.
Test255 fixed5V1800/9V1500mA, float4440mV and Stage1 thermal remain frozen.
The live transport still denies PPS; no live transaction adapter is supplied.

## Source findings

Primary sources are the hashed Samsung X710 files under
`msm-kernel/drivers/battery/charger/sm5440_charger/`, cross-checked with Fedora
ab123e7d. Test256 sources.json preserves identities. No vendor source is edited.

| Finding | Source / behavior | Port decision |
| --- | --- | --- |
| Hardware OCP unsupported | sm5440_charger.c:1761 need_to_sw_ocp=1; init:454 CNTL2=0xF2 disables IBUSOCP/IBATOCP/THEM | no active init / ON API |
| Software OCP trigger | pd_pre_cc_work/pd_cc_work: LOOP_IBUSLIM invokes check_sw_ocp; pre-CC additionally checks prior voltage-down | hardware regulation flags alone are not a complete current limit |
| Delayed OCP check | sm5440_check_sw_ocp:1223 schedules1s later; ocp_check_work:1254 checks STATUS2.IBUSLIM and STATUS3.THEMSHDN_ALM three times with1s sleeps | not a proven mainline response bound; no port of delayed status-only loop |
| OCP I2C errors | those two status read return values are unchecked; local reg1/reg2 are not initialized | never interpret failed reads as healthy status |
| Error reporting | after three positive checks report SM_DC_ERR_IBUSOCP; vendor manager owns stopping | port requires verified OFF, not a notification alone |
| ADC aggregator | get_adc_values returns0 even when channel getter returns negative; SM_DC_ADC_IBAT getter returns0 | fail closed on every transfer; do not invent pump IBAT |
| Poll/refresh timing | DELAY_ADC_UPDATE1100ms / CHG_LOOP2500ms; Fedora poll/refresh/watchdog | these are policy cadence, not accepted OCP latency |

Vendor CC checks measured IBUS against ci_gl and adjusts PPS separately from
the delayed flag check. It does not establish that a software worker can replace
hardware current protection during I2C hangs, CPU stalls or scheduler delays.
The watchdog/analog protection recipe and physical cutoff latency remain blockers.
No claim that host tests qualify software_ocp_verified is permitted.

## Missing offline gates found in Test256 core

1. `apdo=true` was not enough to prove the target fits the latest source offer.
2. `valid=true` did not prove facts/ADC belonged to a recent monotonic timestamp.
3. Facts were not rechecked against epoch after the callback returned.
4. No active-state monitoring entry point checked deadline/overcurrent outside
   a PPS refresh. Data cached for minutes could appear valid.
5. Milliamps discarded the SM5440 ADC's625uA resolution at a strict1800mA cap.
6. Stop/detach could retain an authorization flag; stop must always revoke it.

## Proposed minimal changes

Extend the existing facts/sample/ops structures, not a new framework. Source
offer min/max/current is mandatory in a fresh facts snapshot. Revalidate target
before PPS and before pumpON/refresh; do not rely on earlier target calculation.
Epoch includes source-capability/reset generation as well as attach lifetime.
Adapter operations must themselves check their expected generation under their
hardware serialization lock; core pre/post checks cannot remove an I/O race.

Use a mandatory monotonic `now_ms` callback and nonzero observation timestamps.
Zero, future or backward time is invalid. Initial logical freshness budgets:
facts<=500ms, ADC<=100ms; active monitor call gap/ON observation<=100ms.
These are **[BRINGUP_LIMIT] refusal rules**, not vendor production constants or
a measured protection latency. Adapter must use the oldest required acquisition
timestamp in a facts bundle, and the actual completion timestamp for fresh ADC,
not stamp cached data with the time it was fetched from cache. No auto-refresh
worker/timer or polling-frequency deployment is added.
Source capabilities remain valid by generation until invalidated; this is not a
requirement for new Source_Capabilities messages every500ms. Physical telemetry
must have genuine acquisition times. Immediately before ON, facts are checked
again with100ms observation slack (age<=400ms) so a scheduling pause cannot
reuse the previous grant or let it expire within an accepted post-ON window.

Keep actual IBUS in microamps through the physical sample; compare against
target_ma*1000. Thus1800001uA is rejected at1800mA, and no integer-mA truncation
can hide an over-cap sample. No new pump IBAT inference. A future adapter still
needs independently valid gauge current and approved protection latency.

Add a default-unwired monitor operation to the existing core. A healthy sample
does not change PPS or pump mode. Fault, stale evidence, lost source, overcurrent,
deadline miss or PM cancellation invokes the same verified OFF/fixed fallback;
failed OFF prevents voltage change. Any stop revokes authorization. Pump-OFF
PPS refresh may take longer, but a new monitoring deadline starts only after
fresh post-ON evidence; no deadline is silently reset while pump is active.

## Verification and boundary

Compile the real C core with deterministic mock clock/adapter. Retain all1239
existing test IDs and assertions, extend fixtures for mandatory evidence, add
source contraction/withdrawal, stale/future timestamps, clock regression,
sub-mA overcurrent, missed/overrun monitor, epoch changes inside reads, and
stop/rearm fault tests. Builds use the same explicit offline profile and default
fixed profile; expected config/DT deltas are unchanged from Test256.

Software decision tests are NOT physical OCP tests. No live TCPM power_supply
consumer/device links/worker/PM adapter or active protection configuration is
introduced. Active PPS/direct remains NOT READY; passive ADC/calibration and
software/hardware protection acceptance still precede any such integration.
