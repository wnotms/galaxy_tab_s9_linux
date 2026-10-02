# Test285 — offline tracefs command I/O fix

Scope: address the append-open defect exposed by Test284 tracing setup, while
preserving its STOP/UNKNOWN and finalSMMU103suspect. No physical retry or device
command in this test. Do not change kernel/config/DT/ADC/deadline/charging/USB.

Pinned Linux7.2-rc3 kprobe_events uses `seq_lseek`, which has no SEEK_END case.
Its O_TRUNC open releases all kprobes. Python append-open performs SEEK_END in
FileIO construction ([CPython3.13.7 source](https://github.com/python/cpython/blob/v3.13.7/Modules/_io/fileio.c)).
Thus regular-file append tests do not model this kernel command interface.
HostCPython3.14.4 reproduction on this process's writable seq_file opens fail
EINVAL in append mode; nonseeking open/close succeeds. No actual host write.
This proves the host mechanism; Test284 did not record open-vs-write failure
location or device Python version, so its exact exception provenance remains
an inference, not an independently captured device syscall trace.

`tracefs_io.TraceFS` subclasses frozen279adapter and overrides only kprobe_events
write: O_WRONLY|O_CLOEXEC, no append/truncate/create/seek, one complete newline
command, descriptor close on error/interrupt. Short/failed write stops, no
suffix retry. Errors name open versus write stage. Ordinary private-instance
controls/read/list/mkdir/rmdir and279Session/280coordinator are unchanged.
No global clear, alternative symbol/offset or runtime diagnostic changes.

New syscall/realHOSTseq_file regression tests only. Preserve all old27950tests
and historical evidence; reuse unchanged session/parser/kernel qualification.
No build/full/routing/CI or hardware test. Future portable wrapper must explicitly
select this adapter and have a separate registration/live safety/rescue gates.
Current263 full-journal SMMU103suspect first needs offline analysis; no exemption
or automatic new flash/probe/acquisition. ActiveStage3 NOT READY.
