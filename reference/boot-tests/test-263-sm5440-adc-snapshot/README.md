# Test263: SM5440 cached ADC evidence interface (offline)

Owner requests next porting step after Test262. Read docs/SM5440_ADC_SNAPSHOT.md.
Start branchtest/1e1f0840; current hardware stays acceptedTest260 passive.
Purpose: make complete current/retained ADC evidence and freshness available
without new I2C access or changing validated fixed-PD/SM5440 behavior.

Scope: passive driver optional read-only debugfs snapshot, host tests and docs.
No config/DTS/USB/adbd/CPU/battery/thermal/protection/current/TCPC change;
no PPS, live adapter, pumpON, flash/reboot/rootfs/device action. Default fixed
profile still does not bindSM5440; separately compiled passive profile only.

Design registration precedes implementation. Qualify changed source once:
affected tests during development, one final build/config/DT/protected/paired
module audit and full retained host suite, plus changed-driverW=1/sparse.
Use fresh263 output/build directories; never overwrite accepted260/Test255.
No Actions or repeated qualification for later docs/results commits.

Physical acceptance NOT executed by this task. ADC calibration, OCP and PM/live
handoff remain unresolved; ActiveStage3 NOT READY. Rollback is not required
because nothing is deployed. Preserve earlier stopped trials/evidence.
