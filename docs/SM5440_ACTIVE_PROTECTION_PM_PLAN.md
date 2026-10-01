# SM5440 protection and PM review after Test263

Test264 is offline. Test263 device acceptance is complete under the owner's
updated criterion; its host filename-collision STOP remains historical. The
installed passive kernel and fixed5V<=1.8A/fixed9V<=1.5A/4440mV/thermal/USB
behavior stay unchanged. This review does not authorize PPS or pump activation.
Source file identities are in Test264 sources.json; vendor/Fedora files are
unchanged from the Test256 audit where previously recorded. Fedora is the local
ab123e7d snapshot, not a claim about a newly checked remote revision.

## Protection findings

Vendor path below is `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/
battery/charger/sm5440_charger/sm5440_charger.c`.

| Evidence | Meaning | Mainline decision |
| --- | --- | --- |
| [VENDOR] sm5440_init_reg_param(), line454, CNTL2=0xf2 with disable-IBUSOCP/IBATOCP/THEM comment | This is not a recipe enabling ordinary hardware current cutoff | No active init copied; observed f2 is not an OCP acceptance certificate |
| [VENDOR] probe line1761, need_to_sw_ocp=1, explicit unsupported-HW-OCP comment | Current supervision is a required software policy | Preserve the unqualified software_ocp_verified gate as false for any future live adapter |
| [VENDOR] sm5440_check_sw_ocp()/ocp_check_work(), lines1225/1255 | Delayed1s work, up to three status checks with1s sleeps, error notification to vendor manager | A roughly4s path is not a proven worst-case cutoff; scheduler/I2C time can extend it |
| [VENDOR] ocp_check_work() | STATUS reads ignore return values; reg1/reg2 are uninitialized on unsuccessful reads | Never copy this fault decision; each unsuccessful read must invalidate evidence |
| [VENDOR] sm5440_dc_set_charging_config(), line1112 | +300mA margin (+600mA at minimum input), optional+50mV VBAT offset, unchecked setters | Regulation target and physical maximum are different; do not import margins or expand validated limits |
| [VENDOR] sm5440_set_charging_enable(), line1096 | Mode/WDT operations return values are ignored and function reports success | Future ON/OFF requires checked operations and readback; failed OFF cannot authorize a source-voltage change |
| [VENDOR] WDT helpers, lines306/315 | CNTL1 bits6:4 timer, bit7 enable; active init uses30s | Watchdog is a last-resort mechanism, not100ms OCP or proof that bus failure stops current safely |
| [FEDORA] hw_init()/restore_switching() | Same f2/fe init; reset, active converter, WDT and switching fallback | Do not import complete init; fallback ignoring OFF/PPS-exit failure cannot satisfy our transaction contract |
| [MEASURED] Test263 snapshots | OFF/IBUS0, unchanged f2/e7/37/fe, valid cached raw decoding under PC/fixed9V | Qualifies passive observation only; no nonzero IBUS accuracy, OCP, ON or WDT physical acceptance |

The distinction matters: the verified50mA/code IBUS register is a regulation
setting. Neither that encoding, source advertised current nor a passing mock
proves hardware overshoot/cutoff behavior. No speculative CNTL2/PRTNCNTL bit
recipe or passive watchdog write is introduced.

## ADC evidence and what it does not establish

[MEASURED] PC paired SM5440-minus-gauge VBAT was-87.5..-70.5mV; fixed9V pairs
were-6.5..+3.0mV. The difference changes with the observation condition; do not
apply a constant correction. Gauge acquisition age and wiring-node equivalence
are not independently established. ADC raw decoding matches the vendor formula,
but that is distinct from independently measured voltage accuracy.

[MEASURED] Passive snapshot ages reached1032ms at the original final PC endpoint;
the passive freshness allowance is2500ms. [BRINGUP_LIMIT] The unwired active
core requires ADC<=100ms/facts<=500ms. A cached debugfs read cannot be restamped
to satisfy those gates. IBUS0 tests do not establish the nonzero current scale.
An active adapter needs a separate bounded fresh-conversion API, genuine
acquisition timestamps, independently checked current/voltage and protection
response. These remain unimplemented/unqualified.

## PM and lifetime findings

[VENDOR] sm5440_charger_suspend()/resume(), lines1884/1897, disable/enable IRQ
and wake handling. They do not explicitly drain direct workers, verify OFF or
exit PPS there. The active vendor path holds a wake source; Android/vendor
coordination is not a reusable mainline PM implementation.

[FEDORA] sm5440_pm_notify() cancels its worker before suspend, calls pump-OFF
and fixed switching restore while active, then reschedules after suspend. This
supports the ordering concept, but a NOTIFY_DONE return and unchecked restore
do not establish failure propagation or safe fallback after unsuccessful I2C.

[MAINLINE] Current passive sm5440_quiesce() sets stopped, drains work **before**
taking io_lock, invalidates cached data, verifies modeOFF, and disables ADC.
Suspend returns errors. Resume requires OFF and no fault before restarting.
This is retained, not proof of a future PPS consumer/device-link PM ordering.

The future live implementation must first specify:

1. A single transaction owner; cancellation advances its generation and blocks
   further requests. No core/charger mutex held during drain/PD waits.
2. Worker drain while TCPC and I2C suppliers are still usable, followed by
   verified pumpOFF, PPS exit, fresh fixed contract/physical voltage, then
   release of switching inhibit. An unknown OFF state keeps both paths inhibited.
3. PM failure propagation and abort cleanup for every supplier/consumer order;
   not a successful suspend with unknown pump state. Device links/notifier
   choices must be reviewed against the pinned kernel before implementation.
4. Resume reacquires fresh fixed/source/thermal facts; no old PPS grant or
   cached active state survives. Unbind/shutdown must use the same checked exit.

## Next work and acceptance boundary

| Step | Status after this review | Required next evidence |
| --- | --- | --- |
| Passive fixed path | Test263 device accepted | Reuse unchanged baseline; no repeat physical window solely for host defect |
| Future completion collection | New isolated child-directory helper, host-tested separately | Use capture_completion(endpoint / 'device-completion', ...) in new runners; do not edit sealed historical runner |
| ADC calibration/current response | Unqualified | Independent reference and bounded fresh acquisition; no intentional overvoltage/heating/overcurrent |
| Active protection recipe | Unqualified | Verified register semantics plus actual current cutoff/failure model; no guessed enable bits |
| PM/live adapter | Design only | Supplier ordering, abort/timeout/epoch fault tests, then qualified offline candidate |
| PPS pumpOFF / pumpON | Not executed/not authorized | Separate implementation/registration and explicit physical authorization after relevant gates |

ActiveStage3 remains NOT READY. No new kernel candidate is generated by Test264.
This is a concrete audit and tooling improvement, not a claim that documenting
the missing protections implements them. The next porting step is the bounded
fresh-acquisition/PM adapter design; active current control stays gated.
