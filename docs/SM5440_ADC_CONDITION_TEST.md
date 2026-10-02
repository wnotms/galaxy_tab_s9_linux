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
