# Test287 results — passive refusal traced, device scope completed

**PASSIVE_REFUSAL_CAPTURED; EXACT263_ROLLBACK_READBACK_DEVICE_ENDPOINT_COMPLETED.**
One registered candidate boot and one owned276observer load. Test285's nonseeking
adapter successfully defined all four symbolic probes, captured and removed them;
Test284's old EINVAL STOP remains unchanged. No alternative offset/symbol/retry.

| Captured boundary (boot clock) | seconds |
|---|---:|
| fresh request entry | 100.910559 |
| worker queue | 100.910565 |
| worker execute start | 100.910576 |
| poll entry | 100.910578 |
| request return, -110 | 101.012069 |
| poll return | 101.044962 |
| worker execute end | 101.044969 |

Request elapsed101.510ms; queue-to-worker start11us; worker elapsed134.393ms,
ending32.900ms after the request returned. One request, zero usable deliveries,
first refusal STOP. Seven raw events, all four probes1hit/0miss, complete paired
queue/request/worker boundaries and no detected trace loss. Observer/trace boot
and count binding passed. Collection0.121696s + fixed500ms tail;
including owned cleanup/unload1.055814s. Device endpoint qualification is separate
from the coordinator's trace-only summary and is saved in `endpoint-summary.json`.

These are **traced aggregate wall times**, not ADC conversion latency. Queue
delay was small for this one work item; time was spent inside the worker's
aggregate execution, which includes I2C, polling sleeps and scheduling. Exact
timeout branch, ADC-ready timing, per-I2C timing and causal worker assignment
remain UNKNOWN. Tracing adds overhead; no uninstrumented timing acceptance,
sample freshness, high-power or charging grant follows.

Same candidate boot `2fe71db013594aba9153d2229a39f00d`: full journal/identity/
healthy passiveOFF/protection and battery/ADB/authenticatedWiFi/deviceNCM passed,
no new detected CPU signature/failed unit/Code43. Owned probes/instance and
observer/debugfs absent after cleanup/unload. Raw endpoint journal retained;
bounded display startup triplets remain unresolved, not called stability-clean.

Unconditional rollback completed: all five partitions and181original module
files exact263 readback; candidate modules under `.gts9-test287-tested`, all
older backups retained, BCBclear/rootunmounted. Recovery dmesg and pstore/lastkmsg
availability recorded at each recovery boundary, without claiming absent
sources were collected. One final normal263 boot
`51d701890b84482d9d42b5b7db3508ad`, Wi-Fi`10.125.29.58`, exactnotes/config/normalcmdline,
full journal/currenthealth/rescue/uniquehistory passed. Battery66%,4.020V,31.0C,
Good; passiveOFF/fault0/IBUS0. Observer/freshAPI and DCC absent. Device-side NCM
acceptance; no additional WindowsTCP retry series. This completes the registered
device scope; it does not repair the fresh-request refusal.

Workflow: batched portable push, grouped maintenance/readback, parallel independent
boundary reads, nativeTWRP readiness, no per-command pauses or module/full-journal
rehash per sample. Recorded physical-command endpoint span416.32s (~6m56s),
summed command durations58.93s; span includes boots/orchestration/pushes and is
not a controlled benchmark or proof all remaining time is removable. No repeated
kernel build/full suite: unchanged272/276/279/280/283/285/286 qualification reused.
19 new portable wrapper tests/syntax/staging passed before registration; results
only changes have tests executed:false, not a full regression pass. No CI.

Kernel/config/DTS/181module artifacts, ADC sequence/deadline, USB/adbd/rootfs,
fixed5V<=1.8A/9V<=1.5A,4440mV and thermal/suspend safety unchanged. No PPS request,
pumpON, charging-current escalation or protection-limit testing.

Next **offline**: analyze the captured worker aggregate and pinned polling/I2C
source. If finer phase evidence is required, first qualify a separate private
I2C trace parser/profile using existing tracepoints; do not repeat the same
aggregate acquisition or infer12/four ADC polls from134ms alone. Any future
physical observation needs independent registration. Do not change the ADC
sequence or100ms guard simply to make this refusal pass. ActiveStage3 NOT READY.
