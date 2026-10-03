# Owned PPS native observation — offline integration patch

Found a concrete active-adapter gap: the current public native reader only
accepts fixed mode. The PPS operation returns a native receipt, but later
monitoring cannot restamp that old receipt or send repeated Requests merely
to get fresh logical state. Prepared a separate read-only owned PPS API using
the current producer/lifetime/contract validation paths, without a PD setter.

The patch is unapplied: both current TCPC/header hashes and every Test317
sealed input remain unchanged. There is no live consumer or device deployment.
It supplies the producer needed by the eventual full active adapter; it does
not replace direct charging with a fixed-only or OFF-only completion claim.

88 affected tests PASS in1.456s, zero failure/error/skip. New10 methods exercise
actual patched function C and existing producer/property/lease code with real
pthread locks: native ONLINE2 receipt/no Requests/no changed budget, identity,
all8 getter failures, both lease checks, stale/reset budget/source/publication,
malformed APDO/AVS/fixed capability, PM/revocation, and drain during pinned read.
The initial negative publication stimulus incorrectly wrote the existing9V
again; that failed test/log is retained and the stimulus corrected to a real
20mV change. Production validation was not weakened. A separate temporary
patch-generation indentation TypeError is recorded; it produced no patch.

The complete patched TCPC compiles as one isolated unlinked ARM64 object:
W=1/sparse exit0 in5.841s, no changed-driver warning. Only the known upstream
vDSO declaration warning. The object and its private stage2 include have new
filenames to protect the current provider; implementation/header otherwise
match the applied two-file patch. Seven provider files (including actual
installed-profile TCPC object),98 Test317 inputs and nine formal artifacts
remain exact. Config/DTB diffs empty. No Image/modules relink/full/Actions.

Logical native observation is not physical VBUS/OCP/ADC proof. Pack snapshot
composition, actual worker integration, physical100ms sampling/current cutoff,
ON, fallback/PM acceptance and gradual higher power remain incomplete. Current
Test317 capture NOT EXECUTED; owner's current IP/connection is pending and exact
accepted311 rollback remains required. No physical failure/pass inferred from
empty ADB. Full port NOT READY. See docs/SM5714_OWNED_PPS_OBSERVATION.md.
