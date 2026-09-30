# Test263: offline SM5440 ADC snapshot qualification

**OFFLINE QUALIFIED; physical acceptance not executed. Active Stage3 NOT READY.**

Source `ea938b245bff3ae9e3c1828751ea149a90337992` adds an optional root-readable
`sm5440-<device>/snapshot` debugfs file. Reading copies cached memory under one
short `io_lock`, then formats outside the lock. It performs no I2C access and
cannot clear interrupts, initiate ADC conversion or change charging hardware.
Current and retained startup raw INT/STATUS/ADC/protection bytes, decoded units,
validity, age, fault/PM state and the last sampling error are distinguished.
The output explicitly says independently_calibrated=0 and pump_enable_supported=0.
PM's stop flag uses READ_ONCE. Normal debugfs proxies are removed/drained before
worker and device-managed memory cleanup; unavailable debugfs does not change
passive monitor behavior.

## Preserved charging baseline

The existing OFF, ADC, fault/startup classifier, power_supply and PM hardware
functions are byte-identical to the task baseline. The poller only adds error
and startup timestamp metadata. SM5714 fixed5V<=1.8A/fixed9V<=1.5A, 4.44V float
and fail-closed thermal policy remain unchanged. No PPS/APDO, pump enable,
protection programming, Q4 handoff or live charging adapter was added.

Test263 resolved and embedded config match accepted Test260 exactly:
`f2891de2b636820c8ad10b8682d7e68a9f4447c4af70cdfcd2b953de942f40b5`.
DTB is also byte-identical:
`233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e`.
The two precise diffs in validation are empty. All 96 protected files and 85
Docker/UPower requirements pass, HVC_DCC remains disabled. Test255 fixed-profile
and Test260 accepted artifacts remain intact. DTS, TCPC, USB/DWC3/adbd, rootfs,
SM5714 battery policy, CPU/OPP and configuration were not modified.

## Qualification

- Final standard ARM64 Linux7.2-rc3/clang21.1.8/JOBS8/ccache Image.gz, DTB and
  modules build passed. Embedded config and compiled overlays match the recorded
  revision; 181 regular module-directory files (167 .ko) match the normalized
  modules archive exactly. Artifact hashes/notes/manifests are retained.
- 34 affected host checks passed; 11 snapshot checks passed after the PM flag
  correction. Tests execute the real C copy/format helpers and cover missing,
  stale, pending, fault, stopped, future/long-age and retained startup samples,
  copy consistency/unlocked formatting and partial debugfs setup cleanup.
- One full regression at the final source passed **1351 tests**, zero failures,
  errors or skips (135.586s report). All former Test260 1290 IDs are retained.
  No test was deleted, skipped or weakened. The full run serves final host
  review without redundant wrapper/changed/full executions.
- Actual W=1/sparse v0.6.5-rc1 driver checking passed with no changed-driver
  diagnostic. The pre-existing VDSO __kernel_getrandom declaration warning is
  retained. The first distro sparse0.6.4 rejection is saved and is not claimed
  as a sparse pass. No dtbs_check repeat for the unchanged DTB; the prior
  PS5169 role-switch schema caveat remains, with no new clean-schema claim.

The initial b4fcdb9c build passed before the final READ_ONCE correction and is
not relabeled as final qualification. An attempted incremental rebuild stopped
on sandbox ccache read-only temporary storage; its raw failure is retained.
The identical final-source rebuild outside that sandbox passed. These are
source/environment corrections, not repeated qualification for result commits.
Existing stock-seed Kconfig warnings remain unchanged; no unrelated cleanup.

## Deployment and remaining gates

No tablet command, flash, reboot, partition write, module replacement or
Windows staging was performed. The tablet retains accepted Test260 and the
Test262 fixed-PD results, including its unplug evidence gap. No rollback was
needed because nothing was deployed. Large candidate binaries stay in
`out/kernel-x710-263-passive/`; tracked ARTIFACTS.json records their hashes.
No boot deployment bundle was generated.

See PHYSICAL_PLAN.md for a separately authorized passive snapshot acceptance:
one rescue/identity check, PC5V cached raw/age/gauge capture, then approved fixed9V
telemetry comparison and one PC rescue reconnect. Acquisition times must be
preserved. The earlier startup/gauge discrepancy was not simultaneous evidence
and does not establish a calibration error. Independent voltage calibration,
active OCP/protection and PM/live handoff gates remain unresolved. Snapshot
availability is not permission to enable PPS or SM5440 pumping.

Passive snapshot candidate: OFFLINE QUALIFIED.
Active Stage3 candidate: NOT READY.
