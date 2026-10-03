# Test311 — ordinary recovery candidate device scope completed

Verdict: **ORDINARY_RECOVERY_CANDIDATE_DEVICE_SCOPE_COMPLETED**.
Candidate boot45f6c912-5034-4cdd-aa67-a47c7e20d9a0 is retained. Exact Test299
rollback remains available. No pending rollback, second attempt or extra boot.

Fresh baseline788fef75 passed config/notes, allfive partitions,181 module hashes,
real pack thermal, controls and rescue at40%,3.809V,31.8C. Boot+paired candidate
modules were installed/read back, other partitions remained exact, BCB cleared.
The candidate boot is uniquely attributed. Device ADB/services/usb0/Sink/Device
and pack thermal passed. Admission40%,3.798V,30.2C; endpoint40%,3.818V,31.4C.
Both actual charger witnesses verify Q4 ON/input500mA/fast code32(500mA)/float
code45(4440mV). AICL reduction remains permitted. No program drift/recovery
observed, so this does not physically prove the recovery branch under drift.
The registered15s same-boot endpoint completed; candidate retained without rollback.

Complete raw kernel JSON:1071 admission rows,1107 endpoint rows. Registered
fault_counts and suspects are empty. Existing display/SMMU and QCA startup
warnings remain separately classified, not erased or promoted to a broad clean
stability claim. Source311 controls/thermal precede single bounded boot-history
capture; all history/attribution gates completed. No PPS, pump ON, ADC invocation,
current raise, kernel/config/DTS/USB/adbd/rootfs change in this acceptance.

Battery current remained net negative under the PC500mA supply (-904mA at
admission,-396mA at endpoint); enabled switching charging is not proof that a
PC source covers total system load. Battery safety entry stayed within bounds.
Host Windows NCM TCP probe status255 is separate; device NCM/services/ADB pass.

The existing startup SM5440 REVBLK event is retained. It was followed by two
fresh confirmations and logged inactive; original startup fault/sample remain
in the snapshot. Three existing adjacent ADC/gauge pairs differ263/211/329mV.
No independent physical calibration,100ms freshness or active charging grant
is inferred from this ordinary acceptance. ADC cause remains UNKNOWN.

Offline35 affected tests PASS0.145125s/zero errors,failures,skips; syntaxPASS.
Unchanged Test308 build qualification/artifacts reused; no new build/full/Actions.
125 inherited Test310 inputs unchanged/136 sealed. Six Windowsstage hardlinks,
one unique helper; no largecopy. Initial incomplete fixture error retained.
No tests/build rerun for these results-only edits (`executed: false`).

Full Stage3 remains **NOT READY**: ADC validity/freshness, active protections,
actuator, PPS/handoff/fallback and PM physical acceptance remain outstanding.
Next compare one vendor-backed OFF-mode ENHIZ condition using current accepted
ordinary recovery, preserving original fault/read-validity/exact cleanup. No PPS
or pump permission follows from this result. Historical309/310 STOPs unchanged.
