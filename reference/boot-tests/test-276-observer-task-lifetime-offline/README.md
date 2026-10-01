# Test276 — offline diagnostic task lifetime correction

Test275 stopped after one fresh-call deadline refusal and loss of shell/SSH
during observer unload. Original evidence remains unchanged. Current device272
requires owner TWRP entry; exact263rollback is pending. No physical retry/load,
flash, reboot, PPS, pumpON or current increase belongs to Test276.

Pinned Linux7.2-rc3 kernel/kthread.c: create doc lines542–546 permits autonomous
return only for standalone threads with no later stop; stop doc741–742 requires
caller to retain task lifetime; kthread_stop_put requires an extra task reference.
Old observer kthread_run starts immediately, may exit after first error or8calls,
and later observer_exit uses its unowned pointer. Offline tests covered loop
stop semantics but only checked unload ordering text, missing task lifetime.
This is a definite code defect; without persistent journal the cause of actual
Test275 transport loss remains unproved. API-110 and later unload loss are separate.

Fix only optional external diagnostic ownership: create parked thread, take
get_task_struct BEFORE wake_up_process, stop/join with kthread_stop_put before
debugfs removal. This permits autonomous completion while preserving task and
kthread completion storage until unload. No wait under result lock. Cover fast
exit before init returns, running unload, create/debugfs failure, reference
balance, and a negative-control original implementation in actual compiled C.
Retain every old test; no deadline/cadence/loop/provider/ADC/hardware policy change.

Build one revised external module in separate output directory; keep original
Test274 artifact9d66c080 at its existing path. Reuse sealed272Image/config/DTB/
181modules/Module.symvers; source/provider identity guard remains. W1/sparse/
imports and one final full host regression. No production kernel rebuild.
Before future physical validation: finish275persistent log collection/263rollback,
review exact failedboot evidence, independent new registration and rescue gate.
Revised module is OFFLINE only, not automatically deployed or hardware-qualified.
ActiveStage3 NOT READY; no modification of100ms or ordinary fixed-PD safety limits.
