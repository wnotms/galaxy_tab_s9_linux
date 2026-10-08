# Test347 — five-minute PPS result

**PASS for the registered single 300000ms conservative attempt.** Exact Test331
boot/all five partitions and original 181 module files were restored afterward.
The device remains in **TWRP**, as explicitly requested by the owner. No restored
Debian boot or fresh restored-runtime acceptance was executed; offline restoration
is proved by partition/module readback and final TWRP identity.

## Observed behavior

- Candidate boot `19fbf94136a64f7cb73e9e263da8549c`, uniquely attributed from
  Test331 `a96de8c0383b4f78b976ecc6db3ab793`.
- Owner-confirmed C1 launch used guardian PID 1762 exactly once. Human cable
  waiting did not consume the active window. No restart or repeated activation.
- Native 300000ms profile completed: 62 PPS refreshes, 63 parked-zero-current
  proofs, fixed9 return and no-restart proof. 508 guardian samples, 417 mode4
  samples. The native start-to-completion record spans 300.434389s including
  completion work; this is not a claim of continuous pump-on time or hard-real-time
  cutoff. Pump parking for PPS refresh remains part of the registered behavior.
- Initial PPS target 9040mV/1800mA; hardware input setting 1700mA. Raw input
  current max **1.781875A**, physical ADC VBUS max **9.284V**, pack VBAT max
  **4.168V**, battery temperature max **32.7°C**, pump die max **48.5°C**.
- ADC-derived input power across mode4 samples: unweighted sample mean
  **12.218W**, peak **15.796W**. ADC is uncalibrated; samples include transitions
  around parked refreshes. These are not wall-power, sustained-power, efficiency
  or 45W measurements. Source APDO capability is separate from actual draw.
- Pump-OFF/unbound and fixed9 lease restoration passed. Ordinary switching
  charging then passed **31.022s**: fixed9/1.5A cap, positive battery current;
  endpoint 71%, 32.6°C, +2.069A.
- Owner unplug followed by **15.606s** discharge passed on the same boot:
  USB/TCPM offline, endpoint 71%, 32.0°C, −0.646A, pump OFF/unbound.
- PC return passed once: ADB, device-side NCM, Sink/Device, no Code43,
  same boot, pump OFF/unbound. Full-journal classification found no new
  kernel fault; raw guardian, journals and systemd evidence are retained.

The first PC preparation rejection at SOC71 remains preserved. Natural discharge
then reached68, and a fresh successful preflight admitted installation. Neither
preparation observation is counted as an additional charging attempt.

## Restoration and endpoint

The owner instruction “已接回电脑，本轮完成后保持在twrp” superseded only the
registered final Debian reboot. `finish-in-twrp.py` reused the qualified recovery,
transfer, paired-module restore, boot-write and all-five verification helpers.
Test331 boot SHA-256 is
`025ebea4282524751bace461ce96beef85c01ea65a4d2b117106c7cdfe0ab815`.
Original181 modules verified, Debian unmounted, final TWRP3.7.1_12-gts9wifi /
recovery Linux5.15.94 identity verified. rollback_required=false. This does not
claim fresh runtime validation of the restored Debian image.

The completed seven-file Windows transfer stage was hash-verified and deleted
(248697284 bytes); qualified WSL candidate and current Test331 rollback artifacts
remain. ADB tools were untouched. See stage-retirement.json for exact manifest.

## Scope and validation

No new kernel/config/DTS/USB/adbd/charging-policy change accompanied this test.
Fixed5V<=1.8A / fixed9V<=1.5A, float4.44V, thermal/suspend rules and DCC absence
remain qualified by the unchanged candidate/config and runtime admission evidence.
The independently requested ACPI reporting-only client remains separate.

Host tests executed:false; kernel build executed:false for this evidence-only
stage. Reuse qualified60 host tests,79 actual-C tests and ARM64/W=1/sparse results.
The one-time TWRP completion helper passed Python syntax and actual recovery
integration/hash gates; no broad regression or build was repeated. No Actions/CI.

This bounded result supports designing the next independent20-minute/1200s
candidate. Test347's grant is consumed, its guardian must not restart, and its
300s profile must not be rebound to approximate20min. No higher-current,20min,
independent current/ADC calibration, protection-limit, long-term reliability or
vendor-equivalent charging acceptance follows. **Full charging port NOT_READY.**
