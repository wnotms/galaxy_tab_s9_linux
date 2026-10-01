# Test271 — unchanged-baseline passive startup diagnosis

Device passive diagnosis completed with a retained startup classification gap.
This is neither an original-runner CLEAN result nor high-power charging admission.

## Physical operation and attribution

Exactly one ordinary `systemctl reboot` of the installed Test263 baseline was
performed after registration commit `26bd3394` was pushed. Boot changed from
`4bbd82213c2c4501814c4dfc13d0695e` to `846248afd9914b499f799402274d08e6`;
before/after journal history uniquely attributes that transition. The ended
boot's kernel JSON is separate from the new boot's journals. No partition,
module, kernel, DT, rootfs, charging policy or USB configuration was changed.

The original runner stopped on 20 startup SMMU suspect messages, before any
30-second-window samples. `physical/summary.json` retains
`STOP_BASELINE_STARTUP_DIAGNOSTIC`. These messages have `fsynr=0x660021` /
`S1CBNDX=102`, the splash address range and context9 of a historical startup
fault class, but new parameter values outside the existing approved parser.
Their classification remains unresolved; no global parser/allowlist was widened.
They must not be presented as a warning-free or fully clean startup.

Under the owner's device-normal completion criterion, a separate same-boot,
read-only completion was registered in `DEVICE_COMPLETION_PLAN.md` and pushed
in `2d824741`. It collected the missing 30-second passive window without
another reboot, rollback, flash or charging experiment. Original STOP and all
raw evidence remain unchanged.

## Device observations

The separate completion covered **30.158 seconds / 7 samples**:

| Observation | Actual range |
|---|---|
| Battery SOC | 83% |
| Fuel-gauge VBAT | 4.198–4.203 V |
| Battery current | −407..−94 mA |
| Pack temperature | 32.7°C |
| SM5440 reported VBAT | 4.1225–4.135 V |
| SM5440 reported VBUS | 4.906–4.912 V |
| Cached ADC age | 148–920 ms; conversion timestamps advancing |
| SM5440 reported die temperature | 25.5°C |
| Monitor health / fault / pending | Good / 0 / 0 |
| Charge pump / IBUS | OFF (`01/01`) / 0 |

Protection registers remained `f2/e7/37/fe`. PC USB remained SDP, 500 mA,
Sink/Device. The battery label says Charging but measured battery current is
negative: this bounded PC-USB window is net discharge, not a power-gain result.
No startup REVBLK was recorded in this new boot (`no-startup-event`); the
two-fresh-confirmation startup-classifier branch was **not exercised**.

ADB and authenticated Wi-Fi SSH reached the same boot, current Wi-Fi
`10.125.29.77`. Device `usb0` exists, services are active, no failed unit or
Windows Code43 was detected. Host NCM connectivity was **not tested** in this
window. DCC remains absent. Full kernel journals retain the original 20 SMMU
messages; incremental/final evidence has no new CPU/kernel/passive failure.

Kernel config and notes exactly match Test263:

- config: `f2891de2b636820c8ad10b8682d7e68a9f4447c4af70cdfcd2b953de942f40b5`
- notes: `fea0613f810d57b4baee737127334195fe8ba2f12f59752ad2eee76159679c34`

There was no deployment; full partition/module hashes were not redundantly
recollected for this unchanged-kernel normal reboot. Test263's pairing remains
the baseline, not a newly claimed full installation acceptance.

## Meaning and limits

A lower-pack-voltage ordinary boot now provides healthy, advancing passive
samples with pump OFF. The previous stopped 0x80/stale-cache evidence is retained
in Test267/Test270. This does not establish a universal repair or prove that
voltage alone caused the earlier startup fault. No original failed run is
retroactively passed. Raw reported ADC values are not independent calibration.

**High-power / active Stage3 remains NOT READY.** SOC83 fails the unchanged
5..<80 active entry gate. Genuine <=100 ms physical acquisition, independently
calibrated nonzero current/voltage, verified protection/cutoff response, a live
PM/lifetime-safe adapter, and actual source APDO proof are still required.
Test269's unwired retarget core was not installed or exercised. No PPS Request,
pump ON, current increase, protection/thermal relaxation or latch clear occurred.

## Validation and next step

Registration's 8 focused host tests and syntax check passed. Results-only work
reuses exact Test263/Test269 qualification; kernel build and full regression
`executed: false`. Evidence seals, summary consistency and protected-tree audit
are recorded in `results-validation.json`; raw journals are not whitespace-normalized.
No GitHub Actions were started.

Next work is offline active-acquisition/protection/live-adapter qualification
and proof of an actual PPS-capable source, followed by separately registered
conservative physical entry only after those prerequisites hold. No additional
reboot/flash/charging round is scheduled here. Rollback was unnecessary because
installed software was unchanged. This is bounded passive behavior evidence,
not a reliability estimate or active/direct-charging acceptance.
