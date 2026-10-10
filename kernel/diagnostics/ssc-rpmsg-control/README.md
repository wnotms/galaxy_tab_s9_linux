# Temporary native RPMSG control interface

Build with `python3 scripts/build-ssc-rpmsg-control.py`. This copies unmodified
Linux v7.2-rc3 `rpmsg_ctrl.c` and its two internal headers from the pinned tree,
then compiles an external module against the exact accepted Test370 provider.
The upstream SPDX headers remain intact. No full kernel build, .config edit,
installed module replacement, device connection or module load occurs.

This corresponds to an interface enabled as a module in Fedora X710's
`config-mainline.aarch64`. It is not a missing sensor-driver fix: Test383 showed
working native QRTR/FastRPC transport but no advertised DIAG or SSC service.
A GLINK RPMSG control parent exists; its native control driver is unavailable in
our accepted config. The temporary module can provide the standard endpoint API
without replacing the known-good kernel or any of its 181 module files.

The build validates exact config, ELF notes, Linux pin, upstream source bytes,
provider symbol table and all imported CRCs. Provider inputs are hashed again
following compilation. Never force-load a mismatched module. Loading this
external diagnostic module would add the ordinary out-of-tree taint; record it
in the future registration instead of calling the runtime unchanged production.

The separately tested `userspace/sensors/rpmsg_diagnostic.py` only permits DIAG,
uses the standard endpoint ioctl, opens the endpoint to initiate GLINK OPEN,
reads at most one 64KiB packet with a one-second poll, and destroys through the
same FD. It never opens DIAG_CNTL/DIAG_CMD, sends masks or writes payloads. A
kernel open can wait 5s+5s; an external 15s deadline and owned ledger are mandatory.
Failure leaves explicit required-reboot state; do not reopen an endpoint to
clean it up, retry it, or unload the control driver while endpoints are live.
Restore the baseline by the registered reboot/rollback sequence.

Not installed, not hardware-tested, not a sensor or log-decoder acceptance.
Complete the Test384 registration/runner and artifact/transport gates before
physical use. Retain the exact Test370 rollback and normal GNOME endpoint.
