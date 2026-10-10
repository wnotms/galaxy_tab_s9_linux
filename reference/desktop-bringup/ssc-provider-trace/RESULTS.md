# Native SMP2P/GLINK observer qualified offline

An independent `userspace/sensors/smp2p_trace.py` now observes the six existing
GLINK events and four native SMP2P events in a boot-owned `gts9_ssc_provider`
instance. Historical381/382 collectors are unchanged. It reuses the exact382
geometry, identity, deadline, read-only inventory and collection primitives;
no kernel/DT/module, remoteproc, SMEM, firmware or hardware code is added.

39 affected host tests PASS, zero skips:24 new parser/real collector cases and
15 historical382 cases. Syntax checks pass. The actual398 trace is admitted
as complete17-event evidence with no SMP2P observation, explicitly **not** a
negotiation-failure or SSC restoration verdict. Added native event examples
are labelled host fixtures, not newly captured hardware evidence.

The parser preserves boot ID and original local timestamps, validates all
eight raw per-CPU loss/entry/read counters against derived statistics, checks
raw byte length/hash and trace header/record counts, and rejects unknown rows,
event formats, out-of-range fields, per-CPU clock reversal and events after
collection. CDSP/modem events cannot be attributed to ADSP. SSR acknowledgments
are recorded, not automatically labelled a CPU fault or sensor acceptance.
It does not invent inventory of remote entries missing from the DT.

The actual collector mock changes exactly one file: this owned instance's
`tracing_on` to0. Malformed evidence retains the raw trace/counters and fails
closed. Identity, event-set/filter/format drift and stale boots fail before a
write. Four SMP2P format hashes come from the actual accepted-kernel read-only
capability report, excluding only their dynamic numeric event ID. In particular,
the pinned kernel prints **empty** `out_features=` for zero flags; this is
tested from its `trace_print_flags_seq` implementation rather than guessed.

## Capture scope adjustment before registration

The earlier source-only design proposed an ADSP device filter. The qualified
boot `trace_instance=` facility selects event names; this observer instead
captures only these ten named events **without a filter**, retains other
processors' bounded records and attributes ADSP by its verified platform name
`smp2p-adsp`. No bootconfig mechanism or late filter is guessed, and no early
events are erased to install a filter. A live filter other than `none` is
rejected. This captures no payload/protocol data and writes no shared memory.

The128KiB request uses the already measured131KiB per-CPU reported geometry;
raw trace is capped at1MiB, complete JSON at2MiB, parser at4096 records and
trace deadline at300s uptime. The local clock permits per-CPU ordering checks only,
not cross-CPU causality claims. A missing negotiate event is an observation
within the window, not proof of an unsuccessful negotiation or firmware error.

Next register one separate early-ADSP text boot with the exact398 initialized
readdir daemon/library, original assets, two qualified PDR snapshots and30s
startup observation. Only the vendor trace command line and owned userspace
observer overlay need change; full normal370/GNOME return remains mandatory.
This component qualification is **not** a registration or hardware PASS.

No rebuild/full regression/routing change/Actions; no device trace enable,
flash, reboot, RPC or DSP start. The current desktop baseline remains intact.
PPS/pump/DCC OFF; SSC400, actual samples and automatic rotation unaccepted.
`QUALIFICATION.json` and `SHA256.json` bind exact source and evidence inputs.
