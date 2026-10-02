# Test286 results

**OFFLINE_DISPLAY_STARTUP_CLASSIFIER_QUALIFIED_DEVICE_NOT_TESTED.**
19 affected host tests and syntax passed. Archived284 candidate(context99) and
restored263(context103) full-journal replays meet the new bounded diagnostic
profile; Test284's original finalSUSPECT/STOP is not rewritten.

Pinned source and sealed compiled DTB identify SID1c00 as MDSS and all recorded
IOVAs as reserved splash addresses. The faults precede the charging probes.
The underlying display/SMMU handoff defect remains UNKNOWN and unresolved.
No claim of kernel stability, ADC timing acceptance or charging approval follows.
See `source-facts.json`, raw-preserving replay reports and `INPUTS.json`.

Zero device commands, trace/probe writes, observer loads, flash/reboots, PPS
requests or pump enables. Kernel/config/DTS/modules/ADC/deadline/USB/adbd/rootfs,
fixed charging limits and thermal safety unchanged. Same sealed artifact
qualification reused; build/full-suite executed:false, not a regression pass.
No GitHub Actions. Last verified device remains the restored Test263 from284.

Active Stage3: **NOT READY**. Fresh request timeout attribution still UNKNOWN.
Next: separate one-passive-trace registration using the tested nonseeking
tracefs adapter and this profile, then unconditional exact263 rollback.
