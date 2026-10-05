# OFF continuous raw ADC observation

Test318 stopped because continuous OFF operation produced no INT4 READY within
500ms. Its error, raw evidence and exact accepted311 rollback remain unchanged.
This corrects an observation assumption in a new default-off profile; it does
not rerun or relabel the failed READY experiment.

## Source evidence and design

[VENDOR] Samsung X710 `sm5440_set_adc_mode(CONTINUOUS)` disables ADC, waits
50ms, sets RATE1 and enables. `sm5440_init_reg_param()` supplies AVG32/channels
0xdf. `sm5440_convert_adc()` reads ADC registers directly without a per-read
READY wait. Its production state guard refuses low direct-charge states, with
an OFF-ADC warning; this does not certify fresh OFF conversion results.
Source: `kernel_platform/msm-kernel/drivers/battery/charger/sm5440_charger/`.

[FEDORA] Same-model snapshot ab123e7d, `kernel/files/sm5440_direct.c`, reads
continuous data directly. `sm5440_wait_vbus_settled()` waits20ms first, then50ms
between raw reads, while parked. These delays are software polling choices,
not a converter-period specification or current/cutoff calibration.

`sm5440-adc-raw` uses the real passive driver's startup/native source and pack
gates, existing I/O serialization and a shared converter transaction helper.
It reads eight raw samples, first at least20ms after enable/readback, subsequent
reads at least50ms after the previous completed ADC read. The complete diagnostic
remains bounded by2000ms/450steps. READY is recorded when present, never required
or invented. Raw and READY entry points cannot be mixed in one transaction.
The existing `sm5440-adc-timing` profile retains its READY requirements.

All mode, interrupt/live status, source/pack epoch, physical bounds and exact
ADC restoration checks remain. I2C error, mode/fault/source loss, PM cancellation,
bad time or bounds stop the single transaction. No wait or supplier read occurs
under io_lock. Resume does not repeat an attempted diagnostic. Preserve unknown
ADCCNTL1 bits; do not adopt Fedora's complete initialization recipe.

## Interpretation and boundaries

Debugfs labels the selected mode and explicitly reports
`conversion_freshness_proven=0`. ADC timestamps bracket software reads only.
Repeated data can be old buffering or steady voltage; changed data alone does
not prove calibrated/coherent channels. No companion API publishes these raw
observations and no active100ms freshness/OCP gate changes. No PPS, switching
lease/Q4, pump-ON, current/protection/ENHIZ or writable trigger is added.

No DTS, DWC3/gadget/adbd, TCPM, pack thermal/float or container feature change.
The new Kconfig profile excludes policy, condition and READY experiments.

## Next physical scope

After actual-C tests, normal ARM64 build and exact config/DT/protected-file/module
audit, independently register one PCfixed5 pump-OFF boot with accepted311 exact
paired rollback. Capture native eight raw reads, optional READY/latches, read
timing and exact cleanup once; stop on the first fault and restore baseline.
No failed Test318 replay, extra cable cycle,9V/PPS/ON or increased charging power.
Endpoint-only USB recovery is not a permanent Code43 fix.

This is a transport prerequisite for the full charging port. Native fresh ADC,
physical current/cutoff/OCP, active worker/adapter, real PPS, transactional
fallback and PM qualification remain required before higher-power acceptance.
