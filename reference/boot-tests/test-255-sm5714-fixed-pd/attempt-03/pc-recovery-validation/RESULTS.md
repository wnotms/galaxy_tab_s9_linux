# PC recovery host preparation

All33 retained Test253 pure cable/FunctionFS/runner tests passed, zero skips;
the new thin capture compiles. It reuses CableCycle, native/snapshot parsing
and review_adbd; no historical production-state arming/baseline gate is called.
Daemon PID827 and the exact accepted Test253 binary hash are pinned.
A fresh>=10s offline bound is observed before requesting PC attachment.
Recovery upper bound starts at the last confirmed offline command START,
includes sampling/transport uncertainty and must<=60s. Native shell and NCM
must prove same boot and daemon identity; interface-bound banner and PnP
are required. Initial native/NCM failures are archived, never hidden as
transient-free. No reset/restart/rescan/backend or configuration change.
The subsequent independent>=150s PC window remains mandatory.
