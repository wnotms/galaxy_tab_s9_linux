# Diagnostic fixed9V startup correction — offline qualified

Source80d590f0, profile SM5440_ADC_ONESHOT_TEST. Ordinary PC predicates, converter,
rearm and PM are unchanged. Only diagnostic startup context accepts 8.5–9.5V;
initial inactive REVBLK requires two new clean same-class confirmations, unchanged
controls and existing5s deadline. No direct/charging authority. Test324 retained
STOP and restored accepted323; no device command ran for this correction.

158 affected actual-C/predicate/converter/legacy/profile tests PASS, zero skips,
6.601s. Failed drafts are preserved: one literal legacy-function freeze exposed
that the diagnostic extension should remain separate; a following test caught
9V-to5V cross-class confirmation. Final helpers fix both without changing or
weakening any retained old test. Initial new-fixture mode/UVLO expectations were
corrected to actual existing MODE_MASK and OFF fault decoding; hardware policy
was not changed to satisfy those fixtures.

Final ARM64 Image/DTB/181modules PASS60.731s in reused cache. First83.674s build
was not qualified because its draft cross-class gate failed; it was rebuilt from
final source. Targeted W=1/sparse PASS13.538s, no warnings; exact qualified object
restored after normal command records, no formal relink.

Config byte-identical to Test324; accepted323 differs only ONESHOT absent->y.
Exact accepted DTB, Linux7.2-rc3 pin/DCCn/container/SM5714/ADC5 unchanged.59protected
sources and30formal baseline files verified.181 exact module file set and runtime
sections/symbols unchanged; debug/BTF differences recorded. Boot-only package
built/unpacked/hash-sealed offline with exact accepted323 rollback. No Windows
staging, device flash/reboot/module/rootfs change, Actions or main update.

READY for a newly registered pump-OFF diagnostic test. Not hardware-tested, no
100ms ADC/calibration/OCP or direct-charge acceptance. Full port NOT_READY.
NEXT_PHYSICAL_PLAN is a proposal; no automatic repeat of failed Test324.
