# Test316 — fixed source classification/readiness

Verdict: **FIXED_CONTRACT_CLASSIFICATION_OFFLINE_QUALIFIED_NOT_DEPLOYED**.
Source `8b77b426923b5b93ad4c9825eea32291b0f28e16`. No device operation/flash/reboot. Accepted311 remains installed.
Full direct-charge port NOT READY; Test315 qualification/result is not rewritten.

Pinned Linux TCPM selects source capability labels PD/PD_PPS/PD_SPR_AVS/combined
separately from ONLINE fixed1/PPS2/AVS3. Test273 directly records C1 fixed9V1.5A
ONLINE1 and USB_TYPE_PD_PPS. The diagnostic now matches its unchanged producer's
classification, still refuses actual PPS/AVS or !charge/!fixed9. No protocol setter.

Initial coherent5V snapshot with a fixed9V>=1A source PDO may wait for TCPM's
normal negotiation, preserving first raw snapshot and pinning instance/source
epoch. Missing/weak9V/APDO-only/malformed/PPS source refuses before own bus or
lease. Both40 calls and4s elapsed are bounded; a late in-flight return is rejected,
not a hard preemption guarantee. No retry after9V admission/fault, no wider ADC/
100ms release limits or ordinary fixed5V1.8A/9V1.5A/4.44V/thermal policy.

128 affected tests PASS 1.931s, no failure/error/skip. Actual
coordinator plus pinned Linux PDO helper code covers supported capability labels
with fixed mode, standby->9V, source/PM changes, timeout/slow supplier, APDO/weak/
missing9V and existing full bus/restore/context fault cases. Ordinary preprocessed
driver paths unchanged. No test removal/routing/full/Actions.

8-job ARM64 standard Image/DTB/modules build PASS 81.444s.
W1/sparse two actual objects PASS 7.616s; standard object
restoration PASS 6.150s. Object/vmlinux hashes remain
exactly qualified; no changed-driver warning, existing upstream vDSO/config seed
warnings retained. No unrelated upstream changes. Only config change versus
accepted311 remains ADC_CONDITION_TEST n->y, unexpected empty; DTB identical,
96 protected files and12 overlays verified, USER_NS/mqueue/Docker/DCC/SM5714 gates
pass, embedded config exact and181 modules match deterministic archive.

Prior315 formal artifacts/symbols/79 generated inputs frozen before reusing same
incremental provider, now316; no new complete tree or Windows stage. Window307-316
306 reused305 images already retired; logs/modules retained. See source-context
and actual qualification manifests/raw logs/hashes.

Next independently register the corrected candidate's one fixed9 OFF-context
comparison with preattached fixed9 charger, fresh pack/Wi-Fi rescue and
unconditional exactaccepted311 restore. Physical ADC agreement/freshness, OCP/
watchdog/ON/PPS and actual runtime fallback/PM remain unproved.
