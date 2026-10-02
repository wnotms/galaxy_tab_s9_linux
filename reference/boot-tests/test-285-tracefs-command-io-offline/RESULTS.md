# Test285 offline command I/O qualification

**OFFLINE_COMMAND_IO_QUALIFIED_DEVICE_NOT_TESTED.** 12 affected tests pass,
0 failures/errors/skips; syntax/input hashes/protected source checks pass.
No build/full/routing/CI/device operation. Frozen27950/28024 and272provider/
276build/static/full1481 qualification reused, not rerun or weakened.

PinnedLinux7.2-rc3 kprobe_events is a seq_file command interface: seq_lseek
rejectsSEEK_END; O_TRUNC releases allprobe definitions. CPython3.13.7 append
construction seeks to end (official source linked inREADME). HostCPython3.14.4
realwritable seq_file append-open reproducesEINVAL before anywrite; nonseeking
open+close succeeds, with commandwrite mocked so zero hostkernel writes.
This explains a concrete flaw in279's ordinary-file mock qualification.
Test284 lacked syscallstage/devicePythonversion capture, so its exact exception
origin is a source-consistent inference rather than a proved device syscall.

New adapter overrides onlycommandwrite with O_WRONLY|O_CLOEXEC, one newline
command, no truncate/append/create/seek/retry. Short/failed/interrupted commands
close descriptors and stop. Exceptions nameopen/write stage. Original279Session/
280coordinator/parser/control IO/ownership/loss/miss/cleanup policy unchanged.
No new probe, offset, kernelpatch or actualdevicewrite tested here.

Current baseline remains the restored263 from284; this offline phase did not
contact it. Captured finalSMMU103 evidence contains10context+10syndrome lines;
rootcause/charging relationship unknown, originaljournal STOP unchanged.
Bounded search of listedolder kernel-json filenames found no103match; this
is not an exhaustive historical/rootcauseproof. See smmu103-facts.json/raw284.

Next offline SMMU/boothandoff source mapping audit before new physicaladmission,
then separate registration selecting thisadapter. No automatic replay of284,
newobserverload, PPS/pumpON/currentincrease/ADC/deadline/kernel/config/DT/USB/
rootfschange. FreshADC/request timeout remains unmeasured; ActiveStage3NOTREADY.
Fullchargingport goal remains incomplete and active.
