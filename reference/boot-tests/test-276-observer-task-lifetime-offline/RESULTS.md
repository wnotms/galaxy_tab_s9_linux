# Test276 — OFFLINE_TASK_LIFETIME_FIX_QUALIFIED

Code7a887eab fixes optional observer ownership only. Parked kthread_create,
get_task_struct before wake, kthread_stop_put before debugfs removal. Autonomous
worker completion retains valid task/exit storage. No extra request, deadline,
ADC averaging/channel/polling, charging, provider, DT, config or rootfs change.

26 affected tests pass, including actual compiled init/exit reference models,
immediate worker exit before init returns, running unload, debugfs/create failure,
balanced ownership and negative-control oldcode failure. Initial mock compilation
failed because missing stddef/null declaration and misleading one-line indentation;
corrected before final26/full qualification. No test was deleted/weakened/skipped.
Final full1481 PASS (109.852s unittest), no failure/error/skip; all prior1475 IDs
retained, six additions. Two pre-existing Pogo mock unused-function warnings
remain; module build/static has no diagnostics. Syntax checks pass.

External ARM64 clang/ccache W1 build and sparse pass; static check did not change
object. New unsigned .ko9aafabf6/273080B is in separate out/sm5440-fresh-observer-276,
not installed. Original274.ko9d66c080/267536B preserved at original output path,
but no longer suitable for further physical load. All imported CRCs match sealed
272Module.symvers; fresh symbol0xf172e855. Module has no I2C/TCPM/charger setters.

149 tracked hardware/config/DTS/patch/rootfs/userspace/boot files equal frozen272;
Image/config/DTB/notes/181module archive unchanged. Config/DTdiff empty. Reused
272kernel qualification, no kernel provider rebuild or GitHub Actions. Exact
compiled source hashes and artifact checks saved in ARTIFACTS/final-consistency.

Test275 remains STOP: one fresh refusal-110/108ms, then unload/shell/SSH loss.
This source bug is definite; retrieved persistent failed-boot logs contain no
postfault stack, so causation of the actual loss remains unproved. No physical
Test276 commands/deploy/reboot/PPS/pumpON/
current changes. Exact263 rollback and baseline endpoint have since completed. See Test275
rollback records; this is not a physical Test276 test.

Failedboot persistent1109rows stop before module load; pstore empty. No postfault
stack was captured; absence does not disprove a fault. Any future revised observer run
needs independent registration, no retry or rewrite of275. Queue/converter/
delivery timing still unqualified; no relax100ms/safety or claim successful ADC
conversion from refused zeroed output. Nonzero calibration/OCP/liveadapter/PM
remain separate. ActiveStage3 NOT READY.
