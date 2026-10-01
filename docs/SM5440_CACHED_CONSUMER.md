# SM5440 coherent passive consumer, Test266

Fedora X710 ab123e7d sm5440_get_adc()/wait_vbus_settled() use SM5440 physical
telemetry rather than treating requested TCPM voltage as measured VBUS. Samsung
X710 sm5440_convert_adc()/converter controls remain the hardware reference.
This increment makes the already completed passive sample available as one
coherent in-kernel copy. It does not port active ADC/pump/PPS policy wholesale.

`sm5440_passive_read_cached()` in sm5440-hw.h returns observed_ms (BOOTTIME),
VBUS/VBAT in microvolts, IBUS in microamps, die temperature in deci°C and online.
No independently verified pump IBAT channel is invented. Physical raw decoding
and cached values remain identical to the accepted passive driver. Offline
means online=false, not fabricated connected power at the ADC4.096V floor.

## Acquisition time and refusal

The worker records acquired_ms immediately before the existing converter-enable
operation, after disabling/consuming old ready and selecting channels. This is
the oldest plausible timestamp for this conversion, not exact calibrated ADC
sample time. Converter wait and register-transfer time count against freshness.
Publication, property/debugfs lookup and API read never move that timestamp.
The standard passive diagnostic/property2500ms budget remains unchanged.

The consumer rejects zero/future or age>100ms, no completed/valid sample,
startup awaiting confirmation, fault/I2C error, stopped provider, active mode
or absent/unpublished provider. Failure clears the destination and returns an
error, not a plausible successful zero measurement. No I2C, ADC start, wait,
work scheduling or register write occurs on consumer read. It is a copied
snapshot at the read time; a future caller must recheck time/PM/epoch before
acting. It does not guarantee the calling thread resumes before100ms.

The1s worker cadence and up-to300ms conversion wait remain unchanged. Most
reads between conversions may return ESTALE. This is deliberate refusal, not
an on-demand acquisition API or a promise of100ms physical current cutoff.
It cannot by itself satisfy an active direct-charge monitoring cadence.
Independent voltage/nonzero-current calibration and active OCP remain missing.

## Lifetime and locks

One provider publishes after successful probe setup. A second publication is
rejected; an unrelated cleanup cannot remove the original provider. Readers
hold companion_lock -> io_lock only while checking/copying. A busy worker
I2C lock is rejected via mutex_trylock/EBUSY without waiting under the registry. No provider pointer
or mutable storage escapes. Poll, PM and debugfs never take companion_lock;
there is no inverse ordering or lock-held converter/PD wait in the new API.

The last devm action unpublishes under companion_lock before debugfs/drain/stop
and driver-memory cleanup. A running copy completes before unpublish obtains
the lock; a later read sees ENODEV. Existing suspend/quiesce sets stopped and
invalidates data. Resume still requires OFF/no fault and fresh polling. This
protects this copy-only API, not the future multi-device live adapter's lifetime.

## Scope and verification

Only sm5440-direct.c/hw.h and host tests change. Hardware sample operations,
startup confirmation, protection values, polling cadence, switching charging,
fixed5V1800/9V1500mA,4440mV/thermal, config fragments/DTS and USB remain intact.
No PPS/ON setter, live policy adapter, arbitrary-register API or userspace
control is added. Exporting a read-only symbol is not an activation interface.

Host tests compile the actual publication/copy functions with no I2C functions
available: coherent units/acquisition stamp, age boundaries, failures clearing
old output, mode/PM/fault gates, multiple-provider cleanup and lock ordering.
Actual converter tests prove the recorded time precedes its wait/publication.
An isolated passive build must match Test263 config/DTB and pair181 modules.
ActiveStage3 remains NOT READY; no physical test or deployment is authorized.
