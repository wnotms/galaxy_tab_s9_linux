# Test372 results — SSC discovery on accepted GMU kernel

Test372 was stopped after one bounded discovery attempt. The early ADSP
candidate boot itself passed: the accepted Test370 kernel/modules remained in
place, ADSP ran the authenticated `qcom/sm8550/adsp.mdt`, FastRPC appeared,
the native `qcom_pd_mapper` auxiliary driver was bound, and the kernel journal
had no new fault signature.

The RPC services were then started once with the qualified Fedora-derived
userspace packages. `ssccli --sensor accelerometer` was probed for 60 seconds
and repeatedly returned `SSC QMI Service not found`. The complete QRTR
inventory contained no SSC QMI service. This is a userspace dependency
failure, not evidence that the ADSP firmware or native mapper is defective.

The missing Fedora dependency was identified as the userspace `pd-mapper`
daemon and its Debian `libqrtr1` library. Test372 intentionally did not install
either, so no retry was made. `oemconfig.so` remained an unresolved lookup in
the sensors service log; it is not treated as the first cause because the QMI
service was absent before a sensor request could complete.

The candidate vendor_boot and all owned sensor assets/overlays were restored.
The device returned to the exact Test370 baseline (Test370 config and notes,
ADSP offline, GNOME/USB lifecycle active, ordinary SM5714 charging, DCC absent).
The rollback command experienced one collection timeout and wrote
`recovery-required.json`, but the subsequent offline capture and mutation ledger
confirm `rollback_required=false` and the exact baseline boot is running.

No kernel, DTS, module, USB, charging, PPS, SM5440, or DCC change was made.
The next registered scope is Test373, which adds only the Fedora-qualified
userspace mapper dependency and preserves this failed hypothesis as evidence.
