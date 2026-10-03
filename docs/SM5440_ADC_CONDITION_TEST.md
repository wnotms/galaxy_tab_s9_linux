# Isolated OFF-mode ENHIZ / ADC comparison

Test304 found live CNTL6=0x89, including ENHIZ bit7. Samsung
`sm5440_set_ENHIZ()` sets bit7 when attached but charging OFF;
`sm5440_init_reg_param()` clears it with0x09 before direct-state startup.
Fedora ab123e7d also writes0x09 during active hardware initialization.
These are different operating conditions, not proof of a bug or ADC correction.

The dedicated `sm5440-adc-condition` profile selects a default-off Kconfig
option. It cannot include the PPS consumer. The fixed-PD/default and existing
passive profiles do not select this option. DTS is exactly the existing passive
overlay; there is no charger reset or import of the vendor active recipe.

One startup conversion compares the vendor ADC operating condition while the
pump remains OFF. Under io_lock, verify OFF, save CNTL6, disable/verify ADC,
mark restoration pending before attempting the bit7-only clear, then read back
the exact expected value. Run the unchanged20ms rearm and one-shot converter
without a mutex across their waits. Always disable/verify ADC and restore/read
back CNTL6 bit7, including on conversion/I2C/cancellation errors. Preserve all
other bits and the first error separately from restoration error. A failed
restoration stays pending and faults the driver; teardown makes one bounded
cleanup attempt after draining work. Failure cannot prove hardware OFF.

Record before/during/restored values with explicit read-validity flags. Keep
the original ADC/fault evidence and adjacent gauge comparison. The worker
does not reschedule; resume cannot execute a second condition experiment.
The diagnostic profile does not publish a companion, so cached/fresh/observe
APIs cannot issue a charging grant from experimental samples. Debugfs remains
0400 and observational; no writable knob, PPS operation or pump-ON exists.

The exact ADC conversion, average32/channel0xdf, register decoding,100ms fresh
guard,500ms diagnostic guard, startup thresholds and fault classification stay
unchanged. ENHIZ might affect passive topology: this is an isolated experiment,
not a production fix or an assertion that clearing it is always correct.
No charging current, protection threshold, SM5714/Q4, DCC, USB role, rootfs,
TCPM core or DTS/provider modification is part of this candidate.

Before physical use: execute real-C host tests for every I2C failure/cancellation
and cleanup, build the pinned ARM64 candidate, check exact config/DT/protected
files/modules, then register/push a new one-boot PC-USB comparison. Preserve
accepted Test299/Test300 rollback. First failure stops the scope; preserve
raw journal/paired ADC and restore the accepted installation. No PPS or charger
swap is needed. Physical results, calibration and active readiness remain
unproven until that separately registered test is executed.

## Test313 result and the next operating context

Test313 is terminal STOP with exact accepted311 restoration. CNTL6
89 ->09 ->89 was read back and cleanup completed. One OFF conversion gave
ADC3.7995V/gauge3.802V(delta2.5mV), but live STATUS3=0x22/REVBLK and
IBUS30.625mA remain actual refusal signals. Mode01/01 stayed OFF. No pre-clear
STATUS3 was captured, so causality is UNKNOWN. Do not turn close voltage readings
into a calibration/charging grant or classify live REVBLK as an old inactive
latch. Original snapshots/journal and source excerpts are in Test313.

[VENDOR] set_ENHIZ() sets bit7 for VBUS-present+charging-OFF. Normal ADC access is
refused below CHECK_VBAT except the factory/reverse context. init_reg_param()
clears ENHIZ inside a reset/initialization sequence; it also changes watchdog,
protection and ADC settings. [FEDORA ab123e7d] the active start path hands off
SM5714 at an existing fixed9V contract before reset/init/PPS. Neither sequence
is an isolated permission to clear ENHIZ on a PC5V sink. Do not copy protection
-disable/reset magic to make this experiment pass.

Next implementation must establish a complete pump-OFF preparation context,
not repeat the unchanged5V experiment. Use the existing mainline source-bound
fixed snapshot/lease primitives. Require the same live fixed9V attachment and
bounded pack/thermal state, checked switching handoff if the reviewed hardware
sequence requires it, actual fresh physical VBUS and pre-mutation live STATUS.
A logical9V budget alone is not physical proof. Capture original read-to-clear
latches without losing their provenance. Never clear/mask a live fault to gain
admission. Preserve all protections, only approved writes, exact cleanup and
fixed-path rollback. Keep generation checks across unlocked waits and the
existing lock order; no long negotiation/ADC wait under the charger mutex.

Whether9V/headroom or switching-path state resolves the fault remains an
unverified hypothesis. Any additional condition write needs a separately built,
host-qualified and registered scope. No PPS/pumpON/current raise, alternate
ADC math or wider fault/age acceptance follows from Test313. Actual active
protection/actuator work must remain a separate candidate and default-disabled
until its physical prerequisites pass. Ordinary accepted311 stays the fallback.
