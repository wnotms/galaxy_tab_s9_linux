# One-call SM5440 passive diagnostic observer

Test291 design, before implementation. Reuse Test290 provider8e890215 and its
sealed exact config/DT/181modules, not the old100ms observer276. Do not rebuild
or deploy the kernel as part of this offline test. Old observer/builder/tests
remain unchanged. Active/PPS/pump/current and physical timing acceptance stay off.

The new external module makes exactly one kernel `sm5440_passive_observe()` call
in an explicitly loaded, owned-lifetime kthread. No loop, retry, intervals,
module parameter, direct I2C, power_supply write, rootfs activation or conversion
on debugfs read. Save original provider result even on refusal; only a coherent
new OFF/IBUS0/online and safe-range diagnostic row is labelled diagnostic-valid.
Charge/legacy100ms/independent-calibration authorization fields always remain0.

Validate caller/provider request and return ordering, genuine acquisition start,
software completion, actual age and nonzero acquisition sequence. The separate
500ms diagnostic collection limit includes consumer return, so scheduler delay
outside provider can still refuse a delivery. Do not confuse diagnostic success
with100ms fresh success or realtime protection. A slow sample retains its age.
PM/dying/I2C/busy/invalid/stale/late/fault refusal stops the only call.

Copy results under result_lock only after API returns. Load creates a parked
thread, owns its task reference before wake, and exit uses kthread_stop_put with
no result lock across join. Failed debugfs/create never owns/stops a nonexistent
thread. This preserves the Test276 lifetime correction after fast autonomous exit.
Read-only0400debugfs is cached evidence, removed after join; no unsafe debugfs API.

An independent build helper verifies sealed290 image/config/DT/notes/modules and
source/ABI overlay against8e890215, plus exact new export from matching symvers.
Separate stage/output and strict build/source checks prevent pairing old images
or overwriting276observer. Compile module/W1/sparse, actual C request/failure/
lifecycle tests, and one full regression without rebuilding290kernel. The
result parser needs strict raw schema/time/units/boot/module binding before a
later physical registration. No device operation is performed by Test291.
