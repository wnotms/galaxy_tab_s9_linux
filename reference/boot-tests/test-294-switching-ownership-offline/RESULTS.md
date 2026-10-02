# Test294 — switching ownership offline results

OFFLINE_SWITCHING_OWNERSHIP_QUALIFIED_DEVICE_NOT_TESTED.
Source bb5341463db966a511769d61bbbf3c24ac210e90; no physical operation.

The battery backend now has exclusive, monotonically unique acquire/release
leases. Acquire inhibits before I/O, verifies Q4 OFF and minimum100mA, preserves
fixed contract. Wrong/revoked token cannot restore switching. Changed budget,
standby, poller fault/detach, suspend and unpublish revoke ownership but keep
inhibition; rebind inherits it. Release requires caller-proven pump OFF and
fresh physical fixed VBUS and holds chg_lock through ordinary restoration.
No live caller, PPS authorization, pumpON, current or float/thermal change.

Validation:

- 16actual-C ownership/readback/fault/PM/rebind/concurrency tests PASS.
- 1557full host tests PASS,0failure/error/skip; all1520previous full-run IDs retained.
- ARM64 ccache build PASS,99.44s; independent290cache seed24.30s, no hardlinks.
- W=1/sparse PASS for changed driver; object SHA unchanged. One existing upstream
 VDSO __kernel_getrandom missing-declaration warning, no changed-driver warning.
- Exact290config and DTB identity, empty diffs; USER_NS/mqueue/container features
 retained, HVC_DCC=n. No new dtbs_check: identical previously qualified DTB.
- 96protected inputs unchanged,8compiled overlays match committed source;
 Stage2 frozen artifacts intact,181paired module files/archive payload exact.
- 167module directory files differ from290; binary-section cause not classified
 in this round. Use the new paired archive, never mix old modules with new Image.
- 263/290/291/292/293 evidence seals and290 artifacts verified unchanged.

Artifacts: out/kernel-x710-294-passive; exact identities in ARTIFACTS.json.
Build/audit/static commands, initial fixture failures and full report are retained
under validation/. Initial failures were fixture missing last_online and missing
fault-injection setup; fixed without changing old assertions or runtime limits.

Installed263/Test293 refusal unchanged. Live TCPM/SM5440 coordinator, sensor
calibration, physical OCP/cutoff and PM supplier ordering remain incomplete.
Stage3 active NOT READY. This ownership API is a prerequisite, not a live
PPS/direct-charge acceptance result. Next physical scope must be independently
registered and answer a specific hardware question with short bounded evidence.
