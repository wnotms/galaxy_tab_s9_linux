# Native charging coordinator

This increment connects the bound SM5440 executor to the existing SM5714
switching lease and standard TCPM operations, under `X710_NATIVE_CONTROL` only.
It preserves the accepted ordinary kernel, connector, charging ceilings, thermal
policy and userspace. No device deployment or automatic protocol operation is
part of this work.

An explicitly invoked kernel request runs on one ordered worker. Short
publication locks cover admission, cancellation and result copying only; they
never span supplier I/O, TCPM negotiation, converter scheduling or work drain.
The consumer has its own generation; every forward operation also checks native
source instance/generation and the exact switching lease. The SM5440 token pins
its own provider/session. Cancellation stops forward progress; cleanup still
uses the original source tuple and cannot act on a replacement connection.

The pump-OFF roundtrip is a real coordination path: bracket fixed source and
pack/physical evidence, claim the native hardware executor, acquire switching
inhibition, acquire another native measurement, request bounded PPS through
TCPM, verify the returned source and physical VBUS, then unconditionally perform
checked hardware shutdown/restoration. Only proven quiescence permits fixed-PD
return. A fresh physical fixed measurement and an exact native source witness
precede atomic switching release. A failed PPS setter already attempts protocol
cleanup; the coordinator must first read a matching fixed contract and must not
retry a failed restoration. Unresolved cleanup latches refusal of new requests.

The same adapter table connects the actual transaction core's source/facts,
switching gate, preparation, pump, measurement and fixed-return callbacks.
Direct entry remains unarmed and native activation remains unavailable until
physical ADC calibration/current/protection/cutoff acceptance. Neither a caller
nor a fabricated `software_ocp_verified` field can grant activation. This is an
unfinished full direct-charge port, not hardware acceptance or a higher-power
release. No userspace activation interface is introduced.

The worker now retains an admitted active session across entry, monitor, refresh
and retarget. Temporary pause preserves settings/watchdog ownership; only terminal
cleanup restores/releases them. Real native source/lease binding precedes actuator
operations and maps the controller epoch to the hardware session. One ordered queue
runs 20ms monitor scheduling and 4s paused refresh/retarget, refusing late work under
the existing 100ms deadline. See [retained session design](X710_ACTIVE_SESSION.md).
Neither scheduler nor caller grants activation: the private qualification flag has
no setter and native ON remains closed. Host-only mock grants exercise the actual
entry/monitor/pause/resume/stop paths and are excluded from kernel compilation.
Physical ADC/calibration/current/protection/cutoff/PPS acceptance remains required.

Waiter timeout requests cancellation but is not worker termination. New work is
refused until the existing worker finishes its once-only cleanup. A read-only
status call exposes in-flight and unresolved ownership. A cancelled retained
session rejects all new controls until terminal drain; request-worker queue
refusal schedules immediate terminal cleanup rather than leaving monitoring
cancelled. See [cancellation and queue-failure design](X710_CANCEL_DRAIN.md).
PM marks cancellation,
flushes the work including cleanup, and vetoes suspend on unresolved hardware or
switching ownership. Resume never starts work or arms charging. Provider unbind
and detach are observed through their native token checks; uncertain OFF must
not permit a PD voltage change or an ordinary-path release.

Host tests must execute this actual worker and core with mocked suppliers,
covering successful OFF roundtrip, default direct refusal, every supplier error,
unknown OFF, failed protocol fallback, stale source/pack, detach, cancellation,
timeout/drain and PM. They prove software ordering, not physical freshness or
overcurrent response. Build qualification checks exact config/DTB, actual linked
supplier calls, paired modules and protected baseline hashes. Future physical
scope requires a separate registration and accepted baseline rollback; no flash
or PPS experiment is performed here.
