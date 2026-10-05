# Why the next action changes

[MEASURED] The fixed5V pumpOFF continuous profile received no READY within the
registered500ms wait. Saved controls/channels/physical mode/status and native
facts separate this from an unready source or a failed I2C operation. It does
not prove that continuous conversion never updates, or that its physical period
is500ms; no ADC buffer reads completed. Never infer a conversion timestamp from
a cached or unchanged value. Bit2 of ADCCNTL1 was preserved from0x0c: its meaning
is not established by these source snippets; do not guess or clear it as a fix.

[VENDOR] actual X710 sm5440_set_adc_mode at1053..1079 uses disable/50ms/RATE1/
enable; init_reg_param at454..468 sets AVG32 by bit3 masked update and0xdf channels.
This supports the register recipe; it does NOT promise a fresh ADCUPDATED pulse
for each continuous conversion while pumpOFF. Vendor direct manager's
DELAY_ADC_UPDATE=1100ms is policy scheduling, not a measured conversion/cutoff bound.

[FEDORA] pinned same-model implementation defines RATE1/AVG32 and hw_init
writes0x0b/0xdf. Its ADC pair readers at180..218 read data directly; the
pumpOFF physical-settle routine at421..446 waits20ms then50ms intervals and
compares VBUS, without consuming or requiring per-sample READY. Thus borrowing
the recipe and adding a per-sample READY gate are distinct policy choices.
Neither source establishes coherent bulk channels or a100ms current/cutoff
certificate. Copying the entire Fedora initialization would also change
protection/watchdog/current/ENHIZ fields and is outside this experiment.

Decision: retire this unsuccessful unchanged OFF READY profile from physical
use. Preserve its result and restored fixed path. Do not increase waits,
activate the pump to make READY appear, restamp raw reads, copy disabled-OCP init,
or weaken the active100ms guard. Subsequent acquisition design must separate
one-shot completion semantics, continuous data validity and actual active current
protection; vendor/Fedora are hardware references, not proof of new acceptance.

The active worker/adapter, independently qualified current/cutoff, actual PPS
refresh/fallback and PM integration remain unfinished. This result changes the
next acquisition design; it does not replace the full charging-port objective.
