# Test315 — source-bound fixed9 SM5440 OFF context

Purpose: implement/offline qualify the missing source/pack/switching context of
SM5440 ADC comparison; not repeat terminal Test313 PC5V experiment. Accepted311
ordinary fixed charging remains the installed baseline. No physical execution
scope is registered here, and no current increase, PPS or pump activation.

Design was written before implementation in docs/SM5440_FIXED9_OFF_CONTEXT.md.
Use the existing default-off sm5440-adc-condition profile, no new config symbol,
DTS/TCPM/DWC3/gadget/adbd/rootfs change. The actual diagnostic worker gates fixed9
1000..1500mA source/epoch, standard real pack limits, actual OFF VBUS8.5..9.5V,
zero IBUS, die/pack temperature and live pre-status. An initial exact inactive
REVBLK needs two new fault-free confirmations; live/recurrent faults stop.
Checked SM5714 lease precedes audited OFF-only settings and ENHIZ/ADC comparison.
Restore original ADC-off/ENHIZ/settings with pending and separate errors on
uncertainty. Retain the inhibited lease:500ms diagnostic data cannot authorize
100ms source-atomic switching release. No old capability/cache becomes a grant.

Qualify actual coordinator/control/condition C with framework and bus fault
injection; preserve default preprocessed driver equality. Reuse standard pinned
8-job ARM64 incremental tree after freezing314 symbols/79 generated inputs and
formal hashes. Save exact config diff vsaccepted311, identical DTB, overlay and
protected hashes, embedded config/notes/181 modules and W1/sparse. Use only
modified parts/dependencies; no full/Actions or retired-image regression replay.

Future separate physical registration must arrange a known fixed9 source before
this one-shot boot worker runs, fresh safe pack and Wi-Fi rescue, preserve raw
pre/post STATUS and the first fault, and unconditionally restore accepted311
boot/modules after capture. PC5V is deliberately refused; do not reuse old313
PC runner/rollback. No software OCP/watchdog/ON/PPS/fallback readiness is claimed.
