# Diagnostic-only fixed9V inactive startup confirmation

Purpose: Test324 stopped before native one-shot execution because its OFF 9.4V
initial REVBLK-latch sample failed the ordinary PC 4.5–5.5V classifier. Preserve
ordinary Test323 byte-for-byte predicates/preprocessed behavior; only
CONFIG_SM5440_ADC_ONESHOT_TEST may classify OFF fixed9V 8.5–9.5V initial context.
Both subsequent fresh confirmations must remain in the same voltage class,
retain unchanged controls, and have no new/live decoded fault. Existing
5-second deadline, OFF/READY/zero-IBUS/VBAT<4.3V/die<42°C gates remain intact.
The native 100ms converter is unchanged. No ENHIZ/protection/masks, charging
limits, thermal, TCPM, USB, DTS, rootfs, PPS or pump activation changes.

[VENDOR] REVBLK handling is contextual in Samsung sm5440_irq_thread/direct
state. [MEASURED] Test324 initial INT3=62, STATUS3=20, MODE01/01, 9.4V, IBUS0;
Test317 also saw inactive fixed9V latch followed by fresh clean confirmations,
although that different diagnostic scope stopped on source continuity and is
not new acceptance. [BRINGUP_LIMIT] 8.5–9.5V classification never permits PD above
fixed9V; logical source and pack safety admission remain required by the native
worker. This classifier grants only pump-OFF ADC observation, not ADC calibration
or charging authority. Build one candidate in reused cache, scoped actual-C
ordinary/diagnostic/ADC tests, exact config/DT/protected/pairing verification.
A separately pushed Test325 may execute one new registered boot; Test324 stays
stopped. Always restore exact accepted323 after diagnostic observation.
