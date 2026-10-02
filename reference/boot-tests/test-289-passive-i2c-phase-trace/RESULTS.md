# Test289 results — I2C phases captured, baseline restored

**PASSIVE_REFUSAL_CAPTURED; exact263 rollback and registered device scope completed.**
One candidate boot `7a4d9ce5e4a64b5a82081c54ddcfce3f`, one corrected276 observer
load, one fresh request, provider/consumer -110 and zero usable samples. First
refusal stopped acquisition; no retry, PPS, pumpON or charging-current change.
Registration25f597f5 was pushed before mutation; c40f0458 records paired deployment.

| Boundary, boot clock | seconds |
|---|---:|
| request entry | 31.116294 |
| worker queue / start | 31.116300 / 31.116308 |
| poll entry | 31.116310 |
| ADC enable write call / result | 31.117897 / 31.118005 |
| first completion poll result, 0 | 31.149541 |
| second completion poll result, 0 | 31.181813 |
| third completion poll result, 0 | 31.213684 |
| request return, -110 | 31.220031 |
| fourth completion poll reply / result, 1 | 31.245313 / 31.245316 |
| ADC eleven-byte read call / result | 31.245321 / 31.246833 |
| final protection read result | 31.256233 |
| poll return / worker end | 31.256249 / 31.256253 |

The separate post-disable latch read preceded enable and returned0; it is not
a fifth completion poll. Eighteen source-matched address0x63 worker transactions
succeeded, with no unassigned I2C records. All raw trace, event formats, filters,
per-CPU counters, probe profile, timestamps and bytes remain under
`observation/device-capture/observation/trace/`; derived complete phases are in
the captured summary. Pairing, trace completeness and observer binding passed.

[MEASURED] Request103.737ms, queue8us, worker139.945ms. Transaction wall sum17.483ms
and between-transaction wall sum122.436ms include scheduling/trace overhead;
the latter is not a sleep-only measurement. Enable-call to first-ready-reply
wall envelope127.416ms; ready reply arrived25.282ms after request return.
Raw ADC bytes: `19 a0 79 00 00 00 66 f8 04 75 00`. OFF readback01/01,
IBUS0 and protection f2/e7/37/fe remained. These are passive facts, not calibrated
voltage/current or accepted active protection.

This narrows the refusal: queueing was small, and required ADC/status/protection
collection completed after this requester returned. Enqueue excludes the initial
budget branch. Wait expiry is consistent with source order, but publication/
wakeup/other state transitions were not independently probed; the sealed parser
still reports exact timeout branch and causal worker assignment UNKNOWN. The
physical register-sampling instant lies within a transfer and the ready flag is
polled, so exact ADC conversion duration remains null. No uninstrumented timing,
100ms success, freshness or charging grant follows from successful trace parsing.

## ADC averaging source check

The enable value was0x0d. [VENDOR] `sm5440_init_reg_param()` at line460 sets value1
with **mask0x1, shift3**, explicitly documented as average32. [FEDORA] the audited
same-model `SM5440_ADCCNTL1_AVG_32` is BIT(3); current `SM5440_ADC_AVG32` is also
BIT(3). Source identities are in `average-field-sources.json`. These sources do
not establish a two-bit averaging field or the meaning of retained bit2.
Do not infer average64, invent GENMASK(3,2), or clear bit2 to obtain a faster
sample. No converter mode/channel/averaging/poll/deadline change was made.

## Device completion and exact rollback

Collection0.145707s, fixed500ms tail, total owned cleanup/unload
1.072123s. Same candidate boot remained responsive with
ADB/authenticatedWi-Fi/deviceNCM, healthy passiveOFF/fault0/protection, no detected
new CPU signature/failed unit/Code43. Owned trace instance/probes/observer absent.
Coordinator's trace-only `device_endpoint_qualified:false` is not the separate
endpoint verdict; `observation/endpoint-summary.json` records completion.
Startup display diagnostics remain unresolved and are not called stability-clean.

Unconditional exact263 rollback: all five partition hashes and181original module
files verified, candidate retained at `.gts9-test289-tested`, older backups retained,
BCBclear/rootunmounted. Both recovery boundaries retain ancillary source availability.
Final normal263 boot `d856e6f593254cc28f3a178579e07c1b`, Wi-Fi`10.125.29.32`, exact embedded
config f2891de2 and notes fea0613f/normalcmdline/fulljournal/uniquehistory/rescue passed.
Battery64%,4.000V,31.1C,Good; passiveOFF/fault0/IBUS0. PCSDP500mA; battery current
-465mA is saved as observed, not relabelled from the charging-path status.
Observer/freshAPI and DCC absent. Device-side NCM accepted; no additional hostTCP
retry series. This completes this registered device test, not active Stage3.

## Faster workflow and next step

Grouped stages/batched transfer/parallel independent reads/native recovery readiness
were used, with no per-command manual pause. Physical command records span
317.45s, their durations sum54.45s (106 commands); this includes boots,
readiness/orchestration/push time and is not a controlled benchmark. Exact unchanged
kernel/observer build and1481/full/W1/sparse qualification reused;28836 phase and
28920 wrapper tests passed before deployment. Results-only tests/build/full
**executed:false**, not a new regression pass. No GitHub Actions.

Next work is source-backed API/ADC design using this complete trace, rather than
another identical refusal round. Separate acquisition start/ready/publication
from delivery latency and application freshness; retain the current100ms API and
all fixed/thermal/USB behavior until an independently reviewed design exists.
Do not merely extend its deadline or change average/channel to manufacture a pass.
Calibration/nonzero-current/OCP/PM/PPS and pump acceptance remain unqualified;
**ActiveStage3 NOT READY**. No automatic further acquisition is registered here.
