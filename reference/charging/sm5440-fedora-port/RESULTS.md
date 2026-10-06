# Fedora X710 SM5440 source candidate — offline qualification

2026-10-06. Owner direction: directly use the Fedora repository source and stop
repairing the custom ADC diagnostic. This implements that change of route.

## Source and scope

Kernel source commit: `376693d732e2aede470643c611d4cc31d93d4893`.
Fedora same-model source: `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`,
`kernel/files/sm5440_direct.c` (GPL-2.0-only). `SOURCE.json`, the exact compressed
original and `upstream-to-port.diff` preserve reproducible provenance.

The actual Fedora register/ADC/init/PPS/refresh/charging worker is ported to
`kernel/drivers/sm5440-fedora.c`; this is not a passive-only replacement. Necessary
adaptation uses the existing mainline TCPM and SM5714 switching lease/epochs.
Continuous ADC follows Fedora's operating model. The former single-shot READY
acquisition and its 100ms diagnostic are not linked into this candidate. No new
custom ADC repair or replay is planned. Test326's timeout remains recorded.

Direct charging defaults OFF with a read-only boot opt-in. Probe does not request
PPS, reset the charger, inhibit SM5714 or start the pump. A compiled activation
path exists: the profile verifier now explicitly reports that fact, separately
from the OFF default. The final verifier metadata/assertions are hashed in
`source-inputs.json`; these host-only changes do not rebuild the kernel source
commit above.

Fixed charging remains 5V <=1.8A and 9V <=1.5A; SM5714 float remains4.44V and
existing thermistor/thermal/suspend protections remain unchanged. The initial
opt-in PPS request and pump input cap are1.8A; target8.2–10.5V. Entry requires
SOC5–<80%, VBAT3.5–<4.3V, real pack15–<38C, healthy battery and fixed9V. Active
stops include pack42C, VBAT4.4V and die85C. OFF verification, actual VBUS settling,
checked fixed fallback, watchdog preservation on unknown OFF, suspend veto on
failed cleanup, and bounded fault backoff are covered by host mocks. They have
not yet been accepted on this device with this driver.

## Executed verification

| Check | Result |
|---|---|
| Affected host suites |155 tests PASS,6.912s,0 failures/0 skips|
| Final verifier metadata/new suite |15 tests PASS,0.289s; overlaps the155|
| ARM64 Image/DTB/modules final build |PASS,75.858s; JOBS8,ccache,existing incremental tree|
| Changed driver W=1/sparse |PASS,12.344s,no warnings; standard object restored|
| Embedded config/resolved config |Exact match; DCC absent,85 required symbols retained|
| Accepted Test323 config comparison |Only six expected symbol changes; `config.diff`|
| DTB |Byte-identical to Test323|
| Paired modules |181 exact filenames; runtime ELF bytes/layout/symbols unchanged|
| Protected sources/old formal artifacts |59/37 verified unchanged|
| Offline boot package |Built/unpacked/payload checked; no device commands|

Full host suite was not executed: affected-only scope follows the latest owner
workflow and test routing was unchanged. Initial patch syntax failure and earlier
successful build logs are retained; `build.json` is the final authoritative run.
No additional kernel build was executed for results/metadata-only changes.

The six resolved symbol changes are replacement `CHARGER_SM5440_DIRECT=y` by
`CHARGER_SM5440_FEDORA=y`, plus four old dependent disabled symbols becoming
absent. No unexpected config change exists. Docker/UPower, SM5714, ADC5 Gen3 and
HVC_DCC=n are preserved. Module BTF and four built-in metadata files change with
the new built-in driver identity; module archives are therefore correctly paired
new artifacts, not claimed byte-identical old archives. `summary.json` records
all section differences.

DTS, TCPM core, SM5714 battery/TCPC source, DWC3/USB gadget, adbd/rootfs, CPU/GPU
and fixed charging policy were not modified. Old drivers/results/tests remain
available for history and rollback; this profile does not select them.

## Artifacts, device and acceptance limits

`PACKAGE.json` contains Image.gz, exact DTB/config/notes, modules archive, boot
and rollback hashes. Candidate boot: `out/boot-bundle-x710-fedora/boot.img`.
Kernel/modules: `out/kernel-x710-fedora/`. Reused build cache is now the Fedora
profile provider, not a qualified provider for previous native diagnostic trees.
No new full build tree or Windows staging copy was created.

This is `UNREGISTERED_FEDORA_SOURCE_CANDIDATE`. No flash, partition write, reboot,
rootfs change, physical PPS request or pump activation was executed during this
source port. Last accepted device state remains restored Test323, boot
`3f4cf492bb2f4d8c89e805c6ec499642` (Test326 final restoration record); no fresh
live observation is claimed here. Exact Test323 boot and181 modules are retained
as rollback. The historical Test326 ADC timeout is not rewritten as success.

Offline verdict: **OFFLINE_FEDORA_PORT_PASS**. Full charging port/higher-power
hardware verdict: **NOT READY** pending separate physical acceptance. Software
ADC conversion tests do not establish sensor calibration, physical OCP or
higher-power charging reliability. Next work is in `NEXT_PHYSICAL_PLAN.md`.
