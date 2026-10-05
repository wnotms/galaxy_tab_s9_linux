# OFF continuous raw ADC candidate — offline results

The actual passive worker now has a separate default-off `sm5440-adc-raw`
profile. It performs eight bounded raw reads without requiring INT4 READY,
matching the Samsung/Fedora continuous read model. Failed Test318 READY
results remain immutable; its READY profile keeps the original requirements.

Shared actual regmap transaction saves/disables/configures/verifies/restores
ADC once. Raw/READY entry points cannot mix. First RAW read is >=20ms after
enable/readback; subsequent reads >=50ms after the previous completed read.
Source/pack provenance, faults, pumpOFF, bounds, PM cancellation and exact
cleanup remain. Debugfs records optional READY and software read timestamps,
`conversion_freshness_proven=0`, and raw mode. No charging companion publication.

An actual-C injected clock rollback across enable/readback initially failed the
new assertion: unsigned delay subtraction could permit an early read. RAW now
refuses time before that anchor; regression passes without changing READY limits.
Initial build retained in logs; final corrected ARM64 Image/DTBs/modules build
PASS 57.583s using existing incremental tree/shared ccache. No new tree.
Actual two driver objects W=1/sparse PASS 7.500s, no changed-driver
warning; one upstream vDSO `__kernel_getrandom` sparse declaration warning kept.

Host affected: **68 PASS**,1.922s,0fail/0error/0skip, including13 new RAW cases
and21 unchanged READY/native/integration cases. Every I2C transfer failure,
uncertain write, ignored write, clock, bounds, source/pack generation, admission
and cancellation are exercised against repository C/real worker functions.

Full host run:2178 tests,101.387s, **NOT PASS**:3 subtest failures,
12 errors,25 skips. Failures/errors belong to historical cpuidle/CSD/Test187
artifact tests with intentionally retired boot/Image/partition files. All raw
output and IDs retained. Do not rebuild expired images or delete/skip/weaken
these tests. Full run preceded the final clock guard; affected68 revalidated
final source. No second unrelated full run, no invented full-regression pass.

Exact resolved config diff from accepted311:

```text
CONFIG_SM5440_ADC_RAW_TEST: absent -> y
CONFIG_SM5440_ADC_TIMING_TEST: absent -> n
```

No unexpected config changes. Embedded config matches resolved file; Linux pin
a13c140cc289c0b7b3770bce5b3ad42ab35074aa /7.2-rc3 unchanged. HVC_DCC=n,
USER_NS/POSIX_MQUEUE/SM5714/ADC5Gen3 remain enabled. DTB byte-identical.
181 module-directory regular files and exact archive checked; 167
changed .ko files differ only in BTF ({'.BTF': 167}), no code/data or metadata change.
209 protected sources and26 previous formal inputs match before/after hashes.
Real worker/raw helper/native pack symbols are linked, compiled overlays match.
Full artifact/config/module-section reports in `artifact-audit.json`.

Artifacts: `out/kernel-x710-continuous-raw/` (Image.gz,DTB,config,kernel notes,
release,paired modules archive). Hashes/sizes in artifact report; large artifacts
remain outside git. Existing incremental provider now belongs to this RAW
configuration, not old accepted311/TIMING; their sealed formal archives retained.

No device mutation, boot/module/partition write, physical ADC experiment,
reboot, service change, PPS, pumpON, current increase, ENHIZ or protection change.
No DTS/DWC3/gadget/adbd/TCPM/thermal/float change. Fixed5<=1.8A/fixed9<=1.5A
and4.44V remain frozen. No GitHub Actions or main merge.

Next separately register a single PCfixed5 OFF raw transaction with fresh rescue/
pack readiness, full journal at boundaries, first-fault stop and unconditional
exact accepted311 paired restoration. RAW success would prove read transport
only: conversion freshness/coherence/calibration, physical current/cutoff/OCP,
active worker/native adapter, live PPS, fallback and PM still need completion.
**Full charging port: NOT READY.** This candidate is offline-qualified only
within the affected scope; all-suite historical prerequisites remain unavailable.
