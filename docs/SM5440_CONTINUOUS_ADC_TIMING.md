# OFF continuous ADC timing diagnostic

Test317's one-shot software enable-to-read brackets were128–130ms. They include
I2C/polling/scheduling; they do not identify the intrinsic converter period or
qualify the active100ms ADC/OCP gate. This new isolated experiment records
continuous READY observations, rather than changing that gate or replaying the
same one-shot/ENHIZ experiment.

## Hardware provenance and scope

[VENDOR] X710 `sm5440_set_adc_mode(CONTINUOUS)` disables ADC, waits50ms, selects
RATE1 and enables. `sm5440_init_reg_param()` sets AVG32 at ADCCNTL1[3] and
channels0xdf at ADCCNTL2. [FEDORA] ab123e7d `sm5440_direct.c` uses
AVG32|CONTINUOUS|ENABLE. Only these converter settings are borrowed; none of
those implementations' protection/current/pump/PPS initialization is copied.
ADCCNTL1 is0x1c, ADCCNTL2 is0x1d, READY is read-to-clear INT4[0].

`sm5440-timing.c` performs actual regmap reads/writes in the separately selected
`sm5440-adc-timing` built-in profile. Defaults, previous passive/condition
profiles and the frozen single-shot converter remain unchanged. Kconfig
excludes charging policy and the older ENHIZ condition profile. No charging
companion is published; there is no writable trigger, PPS Request, lease/Q4,
current/protection/ENHIZ programming, TCPM change or pump-ON path. A fault gets
one existing checked pump-OFF attempt before converter cleanup; its outcome
and the original failure are retained separately.

## Admission and lifecycle

The existing passive startup/fault/confirmation gate must pass first. Native
fixed-source and actual pack observations are bracketed by source epochs.
Require fixed5/9V, original1.8/1.5A caps, ONLINE1, charge requested, no PPS or
owned switching lease, real battery-present/healthy/thermal state, SOC5–<80%,
VBAT3.5–<4.3V and pack20–<38°C. Only pre-write native EAGAIN/EBUSY readiness
permits up to20 reads with100ms unlocked waits; retain the first error/count.
Other errors stop immediately. These are readiness attempts, not successful
sampling rounds. No default/cache temperature is substituted.

One existing20ms one-shot rearm leaves the previous converter disabled; the
new helper then verifies that state and applies its own vendor50ms continuous
rearm. An enabled/unknown converter is not adopted. Each step requires pump
OFF, fixed-source VBUSPOK, no live or consumed fault and exact converter-control
readback. Old READY is consumed before enable. New READY latches, both live
status reads and11 raw ADC bytes are retained. Physical decoded VBUS must be
4.5–9.5V, VBAT3.5–<4.44V, IBUS exactlyzero and die temperature<42°C.

[BRINGUP_LIMIT] Up to eight READY events, each within500ms and complete timing
transaction including converter cleanup within2000ms; maximum450 steps. These
are diagnostic limits only. No hardware hard-real-time deadline is asserted.
All control bits/channels are saved, one ADC-disable/readback/restore attempt
is made even after an uncertain enable write, and restoration must match.
First error and cleanup error are separate; repeat begin/finish refuses.
PM/removal stops and synchronously drains the existing worker. There is no
wait under io_lock or supplier call under that lock. After an attempted timing
diagnostic, resume does not arm it again. Source/pack epochs and native fresh
facts are checked again after converter cleanup; a mismatch refuses the result.

## Interpretation and next physical scope

Native BOOTTIME brackets describe software operations, not inaccessible chip
conversion instants. `cleared_ms` is the oldest bound from the previous latch
read call (or first enable), not a manufactured exact clear instant. READY
read begin/end, ADC read begin/end, raw data and partial failed slot remain in
cached debugfs. Reads of that file never touch registers or trigger sampling.
Continuous ADC data may update during a bulk read: coherent multi-channel
sampling, physical calibration, current response/cutoff, continuous ON-mode
protection and software OCP are **not** certified by this diagnostic.

A separately registered physical round should use one PC-USB fixed5V boot,
accepted311 paired rollback, essential live identity/rescue/pack gates, this
one bounded diagnostic, complete journal at boundaries and unconditional
accepted311 restoration. No cable dance or extra9V/PPS/ON round is needed to
answer READY cadence. Failure stops; do not flash the same failed profile again.
Fresh source traces/register checks, independent current/cutoff calibration and
actual ON/PPS/fallback/PM qualification remain subsequent work. Overall charging
port remains NOT READY; this profile never grants higher-power charging.
