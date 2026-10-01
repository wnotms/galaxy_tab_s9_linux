# Test278 — offline timing audit completed; attribution unresolved

Registrationf6327094 preceded analyser implementation. Zero device commands,
physical attempts/builds/probes/tracefs writes. Last verified device remains
restored263 from277; this task did not reflash/reboot/read or modify it. No kernel,
config/DTS/DTB/USB/ADC/charging/rootfs input change, no100ms relaxation/PPS/pumpON.

Frozen272provider and pinned7.2-rc3 source audited. SHA-bound parser reproduces
original275108ms and277101ms provider/consumer-110 rows, cleared outputs not
measurements. All four actual API timeout checks remain possible: initial budget,
wait expiry, post-wake budget, final release. No phase timestamps exist, so the
report deliberately retains UNKNOWN/null instead of selecting a root cause.
275STOP/unknown freeze causation and277safe-unload-after-refusal remain distinct.

ResolvedHZ250:25ms rounds to7ticks/28ms nominal timeout; four nominal timeouts
sum112ms. Twelve requested25ms sleeps sum300ms, plus other costs. These are
budget calculations, not wall-time or physical ADC measurements; no assumption
about the actual poll count/readiness is made. Diagnostic2.5s publication freshness
is distinct from API100ms acquisition/delivery validity.277cached publication
advances92ticks/368ms between sample and endpoint; this is NOT conversion duration.
Unsigned64-bit jiffies are not relabelled absolute BOOTTIME without a paired anchor.

VendorX710 uses AVG32/channeldf and a recurring200ms ADC-enable work sequence for
one-shot mode. Fedoraab123e7d active init selects continuous AVG32. Neither proves
our OFF-mode conversion finishes100ms, and neither sequence is copied to force
an acceptance. Source paths/hashes and detailed reasoning in INPUTS/audit doc.

16host tests PASS: exact data, distinct error/unload outcomes, jiffy conversion,
64bit/wrap/clock/identity/age mismatches, output clearing, unknown phases, no
false charge grant and changed inputs/policy rejection. Syntax pass; derived
report reproduced byte-identical. Original275/277 final seals verified. No
existing tests removed/weakened/skipped; no suite-routing change. Full host/build
executed:false, reuse unchanged272provider and2761481/W1/sparse qualification.

Offline ELF notes equal sealed272; request/poll symbols/workqueue tracepoints
exist, standalone sample_once symbol absent. Captured running fresh address differs
from ELF address (0x1d8000); absolute ELF addresses are NOT authorized for probes.
Use runtime symbolic resolution if a future test is independently registered.
FUNCTION_TRACER is off but KPROBE_EVENTS/TRACEPOINTS are already enabled. A minimal
future request/worker/workqueue attribution can reuse the current compiled kernel;
its aggregate worker timing cannot isolate inlined ADC-ready versus I2C costs.
No new collector/physical registration/probe is implemented or executed here.

See docs/SM5440_FRESH_TIMING_AUDIT.md and analysis.json. ActiveStage3 NOT READY.
Next step is an independently reviewed offline collector for a bounded passive
trace, then a separate physical test if authorized; keep original hardware,
100ms criterion, first-error/no-retry and exact263 rollback. No higher-power stage.
