# Test348 — first raw-input range stop, Test331 restored

Verdict: **STOP_FIRST_NON_CLEAN**, one attempt, no retry. The registered
1200-second acceptance did **not** pass. Native protection stopped the pump
1196.692969 seconds after its pump-start log (about 19 min 56.7 s).

The owner confirmed USB-C1 before the sole activation. Frozen Test348 kernel,
config, DT and paired 181 modules were used; PPS request ceiling 1.8 A and
hardware input setpoint 1.7 A. Neither limit was changed during this attempt.
The same candidate boot `870edc39-33bc-4aa9-967d-dc07f7af8b4b` remained active.

## First failure and cleanup

Native raw IBUS reached **1,811,875 µA**, exceeding the registered
**1,800,000 µA** stop threshold by 11,875 µA (about 0.66%). At that stop:

- ADC VBUS 8.718 V; requested PPS target 8.960 V.
- ADC VBAT 4.0995 V; gauge VBAT 4.084 V and IBAT +2.359 A.
- Pack temperature 27.5°C; SM5440 die temperature 42.5°C.
- Status bytes `00/80/20/08`; the explicit range check returned -ERANGE.

Native stop reports `primary=-34 cleanup=0 lease=0 no_restart=1`.
Its fixed-return verification recorded physical VBUS 9.283 V, three settled
samples, raw IBUS zero and pump OFF. Guardian cleanup independently confirmed
pump OFF, driver unbound and TCPM fixed 9 V/1.5 A; cleanup error is null.
The 30-second ordinary-charge and 15-second discharge acceptance windows were
not executed after the first non-clean event. They are not silently counted
as passed. Owner connected PC immediately for the unconditional rollback.

The complete kernel journal has 2049 rows. The existing parser detects no
CPU stall/panic/Oops signatures; its two new suspect messages are the native
range rejection and resulting primary -34 stop. Known bounded startup
warnings remain labelled in `failed-boot-journal-classification.json`.
This is a current-range stop, not evidence of a CPU wedge.

## Bounded observation

1876 host samples, 1467 with active pump mode. Sample SOC increased 53→60%.
Active host sample maxima: pack 27.6°C, die 43.0°C, ADC VBAT 4.114 V, VBUS
8.903 V, raw IBUS 1.783750 A. The faster native monitor caught the higher
1.811875 A peak between host samples; the host maximum cannot override it.
ADC readings are uncalibrated. A 1.7 A register setpoint is not proof that
instantaneous current is bounded below 1.8 A. The log alone does not establish
whether the peak reflects control tolerance, a transient, ADC accuracy or
another cause. Do not relax the stop threshold or claim a current calibration.

PPS refreshes deliberately park/settle/rearm the pump. Brief zero-input and
negative gauge-current samples were preserved and reviewed with the refresh
journal; subsequent positive-current samples and rising SOC were observed.
This is a bounded test with refresh intervals, not 20 uninterrupted minutes
of pump ON, a calibrated power measurement or a general reliability proof.

## Restoration and owner endpoint update

Exact accepted Test331 boot plus all 181 original modules restored. All five
partition hashes verified, copied root unmounted, initial TWRP endpoint proved.
The owner then stated “后续不要求停在twrp，继续推进”. Registration
`39d16904` was pushed before one ordinary restored Debian reboot.

Restored boot `ba4d8404-8d38-4d9c-8ae2-0f39b68c03bf` is uniquely attributed.
Exact Test331 config/notes, all five partitions and 181 modules pass runtime
acceptance. DCC remains absent; ADB, device NCM and authenticated Wi-Fi SSH
(`10.175.236.100`) work; no Code43/new kernel fault. Wi-Fi obtained its lease
automatically in the same boot; the read-only network diagnosis changed no
settings. Battery at admission 61%, 32.1°C, 4.055 V, Good. No PPS/pump opt-in.
Final endpoint is **Debian**, superseding only the old TWRP endpoint promise.

## Evidence and next work

Full decoded guardian events and kernel journal remain directly readable.
Repetitive host monitor/telemetry logs and the duplicated raw transport response
are preserved in `execution-raw-logs.tar.gz`; every original path/byte hash was
verified before removing expanded copies. `EXECUTION_RAW_LOGS_SHA256.json`
indexes 1367 files. Per-stage summaries remain direct. `summary.json` is the
machine-readable stop/cleanup/restoration result.

For this results-only change, build/host tests: `executed: false`; frozen
qualified artifacts/source unchanged. Independent SSC offline helpers have
separate source/test results and did not change the charging candidate.
No Actions were started. Do not run Test348 again or increase charging limits
from this result. Next: source-based current-margin analysis and a separate
candidate; native SoCinfo kernel preparation may proceed after this restored
baseline, without installing/starting SSC or ADSP on the current tablet.
