# SM5440 native measurement and shutdown supervisor

This composes the actual converter, actuator and watchdog C operations into the
missing register-side active monitoring path. It remains offline/unlinked,
default disabled, with no probe, worker, userspace interface, TCPM request or
device deployment. Test317 and its compulsory rollback stay frozen.

The caller owns one serialized SM5440 worker, exclusive converter/latch access,
native source/facts snapshots and cancellation generation. Start is admitted
only after the checked actuator has recorded successful ON, prepared settings,
owned watchdog, switching inhibit/lease and the same producer epochs. Every
advance checks native BOOTTIME, real facts, actual ONLINE2 PPS mode, matching
APDO and exact mirrored target budget. A PD_PPS label on fixed ONLINE1 is not
PPS. Target stays within the existing 8.2–10.5 V/1.0–1.8 A initial caps.

The asynchronous converter supplies a new one-shot with original-control
cleanup. On completion the supervisor compares exact microvolts/microamps,
not rounded milliamp values: VBUS within 100 mV of target and <=10.5 V, VBAT
3.5..<4.3 V, IBUS <=approved target and die <42 C. Core eligibility retains
the real pack/SOC/thermal/qualified-OCP gates. Verified operating settings and
protection witnesses must still match before a real watchdog service write.
All stages and service must remain within the unchanged 100 ms monitoring gap;
timestamp is the native measurement start, not a cache lookup. A healthy call
does not change mode, current, PDO or switching policy.

First error, stale facts/ADC, loss of generation, source change, suspend cancel,
new hardware fault, exact IBUS overrun or failed watchdog service permanently
stops this supervisor. Execute actuator OFF/readback/owned cleanup first, then
cancel/clean the converter if still in flight. Preserve first operation error,
actuator cleanup error and converter cleanup error separately. Never retry ON,
uncertain OFF or cleanup from a later outer fallback call. If OFF is unknown,
the actuator keeps watchdog/settings ownership; no clean hardware shutdown is
reported. `hardware_quiesced` means checked local pump/converter cleanup only;
it is never permission to request fixed PD or release the SM5714 inhibit. Those
still require same-source native TCPM completion and new physical fixed VBUS.

This implements software current comparison and the associated actual OFF
operation, not a hardware current-cutoff certificate. `software_ocp_verified`
remains mandatory and has no qualified live producer. Mock test facts setting
it true cannot enable an installed kernel. AVG32's real delivery/current
calibration and actual cutoff latency remain physical prerequisites. No
deadline is extended, no F2/FE protection-disable init is imported and no
SM5714 thermal/4.44 V or fixed-PD current ceiling changes.

The existing transaction core remains the owner of entry, refresh/retarget,
PPS keepalive, fallback and PM policy. This helper supplies the actual monitor
side of that adapter; initial ON verification, refresh pause/resume actuator
lifecycle, device facts integration and PM worker scheduling are not claimed
complete by an unlinked helper. Terminal shutdown is not a refresh pause.
