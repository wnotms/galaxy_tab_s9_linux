# Fresh-request timing audit — Test278 offline

[MEASURED] Test275 returned provider/consumer -110 in 108ms, followed by unload
transport loss. Test277 returned -110 in 101ms; the corrected observer unloaded
normally and the same boot's ADB/Wi-Fi/device NCM remained healthy. Neither is a
successful acquisition. Current device is restored Test263; this audit executes
zero device commands and leaves every kernel/config/DT/ADC/charging input intact.
Raw attempts remain immutable; derived facts and tests are in
`reference/boot-tests/test-278-fresh-timing-audit-offline/`.

## Source identities and timeout branches

[MAINLINE] Source pin `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`; timer/workqueue
files were compared with that tree's HEAD. Frozen provider C/header are byte
identical to Test272 `399eb497`. INPUTS.json binds individual inputs, qualified
config/notes and original evidence to SHA-256; the analyser refuses a mismatch.
Observer remains Test276 `7a887eab`, no new diagnostic code is installed.

Four places in `sm5440_passive_request_fresh()` return -ETIMEDOUT:

| Branch | Condition | What existing records establish |
| --- | --- | --- |
| Initial budget | Registry/setup already consumed at least100ms, or clock reversed | No entry/queue timestamps; UNKNOWN |
| Wait expiry | No condition completion within remaining jiffy timeout | No wake/worker timestamps; UNKNOWN |
| After wake | Total budget exceeded100ms, or clock reversed | No wake/copy timestamps; UNKNOWN |
| Final release | Valid copy subsequently became late during final user release | No release timestamps; UNKNOWN |

The observer adds its own total-delivery check, but both recorded provider returns
are already -110. This is not merely the observer rejecting a successful provider
return. Failed output is deliberately zeroed: zero VBUS/temperature/acquisition
fields are not physical ADC readings. Worker I2C/ADC failures latch fault and are
separate from the requester's delivery refusal; -110 alone cannot prove one.
Test277's later valid OFF-mode cache is evidence of subsequent monitor progress,
not proof of which request branch executed or which conversion it represents.

## Three timing concepts must remain separate

[BRINGUP_LIMIT] Request entry-to-return and oldest acquisition age both must be
within100ms for a successful API result. This is a software validity rule, not an
ADC specification, a hardware OCP deadline or a guarantee of thread scheduling.

[MAINLINE] The ordinary converter worker retains average32/channel0xdf, up to
12 `msleep(25)` polls, followed by data/status/protection reads and publication.
Its nominal requested sleep sum is300ms, and its default next monitor delay is1s.
Those are requested sleeps, not an upper wall-time promise: queueing, mutexes,
I2C, timer slack and scheduling also consume time. No operation was shortened.

[MAINLINE] Actual resolved config has HZ250. Pinned `msleep()` uses
`msecs_to_jiffies(25)`, rounded to7ticks, nominal28ms. Four such nominal timeouts
sum112ms; even four ideal25ms requested sleeps leave no headroom inside100ms.
This establishes a budget risk, not that this boot performed four polls or that
conversion lasted112ms. No assumed plus-one tick is added: the pinned source
uses `msecs_to_jiffies(msecs)` directly. Timer-wheel slack and CPU wake latency
are additional considerations. [Linux sleep documentation](https://docs.kernel.org/timers/delay_sleep_functions.html)
describes the timer granularity; this exact source/config governs the calculation.

The debugfs snapshot's `sample_fresh=1` has a different2.5s publication-age window.
It does not satisfy the API's100ms acquisition-age or delivery rules. Changing
its label or using a cached sample cannot make a refused fresh call valid.

## What cached timestamps can establish

[MEASURED] The Test277 sample-to-endpoint publication stamp advances92ticks =368ms
in the same unsigned64-bit jiffies clock. The paired ages are340ms then468ms.
This is an interval between two cached publication stamps, not a368ms converter
duration: conversions/requests are not identified by the old snapshot format.
Before-load to first-sample intervals are12.672s in275 and12.716s in277, containing
other normal polling and host preparation; they are not queue delay measurements.

Jiffies publication, /proc/uptime and observer BOOTTIME are not captured together.
INITIAL_JIFFIES or host UTC command duration is not a measured clock anchor;
suspend/clock phase and packet serialization must not be ignored. The analyser
therefore emits null for absolute publication BOOTTIME and all unobserved phase
durations. Test275 stamps exceeding2^32 remain valid unsigned64-bit ARM64 values.
No false0-duration, restamping, guessed alignment or inferred timing pass occurs.

## Same-model reference does not justify changing converter policy

[VENDOR] X710 `sm5440_init_reg_param()` selects average32 and channel0xdf.
`sm5440_set_adc_mode(ONESHOT)` disables ADC, sleeps20ms, selects rate0, schedules
adc_work for200ms and enables ADC. That worker re-enables ADC and reschedules
itself every200ms. Continuous mode disables/sleeps50ms/sets rate1/enables.
These20/50/200ms numbers describe vendor software sequences, not a measured
maximum OFF-mode conversion time. Vendor `convert_adc()` also gates ordinary
reads on direct-charge state; its ADC fields are not a100ms passive guarantee.

[FEDORA] Audited local snapshot remains `ab123e7d`. Its active `hw_init()` writes
AVG32|CONTINUOUS|ENABLE, reads ADC pairs directly and includes an active charging
initialization recipe. It is not the current OFF-mode one-shot transaction.
Copying its continuous setting or full init to obtain a faster read would change
a tested hardware variable and may import active/protection behavior. Not done.
Vendor and Fedora sources are read-only and independently hashed in INPUTS.json.

## Minimal future attribution, without rebuilding the kernel

The sealed config already includes KPROBES/KRETPROBES/KPROBE_EVENTS/DYNAMIC_EVENTS,
TRACEPOINTS and tracing. FUNCTION_TRACER is off: a function-graph recipe cannot be
assumed usable. Offline ELF inspection shows `sm5440_passive_request_fresh` and
`sm5440_poll`, and workqueue queue/start/end tracepoints. `sm5440_sample_once`
has no standalone emitted symbol in this build, so a direct probe on that source
function cannot be assumed to exist.

ELF notes match the sealed272notes. Nevertheless the ELF fresh symbol address
and captured running kallsyms address differ; do not use ELF absolute addresses
or guess instruction offsets, even with nokaslr in the command line. Runtime
symbol lookup and exact current identity must govern any future probe/filter.
No claim about the reason for this address difference is needed for the guard.

Future independently registered passive test, after offline collector tests:

1. Deploy only already-qualified272paired kernel and276observer, preserve exact263
   rollback. Confirm Sink/Device/SDP500, OFF/fault0/battery/rescue and identity.
2. Inspect actual tracefs events/clock/symbol availability once. Missing support
   stops preparation; do not enable kernel configs, reboot repeatedly or guess.
3. Use a private small trace instance, boot clock if supported, and symbolic
   request/poll entry/return probes plus filtered workqueue queue/start/end.
   Avoid global regmap probes, function graph, fault injection and new I2C reads.
   Save existing tracing state; enable only owned events and clean up only those.
4. One276observer load/one call before first-refusal stop. Collect its cached row,
   bounded trace tail and ordinary snapshot; no reload/request retry. Unload and
   verify sameboot endpoint, then restore263 under the registered policy.
5. Parse PID/work-pointer pairings, clock domain, ordering, truncation/lost events
   and probe misses. Incomplete/overflowed evidence means UNKNOWN, not a pass.
   Report queue delay and aggregate worker time only when uniquely paired.

These boundaries can narrow queue versus aggregate worker/delivery costs, but
cannot directly separate inlined ADC-ready wait from I2C/state-copy work. If that
remaining distinction matters, separately design minimal paired timestamps;
do not call the entire worker duration an ADC measurement. Tracing adds overhead,
so its outcome is diagnostic attribution, not uninstrumented timing acceptance.
A future physical registration/collector and any tracefs writes are NOT executed
in278. No change to100ms, average/channel/polling, source role, PPS, pumpON,
current ceilings,4440mV, thermal or USB/rootfs policy is proposed by this audit.
ActiveStage3 NOT READY until the remaining independent acceptance gates pass.
