# Evidence seal phases

PREDEPLOY_SHA256 records the pre-host-recovery phase. HOST_RECOVERY_SHA256
records the then-in-progress root RESULTS/summary at commit3ff52e6; use that
commit when verifying its root-file entries. Cycle01 changed these living
result files to stopped; it does not change the earlier phase's raw evidence.
EVIDENCE_SHA256 is the final attempt03 seal including the stopped cycle,
post-stop full identity and87 passing local archive checks. No earlier stopped
attempt/seal or device software was changed.
