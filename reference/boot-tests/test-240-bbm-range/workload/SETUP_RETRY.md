The first invocation stopped before creating any kprobe or calling mprotect:
Python open(path, 'a') returned EINVAL on the seq-file kprobe_events interface.
The script had only mapped private pages; finally unmapped them. The same
boot remains responsive, no CPU fault markers, no probe/instance remains.
A direct read-only-in-effect open check proves os.open(O_WRONLY) succeeds
without O_TRUNC, while text append fails EINVAL. This is a harness setup error,
not a candidate failure, a completed workload, or justification for reboot.

v2 uses raw non-truncating os.open/os.write for named probe commands, preserving
all unrelated events. One corrected retry on the same verified healthy boot
is allowed after this review; sustained workload duration/budget is unchanged.
The initial source, stderr, hashes and command statuses remain archived.
