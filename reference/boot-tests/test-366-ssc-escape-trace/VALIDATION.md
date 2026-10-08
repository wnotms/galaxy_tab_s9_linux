# Offline validation

Reuse keyboard-escape-driver standard ARM64 build (Image/DTB/181 modules,
target W=1 and 7 affected ASan/UBSan tests), plus ssc-keyboard-candidate exact
AVB/header/payload verification, 67 input import CRCs and 12 actual-artifact
loader checks. No new kernel/config/DTS/charging change here. The isolated
hexagonrpc verbose binary uses the exact prepared same-model Fedora source;
its two upstream tests passed. Its shared library is byte-identical to the
already qualified installed package; no library/package replacement for tracing.

New affected tests execute actual overlay installation/recovery against temporary
roots, retained asset/runtime transaction invariants against Test366 copies,
Linux QRTR control encoding, finite packet/time bounds, raw packet retention,
socket cleanup, genuine launch-reply loss, first malformed sample/identity
failure with cleanup despite unavailable evidence, old namespace rejection
before partition writes, mapping transition and protected ordinary identities.
Final counts and log are in HOST_TESTS.json/host-tests.log. No skip/deletion of
old tests; the original historical runtime/runner/result files are untouched.

Initial host runs exposed two fixture assumptions: injecting loss into every
command now fails during the new read-only ExecStart check before launch, and
the temporary runner root lacked its required package manifest. The injection
was narrowed to the actual launch to preserve the original lost-launch safety
assertion; the missing fixture file was added. Initial failed logs are kept,
not relabeled. No device action occurred during those tests.

Shell/Python syntax and all registered inputs/artifact hashes are checked before
stage/installation. Current owner affected-only workflow applies: no full
historical regression, routing changes, Actions or CI. Historical full regression
remains NOTPASS; selected local tests do not imply it passed. Registration-only
status is not a hardware acceptance or sensor/keyboard proof.
