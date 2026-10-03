# Native owned PPS observer integration — offline only

The actual SM5714 TCPC driver now exports a read-only owned-contract API through
its existing built-in Kbuild target. It does not issue a Request or change
switching ownership, charging controls, PD policy, source roles or pump state.

- 88 affected actual-C/pthread tests: PASS, no skips (1.609 s).
- Normal Linux 7.2-rc3 ARM64 Image.gz, DTB and modules build: PASS (88.423 s).
- Actual TCPC object W=1/sparse: PASS (7.202 s), no changed-driver warning.
  Known upstream vDSO `__kernel_getrandom` declaration warning is retained.
- Exact config diff vs Test316: empty; DTB identical to accepted311.
- Versus accepted311 only the existing `CONFIG_SM5440_ADC_CONDITION_TEST=n→y`
  diagnostic profile difference remains. No additional config change, DCC stays
  off and Docker/UPower/SM5714/ADC5 Gen3 prerequisites remain enabled.
- All 137 protected kernel/rootfs/build sources and nine prior formal candidate/
  rollback artifacts retained unchanged. Converter code and timing unchanged.
- Exact paired archive: 181 regular files. The 167 `.ko` hashes changed solely
  in `.BTF` sections due to the new linked kernel type layout. Executable,
  data, version and remaining sections unchanged; use the new paired archive,
  not a hash-based claim that old module bytes equal these candidate modules.
- New native API and its export are confirmed in linked vmlinux. The initial
  audit ran before archive packaging and failed with FileNotFoundError; retained
  in initial-audit-error.json and corrected by deterministic packing/auditing.

The host fixture now requires the API in the actual source; no temporary draft
application can conceal a missing integration. The fixed wrapper is compared
against sealed pre-integration commit 2f245cea, rather than against itself.
The historical unapplied draft and raw evidence remain untouched.

## Device state and limits

Read-only ADB confirms the same accepted311 boot 6f0d319b, exact embedded config
and notes, USB NCM interface UP, Wi-Fi 10.139.153.195, real pack 31.3°C and
thermal_zone37 `sm5714-battery` enabled. SM5440 reports Not charging. The earlier
photo's thermal read failure is not reproduced by this read; this is not proof
that an intermittent sensor fault has been fixed. Host NCM SSH was not retested.
No new boot attribution/physical charging acceptance is claimed.

The diagnostic profile is an offline build, not an active charging candidate or
registered physical test. No flashing, reboot, partition/module/rootfs write,
PPS request, pump ON or current increase occurred. Full/Actions executed:false;
latest affected-only owner scope reused retained unrelated qualification.

Test317's 128–130 ms acquisition/read brackets remain diagnostic evidence,
not physical 100 ms ADC/OCP qualification. Fresh pack acquisition, a real live
worker, physical current/cutoff/OCP proof, native refresh/fallback and PM
acceptance remain. No guessed AVG32 replacement or deadline relaxation.

Full SM5714/SM5440/PPS charging port: **NOT READY**.
