# Native X710 controller — offline qualification

Verdict: **OFFLINE_NATIVE_OFF_COORDINATION_QUALIFIED**. Full charging port:
**NOT READY**. This record does not replace Test321 or imply hardware acceptance.
No device command, reboot, flash, PPS Request, pump ON or rootfs/USB change occurred.

The actual `X710_NATIVE_CONTROL` candidate now links an ordered charging worker
and kernel-only request/status/cancellation API to bound SM5440 ownership/ADC,
SM5714 switching inhibition, pack thermistor/gauge and stock TCPM PPS/fixed-return
operations. It uses exact source, pack-provider and hardware-owner instances,
consumer generation, native source/budget generations and real acquisition times.
A completed native ADC now exports actual die temperature and raw microvolt VBUS;
fixed-return proof does not round a 100001uV deviation into the 100000uV window.

The OFF roundtrip executes a real coordinator pipeline. Its successful path:
ordinary source/pack/physical observation -> native SM5440 claim -> bracketed native
ADC/pack/source -> switching lease -> repeat bracket -> standard TCPM bounded PPS
-> physical VBUS/pack/source bracket -> checked native hardware cleanup -> fixed
contract -> fresh physical fixed VBUS -> atomic source-bound switching release.
Protocol failure uses the native restore receipt rather than attempting a second
failed setter. Unknown hardware OFF prohibits voltage change. Any unresolved
hardware/lease/cleanup refuses subsequent requests and vetoes PM. Timeout cancels
forward work but keeps the original worker in flight until cleanup completes.
PM drains that cleanup first; resume never queues or arms charging.

Direct entry is unarmed; native actuator activation and software-OCP grant remain
absent. The adapter table calls the actual transaction core, but active-session
park/resume and periodic monitor/refresh integration are **not completed** by
this terminal OFF roundtrip. Host-tested callbacks or compiled references do not
supply physical activation permission. No caller-owned `facts`/grant can be passed
into this public coordinator interface. The legacy OFF consumer/observer and all
ordinary supplier algorithms remain unchanged.

## Local verification

- 313 affected tests: PASS, 11.044s, zero failures/errors/skips.
  Includes actual coordinator/core threaded tests (15), supplier fault injection,
  native ownership/converter/PM lifetime tests and Type-C/pack/container regressions.
- Final native result export assertion: 17 PASS,
  0.765s; checks actual converter raw9V and30C outputs
  and zero telemetry on timeout. No kernel input changed after the final build.
- Full regression: executed:false; no routing change. Historical full-suite missing
  retired artifacts are not reclassified as passing.
- Final ARM64 Image/DTB/modules build: PASS, 60.247s, jobs8/ccache,
  standard project flow, pinned upstream a13c140cc289c0b7b3770bce5b3ad42ab35074aa (Linux7.2-rc3).
- W=1/sparse: PASS, 7.702s. No changed-driver warnings; retained
  upstream VDSO `__kernel_getrandom` declaration warning is recorded in static.json.
- New controller C/header checkpatch: zero errors/warnings/checks; bash syntax and
  Git whitespace checks pass. Initial development PM error-attribution assertion
  found cancellation reported ESTALE; now explicit ECANCELED. No prior test was
  removed, weakened or skipped.

## Exact identity

Resolved configuration is **identical** to the previous native-control candidate.
Compared with accepted311: `X710_CHARGING_POLICY` n->y, `X710_NATIVE_CONTROL`
absent->y, `SM5440_ADC_CONDITION_TEST` n->absent (existing !policy dependency).
Compared with Test303 only NativeControl absent->y. No unexpected config change.
HVC_DCC=n, USER_NS/mqueue/container, SM5714/ADC5 and ordinary ceilings are preserved.
DTB is byte-identical to accepted311. All 53 protected sources
and 18 frozen formal files are unchanged. Compiled
source copies/embedded config/notes/actual supplier/core references are checked.

Paired archive has181 exact matching file paths. ELF comparison checks runtime
sections/shape/relocations and nondebug symbols; metadata adds only the built-in
controller path plus its filename/description/license. Module build/debug identity
is recorded without treating a matched archive as a physically installed module
set. See lossless artifact-audit.json.gz and builtin metadata delta records.

Formal artifacts: `out/kernel-x710-native-controller/`. They have not been deployed.
One existing native-profile source/incremental cache was reused; its303 directory
name is historical, not its current provider identity. No new complete build tree
or D: staging was created. Retained ordinary boot/modules/partitions are unchanged.

## Remaining work and device boundary

Finish the retained active-session adapter, native activation/source-lease binding
and scheduled hardware protection/refresh loop, with first-fault OFF/fixed cleanup.
Current OFF refusal windows and Test321 RAW values are not proof of ADC validity,
calibration, current limit or hardware cutoff/OCP. Do not reflash an unchanged failed
ADC profile. Determine the next source-backed acquisition change from Samsung X710
and same-model Fedora, then register one bounded new physical scope with accepted
ordinary rollback. Physical PPS-OFF, pump <=1.8A, PM/fault recovery and higher-power
progression remain separate unaccepted stages. This record does not authorize them.
