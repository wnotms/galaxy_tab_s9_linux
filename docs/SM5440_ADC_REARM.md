# SM5440 vendor single-shot rearm

Test295 captured three near-time SM5440/SM5714 pairs differing244–355mV.
Physical cause remains unknown; neither sensor is an external calibration.
Samsung sm5440_charger.c:sm5440_set_adc_mode(ONESHOT), lines1058–1065,
disables ADC, sleeps20ms, selects one-shot, then enables it. Current passive
sample_once changes disable/rate/channel/enable immediately. This is a concrete
source-backed sequence omission, not proof of the observed voltage cause.

Add a checked worker preamble: confirm modeOFF, disable ADC enable bit, unlock,
wait20ms, check cancellation; then run existing sample_once, which independently
checks OFF, preserves all read-to-clear faults, selects one-shot and starts the
new conversion. The repeated disable in sample_once is idempotent; no ENABLE
occurs in the preamble. No mutex across sleep. If I/O/mode fails, no wait/rearm;
worker latches/refuses as before. PM marks stopped and drains before verifiedOFF.

Do not change the converter function, ADC math/AVG32/channel mask, startup
threshold/5sdeadline/fault handling, legacy100ms or separate500ms validity.
Timestamp still precedes actual enable, never the preamble/cache read. Requests
include the preamble in their existing completion deadlines; no age waiver.
No reset, active initialization, continuous mode, PPS/pumpON/current increase.
Frozen fixed-PD unaffected (its SM5440 node is disabled).

Qualify changed SM5440 tests/build and register Test296 separately. One passive
PC-USB candidate boot; compare the three startup pairs to295 without declaring
causality from one boot. Device ADB/services/roles/NCM configuration plus exact
identity/kernel/safety are required. NCM host TCP is recorded once, but a host-only
timeout with responsive device is not charging admission and does not prolong
this OFF-only diagnostic. No cable changes or PPS.15sdeviceendpoint then exact263
rollback. New device/kernel/thermal/I2C fault stops; prior startup refusal stays
latched. No further same-profile retries if the rearm hypothesis fails.
