# Test305 — isolated ENHIZ/ADC condition candidate, offline

Purpose: prepare one source-backed pump-OFF comparison after Test304 observed
CNTL6=0x89. A separately enabled profile temporarily clears only vendor ENHIZ
bit7, runs the unchanged converter and always attempts verified restoration.
This is not a production ADC fix or permission to enable PPS/direct charging.

See `docs/SM5440_ADC_CONDITION_TEST.md` for sequence, source provenance,
lifecycle and fail-closed boundaries. Normal preprocessed driver paths/structures
are identical to949d6b73. The diagnostic build does not publish a companion and
does not reschedule a second conversion; failed restore stays pending/faulted.
Original converter/rearm/quiesce/threshold/fresh APIs are byte-identical.
Normal Stage1/Stage2/USB/DCC/charging limits and passive thermal fix remain.

Profile: `GTS9_CHARGING_PROFILE=sm5440-adc-condition`; default-off
`CONFIG_SM5440_ADC_CONDITION_TEST=y`, passive pump monitor=y, policy consumer=n.
DTS uses the existing passive overlay. No new hardware threshold/active init.

Local integration regression:1,748 tests passed, no failure/error/skip,112.621s.
Final21 diagnostic/profile tests passed0.705s, including an added normal-path
preprocessor equivalence check. Existing1,728 results are reused unchanged;
unique qualified tests1,749. No tests deleted, skipped or weakened; no Actions.
ARM64/W1/sparse/config/DT/protected/module qualification subsequently passed;
see [RESULTS.md](RESULTS.md). Physical entry currently waits for battery recharge.

Old297 incremental cache debug/config/generated inputs were compressed and
hash-verified (2,733 files); the cache can be reused instead of another4.7GiB
clone. Formal artifacts and accepted rollback remain unchanged. Cache reuse
does not make a rewritten cache a usable old297 provider.

Physical mutation/reboot/flash/PPS/pump: executed:false. Retained device remains
Test299/Test300. A separately committed/pushed one-boot scope is required before
physical comparison. Full active Stage3 remains NOT READY.
