# Test305 offline qualification

Verdict: **OFFLINE_ADC_CONDITION_CANDIDATE_QUALIFIED**.
Source: `9dceb767698b9518a5c150dad7f51b46df4742d2`.
Physical deployment/experiment: **not executed**.

The actual kernel now has a separately selected, one-conversion pump-OFF
ENHIZ/ADC comparison. Only CNTL6 bit7 is temporarily cleared/restored, with
ADC-off/mode checks and exact readback. First conversion error and restoration
error remain separate; failed cleanup remains pending/faulted. PM/unbind drain
work before one bounded restoration attempt. No companion publication,
subsequent worker reschedule or second experiment on resume. No userspace write
interface, PPS request, pump activation, reset or protection/current programming.

Samsung X710 `set_ENHIZ()` and `init_reg_param()` provide bit/sequence provenance;
Test304 provides the live0x89 observation. This qualifies an experiment, not a
claim that the vendor attached/OFF condition is incorrect or that ENHIZ explains
the voltage discrepancy. See `docs/SM5440_ADC_CONDITION_TEST.md`.

## Validation

* Full local integration regression:1,748 passed,112.621s, zero failure/error/skip.
  An additional normal preprocessed-path equivalence test was then added;
  final21 diagnostic/profile tests passed0.705s. Unique qualified tests1,749:
  1,728 unchanged full-run results reused plus21 final diagnostic tests.
  No test deletion/skip/weakening, routing change, Actions or CI.
* The16 checked preprocessed structures/functions match949d6b73.
  Original converter,20ms rearm, quiesce, thresholds and100/500ms APIs remain
  byte-identical. Tests execute real C, including each actual bus failure,
  uncertain CNTL6 write delivery, readback mismatch, timeout and cancellation.
* Standard8-job ARM64 Image/DTB/modules build: exit0,92.647s.
* Changed SM5440 object W=1/C=2/sparse: exit0,8.078s. Object and vmlinux hashes
  remain identical to the build. No changed-driver warning. The existing
  upstream vDSO `__kernel_getrandom` declaration warning remains recorded;
  seed-config normalization warnings are preserved in the full build log.
* Checkpatch: exit0, empty diagnostic output.
* Artifact audit:96 protected files unchanged,10 compiled overlays match the
  committed source, frozen Stage2 artifacts intact,181 matched module files
  exactly represented in the modules archive; embedded config matches resolved.
* Against **accepted Test299**: exact config delta is only
  `CONFIG_SM5440_ADC_CONDITION_TEST: absent -> y`. DTB is byte-identical.
  Against frozen Stage2, the existing passive charger enable/policy declaration
  are separately explained in the audit; no other unexpected delta.

Docker/UPower, DCC absence, SM5714 ordinary fixed5V<=1.8A/9V<=1.5A policy,
4.44V float, pack/IIO fail-closed thermal policy, USB/gadget/adbd and TCPM core
are unchanged. Mainline/passive/policy profiles do not select the experiment.
The new symbol is default-off and cannot coexist with the PPS consumer profile.

Artifacts are in `out/kernel-x710-305-adc-condition`; hashes/byte sizes are in
`summary.json` and `validation/artifact-audit.json`. No binary is tracked here.
All25 seals of263/297/299/302/303 formal artifacts remain unchanged. Old297
cache was reused only after2,733 critical debug/generated files were compressed
and individually verified. Its former cache path is no longer a297 provider;
the retained archive/manifest preserve reconstruction/debug provenance.

## Device entry gate

Read-only final identity still shows retained Test299/Test300 boot
`57535bed-a626-48d0-aaaa-3071ac8332e5`, with accepted notes/config. However, the
gauge has fallen to0%/3.287V with net negative current. PC input is SDP500mA,
Sink/Device; Wi-Fi SSH remains responsive. This is below the physical test
entry range. No flash/reboot/ADC experiment may start in this condition.

The owner was asked to reconnect the previously validated USB-C2 ordinary18W
source while preserving Wi-Fi, without reboot. Recharge telemetry is a separate
read-only observation, not a deployment or validation of this candidate.
Physical comparison must wait for battery recovery and a separately committed/
pushed one-boot registration with accepted299 rollback. No deadline/fault/
freshness exemption follows from the experimental profile.

ADC validity/calibration/100ms freshness, physical pump-OFF PPS protocol,
active protection/OCP and full direct coordinator/pump acceptance remain.
**Full active Stage3: NOT READY.** The full port goal remains active.
