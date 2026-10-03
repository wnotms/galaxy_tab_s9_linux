# Test308 ordinary charger programming recovery — offline

Verdict: **OFFLINE_ORDINARY_PROGRAM_RECOVERY_QUALIFIED**.
Source: `158d0dd376dac2770cd72582be1bd1fe2474e71d`.
Device deployment/physical charging acceptance: **not executed**.

Test307 directly showed Q4/input/fast/float controls inconsistent with initial
ordinary charging logs; it did not establish reset/watchdog cause. The actual
battery driver now keeps a successful readback witness and checks its four
stable controls during authorized ordinary same-attach polling. Unchanged state
and AICL-lowered input generate no writes. Intentional OFF invalidates the
witness. One positively observed mismatch may re-run the existing configuration
after proven Q4OFF and fresh fault/pack thermistor/live budget checks. A second
mismatch, transport failure or failed programming latches a program fault even
without Type-C ownership. Cleanup reads Q4/input back; failed OFF is unproven.
No automatic reset, watchdog clearing or hardware mode write was introduced.

Existing source/current/thermal policy, fixed5V<=1.8A/fixed9V<=1.5A input caps,
4.44V float, full-charge behavior, PM/standby/lease gates and TCPM ownership are
preserved. No SM5440/PPS/pump/USB/gadget/adbd/DT/config fragment/core change.

## Executed validation

-102 unique affected host tests passed,4.759s;15 new tests execute actual C,
 including each recovery transfer error, silent write delivery, OFF proof,
 source contraction, thermal/OVP/watchdog/detach refusal, intentionalOFF,
 bounded recovery, second drift, independent latch and actual poller routing.
 Existing87 selected tests remain unchanged in assertion strength. No skip,
 failure, error, test deletion, suite routing change or new full regression.
-Standard ARM64 Image/DTB/modules build passed,85.037s. Two earlier sessions
 were interrupted before link completion; their original logs are preserved
 and are not passes. The same incremental cache resumed after process absence
 was established. The final result records actual source hash/base revision.
-Changed driver W=1/C=2/sparse passed,8.314s; object/vmlinux identical to build.
 No changed-driver warning; known upstream vDSO declaration warning retained.
 Checkpatch passed with zero diagnostics.
-96 protected files unchanged;10 compiled driver/header overlays match the
 recorded source commit. Embedded config equals resolved artifact config.
 Container gate passes85 required-y symbols; HVC_DCC remains disabled.
-Against accepted299 the sole exact config delta is the already introduced
 `CONFIG_SM5440_ADC_CONDITION_TEST: absent -> n`. The generated explicit
 disabled line is not an enabled diagnostic. Feature settings are unchanged;
 DTB is byte-identical. The exact diff is preserved, not labeled byte-identical
 config.181 regular module-directory files match the deterministic archive.
-Historical Stage2 Image has been retired under the owner's ten-round policy;
 no missing-image hash check is falsely reported as passed. Current accepted299
 remains the comparison and rollback baseline.

## Storage and device boundary

Artifacts remain only in `out/kernel-x710-308-passive`; hashes/byte sizes and
full paired module manifest are in `validation/artifact-audit.json`. No Windows
staging/flash package/rootfs installation, reboot or device command was made.

After qualification, replaced302 regeneration-only intermediates were removed:
11,684 files/~3.87GiB.7,871 retained debug/generated/module input files were
hash-verified unchanged. Its former directory is not a complete incremental
provider; final debug/CRC/module inputs remain.308 is the one active incremental
charging cache. No source worktree or old formal evidence was deleted. Original
copied-cache and cleanup manifests retain provenance without archiving objects.
The final build inherited the pre-existing external ccache; static validation
uses project `.work/ccache`. No new private ccache was created.

Last Test307 device reading remains0%/2.775V/Not charging/lpcharge=1; no fresh
safe entry is asserted. Await ordinary C2 recharge confirmation and battery
recovery before a separately registered physical test. Do not transplant this
image into Test306, whose input seal names the previous driver. Preserve exact
accepted299 rollback and thermal fix. ADC validity/freshness, active protection,
actual PPS/handoff and PM hardware acceptance remain incomplete: full Stage3
**NOT READY**. See README.md for the next bounded acceptance scope.
