# Proposed Test345 — final-window refresh scheduling

Independent registered <=30s/1.8A attempt after immutable Test344 STOP. Never replay Test344 or rebind its consumed one-shot. Candidate hardware1.7A/PPS1.8A/raw1.8A, all voltage/thermal/identity/lease/fault/PM/gap/no-retry/rollback gates unchanged. Test331 known-good/original181 remains the rollback.

Before deployment freeze qualified candidate hashes and exact331/config/DT diff; register, affected guardian tests and push. New guardian accepts at most one correctly timed native refresh-deferral witness while pump remains ON, never a park/ON or PPS request after the deferral. It must report an explicit native STOP as the primary rejection even if failed cleanup occurs with an outstanding parked refresh; this does not allow failed rounds to pass. Keep3zero/>=100ms proof before initialON and each resumed refresh, <=2s park/resume bound and absolute deadline/cleanup latency gates. Test full/partial/duplicate/out-of-phase/timestamp/deadline/malformed witnesses and actual Test344 failure replay.

Owner PC connected -> fresh preparationSOC20..75 + rescue/fullidentity -> one installed candidate/normalPC boot -> preentry worker drained and OFF/unbound -> new local guardian waits ownerC1<=900s -> fresh physical C1 confirmation -> sole activation marker/rebind. Collect full raw kernel timestamps and raw samples. Clean requires explicit native complete/fixed return/lease0 and no new fault; deferred marker alone is not completion.

After clean completion: ordinary fixed9 charging30s, unplug/discharge15s, ownerPC rescue check and unconditional exact331 restore. On first anomaly: OFF/cleanup evidence, no retry/extra current, owner unplug/returnPC then exact331 restore. Record primary and cleanup separately. No45W/calibration/currentaccuracy/hardrealtime/longterm reliability claim. No more powerful/longer test until this stage is accepted.

Only preparation/build plan at this point; no Test345 physical registration or device operation is implied by this file.
