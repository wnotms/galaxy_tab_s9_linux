# Test290 results — independent passive observation, offline qualified

**PASSIVE_OBSERVATION_OFFLINE_QUALIFIED_DEVICE_NOT_TESTED.** Source8e890215.
Design was written before implementation in `SM5440_PASSIVE_OBSERVATION_API.md`.
Test289 proved that one source-matched OFF-mode sample completed required reads
later than the100ms requester. Its refused/raw verdict remains unchanged.

## Concrete change

`sm5440-direct.c` / `sm5440-hw.h` add kernel-only `sm5440_passive_observe()` and a
distinct diagnostic output: request entry, original oldest acquisition start,
software completion, delivery, actual age, acquisition sequence and PM epoch.
The worker records completion after checked reads, immediately before cache copy;
it is not a physical ADC-ready timestamp or exact publication/wakeup instant.

A separate500ms [BRINGUP_LIMIT] collection budget can return slow passive evidence
with its explicitly old age. It is not an ADC specification, realtime cutoff or
charging admission. Tests simulate140ms completion with135ms oldest age: the
observation reports135ms, rather than relabelling it100ms fresh. No legacy cache/
fresh/API or active policy deadline was increased. Those functions, converter
sequence and quiesce remain byte-for-byte baseline; no restamping/hardware tweak.
Legacy functions deliberately remain separate to preserve verified behavior.

Both request APIs share one reservation/worker and pinned lifetime. No I2C in
request callers or second converter; no core/registry/io lock across wait. PM
stops/advances epoch before drain; unpublish wakes/drains references and retains
its final registry barrier. Old/same-sequence/invalid-time/fault/I2C/stopped/PM/
busy/late-release failure clears the full destination. Timeout neither retries
nor cancels normal monitoring; faults stay latched. No userspace writer, auto-
request, live adapter, PPS Request or pumpON/current path is introduced.

## Qualification performed once

| Check | Actual result |
|---|---|
| New actual-C tests |13PASS; threaded removal, PM epoch, cross-API exclusion, timing/sequence/errors |
| Full host regression |1494PASS,0failure/error/skip; prior1481IDs retained,13added |
| Changed selection |same1494 selected; executed:false, covered by the one full run |
| Shell syntax |PASS for all scripts/lib/boot shell files; wrapper tests not rerun |
| ARM64 build |PASS, pinned7.2-rc3, LLVM/ccache/JOBS8/181paired modules |
| W=1 / sparse |PASS, final driver object hash unchanged by static pass |
| Config / embedded config |byte-exact272 f2891de2; precise config diff empty |
| Compiled DTB |byte-exact272 233a9fee; precise DT diff empty |
| Protected / compiled overlay |96unchanged; all8match source8e890215 |
| Container / DCC |85required y retained; HVC_DCC absent |
| Existing results/artifacts |272/276/283–289 seals and old272 artifacts intact |

Build/config seed warnings and the known upstreamVDSO `__kernel_getrandom`
declaration warning remain in raw logs. No driver warning or unrelated upstream
cleanup is hidden. Schema validation is reused for unchanged byte-identical DTS/
DTB; no new DT schema run is claimed. Final artifacts/hashes and exact module
manifest are in ARTIFACTS.json and validation/module-hashes.json.

The new module file set is181, archive exactly matches.167binary hashes changed;
ELF review finds.BTF changes in167, and build-id/debug-relocation/debug-string
changes in one. Every other compared ELF section, including.text, is unchanged.
This is not permission to mix old modules: use the newly paired archive for this
new kernel. Old272/263 files and rollback remain untouched. No boot bundle or
physical installation is generated/executed by this test.

Initial new host tests had four failures caused by missing release-delay injection,
a nested mock call under an invalid caller lock and an incorrect same-sequence
expected errno (wait cannot complete). Their log is retained; mocks were corrected,
production gates not weakened, and final affected/full runs passed. A first
module-diff summary failed because Counter.update received mapping values; the
corrected section audit used keys and saved the actual complete comparison.
Initial old272 seal verification needed its algorithm/files wrapper normalized;
format-aware verification then passed, with no old-record drift.

## Frozen behavior / remaining boundary

SM5714 battery/TCPC, fixed5V<=1.8A/9V<=1.5A,4440mV, pack thermistor/failclosed
thermal/suspend, source capabilities/TCPM, USB/DWC3/gadget/adbd/NCM/SSH,
CPU/GPU/DT/config and Docker/UPower unchanged. ADC averaging/channel/register
writes,12x25ms requests,1s cadence, protection recipe and OFF-only behavior unchanged.
Test290 sent zero device commands. Last device verification is restoredTest263
bootd856e6f593254cc28f3a178579e07c1b/Wi-Fi10.125.29.32 from289, not a new endpoint.

Next prepare a separate owned-lifetime diagnostic consumer; old276 calls the
legacy100ms API and is not a replacement. Then independently register one passive
call with essential rescue/identity/battery gates and exact263rollback; avoid
repeated identical traces, builds or full regression for results-only commits.
`FUTURE_PHYSICAL_PLAN.md` defines that limited scope; not executed here.

This enables useful passive acquisition evidence, not accepted active sampling.
Independent voltage/nonzero-current calibration, real protection/OCP latency,
live supplier/PM/handoff, PPS and pump acceptance remain open. The original100ms
active refusal rule is not solved or waived by this500ms diagnostic contract.
**ActiveStage3 NOT READY; full wired-charging port goal remains active.**
