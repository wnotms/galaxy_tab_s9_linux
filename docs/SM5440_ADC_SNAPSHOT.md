# SM5440 passive ADC evidence, Test263 offline design

Start: test HEAD1e1f0840, installed Test260 passive candidate. Test262 fixed9V
charging phase and final endpoints passed with a retained unplug evidence gap.
This work only prepares an offline candidate. No device commands or deployment,
PPS/APDO request, Q4/handoff, pump enable or current/protection change.

## Why this precedes active integration

Test260 startup SM5440 VBAT3.6005V differs from the contemporaneous SM5714 gauge.
Existing power_supply exposes VBUS/current/die only; the retained first fault
has raw ADC, but later successful samples lose those raw values in user-visible
telemetry. Neither independently calibrated VBUS nor active OCP/PM coordination
has been accepted. Exposing evidence is a prerequisite for investigating that
difference, not a correction factor, calibration proof or permission for ON.

## Minimal implementation

Add optional root-readable, read-only debugfs `sm5440-<devname>/snapshot` through
normal debugfs_create_file and seq_file. One short io_lock section copies the
current conversion, retained startup conversion, flags and jiffies. Formatting
runs after unlock. A read performs **zero I2C operations**, never consumes INT,
starts ADC, changes policy or samples on demand. The existing single worker,
conversion/fault/startup/PM behavior and every register write remain unchanged.

Output labels present/valid/fresh, stopped/fault/startup pending, capture/stamp
jiffies and age_ms. Fresh means cached passive evidence within the existing
2500ms publication budget, healthy and not pending/stopped. It is explicitly
NOT a100ms active transaction measurement or an independently calibrated sample.
Keep raw INT/STATUS/ADC, converter completion, modes and protection readback
alongside VBUS/VBAT/IBUS/die with explicit uV/uA/deciC units. Retain the original
startup snapshot even after confirmation; its presence does not mark it current.
Missing/failed/stale samples remain explicitly unavailable, never plausible
zero-value defaults. Raw cached faults are still printable for investigation.

Use normal debugfs proxy lifetime protection in pinned Linux7.2-rc3
fs/debugfs/file.c. Register devm cleanup after the existing stop action so files
are removed/drained before worker/power_supply/regmap memory teardown. Debugfs
absence or allocation failure removes any partial directory and does not
change passive charging hardware behavior. No writable file or activation API.

## Sources and preserved policy

[VENDOR] /home/ms/Samsung/kernel_platform/msm-kernel/drivers/battery/charger/
sm5440_charger/sm5440_charger.c: sm5440_convert_adc(), ADC control helpers;
13-bit VBUS/VBAT/IBUS and die decoding already shared in sm5440-hw.h.
[VENDOR] IRQ read-to-clear latch semantics: additional diagnostic I2C reads
would corrupt first-event provenance, so only already captured memory is shown.
[MAINLINE] seq_file/debugfs and cached-copy lifetime rules from the pinned tree.
[MEASURED] Test260/Test262 are bounded passive/fixed observations, not calibration.
[BRINGUP_LIMIT] fixed5V<=1.8A /9V<=1.5A, ordinary float4440mV/thermal policy
remain unchanged. No SM5440 protection recipe, PPS or live policy adapter.

## Qualification and next physical plan

Host-execute actual C snapshot-copy/format functions with mocked seq/mutex/time:
healthy/raw preservation, pending, fault, no sample, stale, exact freshness bound,
stop/suspend, long age, copied retained startup, and formatting outside lock.
Assert no register I/O or unsafe write enters these functions; retain all older
driver fault tests. One isolated passive ARM64 Image/DTB/modules build, W=1/
sparse on the changed driver, full host run once; exact config/DTB diff versus
accepted Test260 must be empty. Preserve85 Docker gates/DCC/96 protected files
and frozen outputs. No unrelated schema cleanup for byte-identical DTB.

Future separately authorized physical acceptance: existing rescue/rollback,
one passive startup, capture snapshot plus gauge/TCPM with source timestamps on
PC5V and approved fixed9V; compare repeatability/raw decoding and acquisition
age. An inline meter or other independent reference is still needed for absolute
VBUS validation. Stop on any new fault, unsafe/unavailable measurement or rescue
loss. No deliberate heating, overvoltage, PPS or pump run. A snapshot candidate
must be flashed only after new authorization; this task ends offline.
