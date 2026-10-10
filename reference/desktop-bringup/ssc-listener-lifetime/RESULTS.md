# Default listener lifetime — offline qualification

Test395 actual X710 startup evidence and Qualcomm primary implementation
(a56e9d4de3614a8d8f4b0e15ff561350c4b686e3/src/adsp_default_listener.c)
retain a default-listener registration reference during reverse RPC. Existing
Fedora-derived0.4.0 closes its only registration context before the callback
loop. A real-C host/QEMU harness reproduces that order; it is a lifecycle
difference, not yet a proved SSC root cause. No guessed SNS/library request.

Only hexagonrpcd/rpcd.c changes over the qualified Test393 status69 profile.
The caller owns the opened context until loop exit; registration failure closes
once without entering the loop. Remote-close failure releases local ownership
without retry; the fd/session handles process teardown. The common cleanup now
also deinitializes localctl after failed registration/open. Message schemas,
attach ioctl, callback payloads, mapped inputs and error69 semantics unchanged.
Unrelated allocation failures/FS interface teardown are not claimed fixed.

73 affected host tests pass,0skips; exact source/real C/UBSan/fault and unchanged
open/return dependency IDs in HOST_TESTS.json.16 actual ARM64/QEMU cases pass
(8 original +8 final). Normal order ORCLD→ORLCD; open/register/loop/close errors
and512 repeated sessions verify no early release/retry/double close/local
context leak in the new ownership path. Original close-error cases reproduce
a context leak and held=true; an initial report checker overgeneralized
held=false to all original cases and was corrected, with initial error retained.
No C source/test expectation was weakened. These mocks do not prove DSP teardown.
2 upstream Meson tests pass. ARM64 release daemon compiled in existing pinned
builder, unchanged companion library hash1be44d2f…. No kernel build/full
regression/Actions/device operation. ARTIFACTS.json binds deployed candidates.

Nothing installed. Next separately register one new early-ADSP/ordered-RPC
observation using this daemon, preserving the existing kernel/assets/30s bound,
PDR/state/framing/stat/return evidence, first-failure stop and exact Test370
GNOME return. Do not repeat the unchanged Test393 binary. PPS/pump/DCC OFF.
SSC/accelerometer/rotation remain unproved.
