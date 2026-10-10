# Bounded Fedora listener2 return observer — compiled, not deployed

Test387 still lacked SSC400 after the wire repair. Actual stat output establishes
callback metadata, not the encoded return frame or successful next2 boundary.
The new isolated profile keeps Fedora0.4/stat/codec/library unchanged and modifies
only listener.c plus one trace header. No callback/policy/data/encoding/ioctl
argument changes. Explicit HEXAGONRPC_RETURN_TRACE=1 opt-in, default OFF.
TX/next2-return/RX sequences record exact bytes, scalar/context and transport status;
next2 success is not DSP parsing proof. A blocked final call remains pending.

Per-frame8192B and per-daemon512KiB limits emit an explicit limit/error marker;
never silently truncate/modify a reply. The parser rejects gaps, restart/attribution
changes, malformed frames, limits and inconsistent next2/context/lengths. Independently
reconstruct registry open/read/close replies and hash only actual written bytes,
excluding unused read-buffer tail. Match exact stock manifest, all nonempty groups,
closed/acknowledged linear reads; no registry mutation or guessed selectors.

70 affected tests PASS/0skip:35 new real-C listener/UBSan/admission/framing/content
checks,24 wire/composition and11 stat-profile checks. Networkless pinned Debian
ARM64 build passes both upstream QEMU tests. Actual modified listener+codec also
pass6 ARM64/QEMU cases (normal,large,transport error,frame limit,budget,disabled).
All56 compiled source hashes match. Daemon9e9884754d5032f0410ea5ac94e2e6f0fd9ea95e3fafec9b8ae30cbab49c1eb3;
library1be44d2f unchanged. Python syntax PASS; kernel/config/DTS/181 qualification
reused, no new kernel build/routing/full regression/Actions.

No deployment/reboot/ADSP/RPC start this preparation. Accepted Test370 remains
restored; sensor/rotation migration unfinished. This is a qualified observation,
not a sensor repair/PASS/rootcause. Independent Test388 must register this changed
boundary before one bounded candidate startup, retain first failure and restore
Test370/default GNOME. No unchanged Test387 retry/DIAG masks/PPS/pump.
