# Test314 — OFF-only SM5440 settings transaction

Verdict: **OFF_ONLY_SETTINGS_OFFLINE_QUALIFIED_NOT_DEPLOYED**.
Full direct-charge port: **NOT READY**. Installed accepted311 remains untouched.
Source revision: `deb28242954d6fb289b41926d656526df8f69ac7`. No flash, reboot, partition/module
replacement, device register operation, PPS request or pump activation this turn.

New sm5440-control.c/.h implements actual regmap programming/readback for three
source-audited fields while OFF. Requested input1000..1800mA is rounded DOWN;
VBAT regulation4437.5mV does not change SM5714's accepted4440mV float policy;
frequency follows X710450/650/850kHz mapping. Captures original fields and ten
untouched-register witnesses; live pre-status and OFF are checked before writes.
Uncertain writes are marked pending before I/O. Errors trigger bounded reverse
restoration only after proven OFF, with first operation and cleanup errors kept
separately. Unproven OFF/protection drift/failed cleanup stay faulted/pending.
No INT consumption, fault masking, reset, ENHIZ, current margins or protection
aggregate import. No live adapter/export/probe hook or CHG_ON implementation.
These are hardware-layer helpers, not source/thermal/physical-current grants.

[VENDOR] exact X710 driver/header and r02 DTS hashes/numbered source excerpts
are in source-analysis, with [FEDORA ab123e7d] cross-check. Excerpts normalize
trailing whitespace; full original source hashes identify the unchanged input.
Vendor software-OCP requirement remains unresolved; input regulation is not a
qualified hardware protection or permission to enable the pump.

Eight-job standard ARM64 Image/DTB/modules build:exit0, 87.075s.
W=1/sparse for the new actual object:exit0, 6.987s;
object and vmlinux hashes unchanged. No changed-driver warning; existing
upstream vDSO missing-declaration warning and config-seed normalization warnings
are retained, with no unrelated source edits.

105 affected host tests:PASS, 1.529s,
zero failure/error/skip. Real new C code is compiled and bus-fault injected at
every prepare/restore I/O position, including uncertain accepted writes,
silent drops, mode/live fault/detach changes, protection/unowned-bit drift and
persistent errors. Existing passive/ADC/PPS consumer and source-preparation
profile classes are preserved. No routing/full suite/Actions. An initial
mistakenly broad444-test selection included retired Test187/old cpuidle image
checks:3 failures/8 errors/19 skips are retained in overbroad-host.json and are
not presented as a full-regression pass. No test deletion, skip or weakening.

Exact accepted311 ->314 resolved config diff saved. X710_CHARGING_POLICY:n->y
selects the existing inactive offline profile. SM5440_ADC_CONDITION_TEST:n->absent
follows its existing !X710_CHARGING_POLICY dependency and remains disabled.
Unexpected config changes:empty. DCC remains disabled; USER_NS/mqueue/container
and SM5714/ADC5Gen3/fixed charging gates pass. DTB byte-identical.96 protected
files unchanged,12 compiled overlays match the source revision. All181 matching
module files agree with the deterministic archive. Config extracted from
Image.gz matches resolved config; notes and formal artifact SHA-256 are saved.
The two helpers exist in vmlinux and have no exported-symbol entry.

Reused the existing incremental cache. Prior Test312 diagnostic symbols and79
CRC/config/generated inputs were compressed and individually verified first;
retained for Test313 fault analysis. Formal312 and accepted308 artifacts remain
unchanged. Cache is now the314 offline-policy provider, not a312 provider.
No new full build tree or Windows staging copy; Test304 had no obsolete images
outside the305–314 retention window. Current rollback and original logs remain.

Next implement the source-bound pump-OFF preparation adapter, with physical
VBUS/live pre-status/pack/epoch/switching ownership. The100ms physical evidence
and ADC disagreement remain real blockers; do not widen them, restamp old data,
repeat313 or flash this unused-helper profile merely to produce another round.
Qualified OCP/watchdog, actual ON actuator, runtime handoff/fallback/PM and
separate conservative hardware acceptance still remain toward the full goal.
