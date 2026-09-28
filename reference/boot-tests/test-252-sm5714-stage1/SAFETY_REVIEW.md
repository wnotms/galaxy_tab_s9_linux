# Same-model and stock safety review

Compared against `/home/ms/Samsung/gts9wifi-fedora-linux` at
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`. The eight requested reference files
match that commit byte-for-byte. `validation/same-model-review.json` and the
full `same-model-driver.diff` record the comparison. This establishes source
provenance, not a guarantee that the candidate cannot damage hardware.

| Item | Evidence and candidate result |
| --- | --- |
| Addresses/adapter | Charger 0x49, dummy gauge 0x71 and MUIC 0x25 use the same DT-selected adapter, as in the same-model source and Samsung X710 board/MFD. No dynamic Linux bus number or I2C bus scan. |
| Gauge | SRAM window mutex and SOC/voltage/current/OCV conversions are identical to the pinned reference. No gauge recalibration, SRAM table writes, factory reset or SOC override. Current sign still requires physical verification. |
| Float | Samsung `drivers/battery/charger/sm5714_charger/sm5714_charger.c:195–220` and X710 r02 DTS line548 specify 4440mV. `CHGCNTL4=0x1a`, mask0x3f, encoded value0x2d; upper protection bits retained. Probe and every charge reconfiguration program and read back that value. Missing/wrong design data prevents probe. A failed programming/readback leaves Q4 open. |
| Input/pack current | Same-model ordinary limits SDP500/500, CDP1500/1500, DCP1800/2100mA; stock input `(mA-100)/25` and pack109.375mA +15.625mA steps preserved. Only exact ordinary BC1.2 classes authorize higher limits; ambiguous/AFC/QC sources stay500mA. Input register mask0x7f now preserves bit7, matching stock's update mask. No 3A, PD budget or PPS path. |
| Q4/retained state | Stock `chg_set_enq4fet` line357 and same-model sequence reduce input to500mA before closing Q4 and restore a bounded classified limit afterward. Candidate opens Q4 before rebuilding limits, even if Android left CHARGING; any error attempts to open it again. Full/TOPOFF does not force charge, and disconnected VBUS reports Discharging before evaluating stale TOPOFF. |
| Pack thermistor | Existing PMK8550 ADC5 Gen3 channel0x144 provides processed IIO temperature in m°C, converted to tenths°C. Gen3 provider built-in and mandatory Kconfig dependency. No fuel-gauge die fallback. Missing/implausible sensor data inhibits charge. |
| Cold/warm/hot | Stock X710 policy has cold0°C, cool bands5/15/18°C, warm42°C and overheat50°C. Candidate conservatively stops below10°C, resumes a stopped cold pack at15°C, limits10–18°C and >=42°C to500mA, stops >=50°C and recovers hot stop only below46°C. No current/voltage is raised to overcome these bounds. Actual C helper boundary tests pass. |
| Protection/faults | Stock health checks STATUS1 bit2 VBUS OVP, and charging init recognizes STATUS2 bit7 WDT expiry. Candidate reports these and stops charge, preserving latched evidence. No OVP/OCP/thermal protection register or charger watchdog timer is disabled/reprogrammed. No reset/retry loop clears the fault. It does not reproduce Samsung's complete ageing/cable/thermal policy. |
| Poll/lifecycle | One-second thermal/charge polling; bad safety reads open Q4. Poll cancellation on suspend/unbind/shutdown also opens Q4 because unattended charging cannot rely on a paused thermal worker. Suspend functionality is not otherwise a test target. |
| Excluded paths | No SM5440, TCPC/TCPM callback, OTG boost, MUIC USB switch write, role change, fast-charge UI or bypass policy. DTS/USB gadget remain unchanged. |
| Capacity | Official SM-X710 specification:8400mAh typical,8160mAh rated minimum. Existing8160000µAh design metadata preserved. GPL board `0x2648` capacity conflict is recorded in the Stage0 plan and not used to alter the design value. |

Safety tests execute extracted **actual candidate C functions** with mocked I2C
transport: cold/warm/hot boundaries, float encoding, stock current limits,
retained register bits, missing temperature, OVP/WDT, FULL, and failure during
limit/float programming or float readback. They cannot model electrical faults,
chip behavior after an ambiguous transfer error, bad physical thermistor wiring
or full pack ageing policy. If opening Q4 itself fails, the driver logs it;
software cannot promise isolation through a failed bus. Physical temperature,
voltage, current direction and charge trend must be checked before acceptance.

No source review or host regression justifies the claim "cannot damage the
device." The review found no intended overvoltage/high-current/PPS enable or
protection bypass, and the first physical run remains explicitly bounded with
charger disconnect and verified Test249 recovery available. It has not run.
