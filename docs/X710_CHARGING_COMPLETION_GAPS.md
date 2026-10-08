# X710 charging completion gaps — 2026-10-08

The requested end state is a working mainline-first X710 wired charging port,
including vendor-derived SM5714/SM5440 safety and charging policy, retaining
known-good fixed5V/9V fallback. A bounded PPS run alone does not complete it.
This document records current evidence and separates code from acceptance;
AGENT.md and each frozen registration remain authoritative for deployment.
No device operation or change of a charging limit is authorized here.

| Requirement | Current authoritative evidence | Work still required |
| --- | --- | --- |
| Ordinary BC1.2/fixed charging,4.44V and thermal failure handling | Test331 paired baseline; kernel/drivers/sm5714-battery.c | Preserve this baseline through every further candidate; do not increase fixed5V1.8A/9V1.5A limits |
| TCPM PPS transport and source lifecycle | kernel/drivers/sm5714_usbpd.c and sm5714-stage2.h; source-bound lease APIs used by sm5440-fedora.c | Retain epoch/lease invalidation, no stale source reuse, stock TCPM protocol ownership |
| Fedora-derived pump/refresh/fallback | Test345 short attempt and Test347 native300s acceptance, full journals and exact331 restoration | Test348 independently registered1200s hardware validation is pending; no automatic replay or longer runtime follows from existing tests |
| Twenty-minute implementation | source0b731b4a; reference/charging/test347-twenty-minute-followup/summary.json; Test348 PACKAGE/INPUTS/offline-summary | Compiled and host-tested, not hardware-tested. New owner scope, fresh identity/rescue/telemetry and candidate-bound C1 reply precede the sole attempt |
| Higher-current charging | Current SM5440_PROGRAM_IBUS_MA=1700 and MAX_PPS_MA=1800; raw-current checking in sm5440_once_measure | No2/2.25/2.5/3A acceptance. After preceding duration acceptance, independently qualify each hardware setting, raw stop, source/APDO and protection envelope; changing one constant cannot establish capability |
| ADC/current accuracy and cutoff | Test347 uncalibrated rawIBUS max1.781875A; sm5440_once_settings programming witness; 100ms worker target/500ms gap stop | Independent accuracy/protection evidence absent. CNTL2=0xf2 needs software OCP; a register readback is not hardware OCP validation. Do not deliberately provoke OVP/OCP or claim a hard-realtime guarantee |
| Vendor CC/CV/termination/recharge | Vendor audit and read-only Samsung sm5440_direct_charger.c; current sm5440_pps_target_mv/renegotiate_pps use conservative operating points | Full vendor CC/CV adjustment, termination/recharge and their transitions remain incomplete. Separate bounded acceptance from production charge completion; preserve SM5714 FULL behavior and fixed ceilings |
| Thermal policy and sensors | Current mandatory pack IIO, NORMAL/REDUCED/STOP and direct bring-up gates; vendor audit temperature table | Vendor mixed-sensor/LRP optimizations lack accepted sensor mapping. Retain fail-closed behavior; do not translate aggregate Samsung zone currents into switching limits |
| Watchdog/fault/PM behavior | sm5440_direct_once_work services WDT; restore_switching preserves primary/cleanup failures and leaves WDT armed when OFF unproven; PM/unbind paths and affected C tests | Software paths are implemented/tested; complete hardware fault/PM production acceptance remains separate. SM5714 vendor watchdog maintenance and reset/termination strategy are not automatically ported by PPS acceptance |
| Production policy | Driver defaultsOFF; Test348 is exclusive one-shot; Test347 consumed its grant | No always-on production release or vendor-equivalent45W claim. Production mode requires the missing policy and applicable acceptance; keep paired331 rescue |

Continue with Test348 rather than redesigning the working ADC path. The active
SM5440 code already derives from the same-model Fedora source; keep its useful
hardware sequence while preserving this repository's source ownership, thermal,
physical-measurement and fixed-return gates. Samsung remains the hardware/board
policy reference and Linux TCPM remains protocol owner. Do not import unrelated
Android framework, OTG/dock/DP or bypass features to close these wired gaps.

Twenty-minute acceptance, if later clean, would close only that duration row.
It would not prove higher current, measurement calibration, all historical CPU
faults, long-term reliability, full CC/CV policy or the complete port objective.
The next candidate must address the next concrete missing requirement rather
than relabeling the existing bounded candidate as production-ready.

Validation for this documentation change: tests executed:false, build
executed:false. Reviewed current source functions, Test347 physical-summary,
Test348 registration/PACKAGE/offline-summary and qualified0b731 results; reuse
those qualifications. Frozen inputs and device state were not modified.
