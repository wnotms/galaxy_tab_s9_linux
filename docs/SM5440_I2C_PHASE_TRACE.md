# SM5440 passive I2C phase observation

Test287 captured request101.510ms, queue11us and aggregate worker134.393ms.
Those boundaries eliminate a large queue delay for that one item but do not
identify ADC-ready/publication times. The worker can publish/wake before its
`power_supply_changed()` and final return: its late return alone does not prove
the wait-expiry branch. Initial-budget refusal would return before enqueue;
the captured request-thread queue excludes that branch for this call. The
other three -110 branches remain unresolved. Never infer poll count from134ms.

Test288 qualifies a separately named private trace profile and parser, reusing
the frozen279 ownership/loss guards and280 first-refusal coordinator semantics.
No hardware, register sequence, kernel config,100ms guard or charging policy
changes. It is offline-only until a separate physical test is registered.

## Source-defined observation

[MAINLINE] Pinned Linux7.2-rc3 `include/trace/events/i2c.h` supplies write/read/
reply/result events. `drivers/i2c/i2c-core-base.c::__i2c_transfer()` emits messages
before master_xfer, read replies for completed messages, then a result. These
timestamps include core/tracing/scheduling/transfer costs, not on-wire timing.
`regmap-i2c.c` encodes this driver's8-bit register read as pointer write + read;
ordinary writes are register+value. Negative/short results are retained as
transfer failures, not fabricated ADC data or a reason to retry.

[MEASURED] Qualified device name/debugfs is `0-0063`. The new profile enables
only bus0 events in its exclusive256KiB-perCPU instance, with boot clock and
overwrite0. Result events have **no slave address**, so all four events filter
`adapter_nr == 0`; address-only filtering would create orphan results. Raw
background traffic is retained/count-checked, never assigned to the ADC phase.
Only address0x63 transfers with the matched worker's PID wholly inside its
poll-entry/return interval are decoded. Unknown format/filter/order/pairing,
missing reply/result, hash/loss/miss or incomplete worker => UNKNOWN/STOP.

The decoder follows the frozen sample_once recipe:

1. CNTL5 OFF check and INT1..4 read.
2. ADCCNTL1 disable/rate-clear RMW, optional write if already disabled; post-
   disable INT4 read. Preserve its literal value.
3. ADCCNTL2 channel0xdf; ADCCNTL1 average32+one-shot enable RMW. Require an
   observed new enable edge; never substitute an older conversion.
4. One to12 INT4 poll transactions ending at the first ADC_UPDATED observation.
5.11ADC bytes,4status bytes, CNTL5 OFF and four unchanged protection registers.

All actual bytes/transaction envelopes are retained. The report exposes observed
poll count/values, enable-to-ready reply **wall envelope**, ADC read bytes,
transaction wall sum and inter-transaction gaps. It deliberately leaves
`adc_duration_ns=null`: the exact register-sampling instant within a transfer
and the physical conversion interval are not captured. Inter-transfer gaps may
include polling sleeps, locks, scheduling and overhead. No exact ADC speed,
uninstrumented timing acceptance, calibrated voltage or charging grant follows.
Fault/status bytes remain evidence; matching a sequence does not mean healthy.

## Safety and integration

No i2cget/i2cset/new MMIO/register read, IRQ consumption, regmap probe or instruction
offset. The already-qualified observer makes the only fresh API calls. No PPS,
pumpON/current increase, ADC mode/channel/average/poll or delivery-budget change.
Same one-load/max30s/8calls/1s interval/first-refusal/fixed500ms-tail and owned
cleanup/unload apply. Additional events are disabled before buffer/counter capture
and instance removal; unrelated probes/global trace state remain untouched.
The independent coordinator's function ASTs match frozen280, with only imports
selecting the phase Session/analyser. Full paired identity/health/rescue/journal,
normal cmdline, endpoint and exact263 rollback remain physical wrapper duties.

Qualification:36 offline source-recipe/adversarial/ownership/integration tests,
syntax and protected-input/old-seal audit. No device command/build/full suite/
routing/CI in Test288. Unchanged kernel/provider/observer qualification reused.
Test287 is not reinterpreted as containing I2C data: the new parser correctly
returns UNKNOWN for its missing phase evidence. ActiveStage3 remains NOT READY.
