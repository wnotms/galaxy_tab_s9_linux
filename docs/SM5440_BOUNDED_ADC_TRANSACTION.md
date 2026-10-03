# SM5440 bounded conversion transaction

This adds the actual register-side measurement operation missing from the
future direct-charge adapter. It is not integrated into Kbuild or any device
caller. Test317 inputs and installed kernel remain frozen while its compulsory
rollback is pending. ADC/OCP qualification is still missing; this helper cannot
make `software_ocp_verified` true.

Samsung X710 `sm5440_set_adc_mode(ONESHOT)` disables ADC, waits 20 ms, selects
one-shot and enables it. `init_reg_param()` sets AVG32 and channels 0xdf.
`sm5440_convert_adc()` supplies the scale/offset and explicitly gates ordinary
reads below CHECK_VBAT. The vendor also schedules its ADC worker after 200 ms;
that is **not** evidence that a conversion meets our 100 ms monitoring budget.
Fedora X710 ab123e7d uses continuous AVG32. We do not copy continuous sampling
and label its cached output fresh. Both sources are retained in the audit.

The transaction has begin/advance/cancel calls and no internal wait, worker or
mutex. The future caller serializes uncached regmap access against all other
ADC users, publishes a cancellation generation before draining work, and
schedules advancement without holding charger/TCPM locks. No IRQ handler may
independently consume these read-to-clear latches. A zero initialized request
is disabled and admits no I/O. Each object is used for only one conversion.

Begin checks generation, device ID, expected OFF/CHG mode, all live/latched
faults and idle ADC. It saves original converter controls, then disables ADC
with exact readback. Advance waits for the source-backed 20 ms interval without
sleeping; rechecks generation/mode/faults, consumes the completion latch again
after disable, sets channels and single-shot AVG32, and records native BOOTTIME
**before** actual enable. Subsequent advances preserve all four interrupt
latches and live status, require a newly observed ADC_UPDATED, fetch the entire
11-byte data block, and recheck mode, controls and generation. There is no
completion from a previous conversion, continuous cache restamp or special
inactive-REVBLK exception in this active measurement path.

All steps, including rearm, transfer and converter restoration, must finish
within the existing 100 ms software request budget. Each bus call can still
block below regmap; this is a refusal budget, not a hard realtime I2C/OCP
certificate. Native clock regression, cancellation, excessive polling, timeout,
malformed data, any fault or cleanup uncertainty returns no usable sample.
The caller must immediately invoke its checked pump OFF/fallback transaction on
an active measurement error; this converter helper neither turns the pump ON
nor makes an unsuccessful OFF operation appear successful.

Original enable must be zero. Cleanup disables ADC and verifies it before
restoring the original channel byte and owned rate/average fields. It never
restores an inherited enabled converter, resets the chip, clears a fault by
writing status, changes ENHIZ/protection/PDO/current or retries an uncertain
cleanup. Unowned control drift and both operation/cleanup errors remain visible.
Raw latch/status/ADC bytes, start/completion times and fault bitmap are retained
on refusal; `sample.valid` is published only after verified cleanup and final
generation/deadline checks. Reusing a terminal transaction performs no new I/O.

The physical sample preserves VBUS/VBAT in microvolts, IBUS's 625 uA LSB and die
temperature in deci-C. It also fills the existing transaction core's sample
(mV fields). Hardware running mode and measured current are separately recorded.
Fixed/PPS contract, APDO, real pack thermistor, independent gauge comparison,
OCP/current ceiling and thermal policy remain the caller/core's responsibility.
The helper is only a measurement transport operation, not a charging grant.

Qualification runs the actual C on a faulting regmap/native-clock mock and an
ARM64 W=1/sparse single object. No Image/module relink, device deployment, new
test number or physical acceptance is implied. If AVG32 cannot meet 100 ms on
hardware, refuse active charging and design a separately sourced sampling or
protection solution; do not expand 100 ms to the 500 ms OFF diagnostic window.
