# Resolve ADC completion context before activation

The retained native session is compiled and host-tested. Its ADC/current/physical
cutoff qualification is still missing. Preserve ordinary Stage2 and the closed
native grants. Do not turn Test321 raw reads, a coherent-looking pair or a mocked
READY flag into a physical activation grant.

The exact Samsung X710 `sm5440_irq_init()` writes MSK1..4 = C0/F7/18/F8 before
registering its threaded interrupt. `sm5440_charger.h` maps MSK4 to 0x07 and
ADCUPDATED to INT4 bit0. Our passive driver neither requests this IRQ nor writes
those masks. Test318/321 preserve INT/status/control data but do not record MSK4.
Consequently mask configuration is a missing context fact, **not an established
cause** of missing READY. Source excerpts/hashes are under
`reference/charging/sm5440-adc-completion-audit/`.

Samsung's one-shot worker re-enables ADC every200ms; its read function excludes
ordinary CHG-OFF below CHECK_VBAT. Fedora uses continuous AVG32 and reads ADC
registers without requiring INT4 READY. Neither proves a100ms fresh OFF conversion
or independently calibrated current. The native deadline/READY criteria stay
unchanged; do not replace them with unverified elapsed time or unchanged raw data.
Do not blindly copy the vendor IRQ masks, enable the pump for ADC, or change ADC
math/ENHIZ/protections to make a test pass.

The new `scripts/sm5440-adc-context.py` performs **one** bounded ADB/Python capture:

- Validate expected boot ID, exact embedded config and kernel notes; refuse
  lpcharge context before any register read.
- Read only pump-mode witnesses, ordinary MSK1..4, ADC controls and DEVICEID.
  `pread` reads exactly one7-byte register line. No full-regmap/INT dump,
  read-to-clear access, ADC start, cached-to-fresh conversion or register write.
- Save the existing cached snapshot and pack/source telemetry without requesting
  a new measurement. Check identity again across capture.
- Preserve raw results, errors, command times and SHA256. No retry, reboot,
  service restart, recovery, flash or PPS operation.

Use fresh confirmed baseline values; never substitute an old boot ID:

```sh
python3 scripts/sm5440-adc-context.py \
  --expected-boot-id ACTUAL_NORMAL_BOOT_ID \
  --expected-config ACTUAL_ACCEPTED_CONFIG_SHA256 \
  --expected-notes ACTUAL_ACCEPTED_NOTES_SHA256 \
  --output reference/charging/sm5440-adc-completion-audit/normal-context
```

The current default Windows ADB location is `/mnt/d/android/platform-tools/adb.exe`
from the latest AGENT.md workflow. Expected hashes must come from the accepted
manifest. Successful verdict `CONTEXT_CAPTURED_NOT_ADC_QUALIFIED` means only that
the ordinary register context was captured; all calibration/freshness/OCP/ON
flags remain false. A different MSK4 is an observation, not permission to write
F8 or to claim it caused the old timeout. Failure saves STOP and prohibits replay
with guessed identity.

Next normal baseline observation should first settle this missing mask fact.
Then choose a source-backed, single-variable OFF experiment only if the fact
justifies it, registering/pushing its exact code/package/scope before mutation.
Compare real VBUS/VBAT/source/pack brackets and completion provenance; preserve
first failure and exact ordinary rollback. Pump/current/OCP/cutoff/PPS remain
later acceptance. No physical stress or intentional protection-limit test.

Today's first read stopped **before register access** because the boot changed.
New accepted config/notes match, but lpcharge=1 and1% SOC prevent normal deployment
admission. Prior/current boot journals are saved; a root *user manager*
shutdown.target entry is not evidence of a system poweroff. Manual versus
low-battery/autonomous restart remains unknown pending the owner's response.
Battery recovery and normal-entry confirmation precede any physical candidate;
this plan does not authorize an automatic reboot or reuse an unchanged failure.
