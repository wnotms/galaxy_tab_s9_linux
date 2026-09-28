# Stage 1 host candidate: compiled and packaged, not flashed

The SM-X710 SM5714 battery telemetry and ordinary switching-charger candidate
builds against Linux7.2-rc3, pinned to
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`. No device command, partition write,
rootfs install, candidate boot/probe or charging experiment was performed.
Installed production remains the last recorded Test249/Test250 baseline;
a later deployment must verify that baseline again before writing anything.

## Implementation and reference comparison

The local `/home/ms/Samsung/gts9wifi-fedora-linux` checkout is clean at
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`. All eight requested reference files
were checked against their committed bytes. The full driver comparison and
source hashes are in `validation/same-model-driver.diff` and
`validation/same-model-review.json`. Eight gauge/float/current conversion
helpers remain identical. X710 stock register, current, float and thermal
evidence is traced in `docs/X710_BATTERY_CHARGING_PORT_PLAN.md` and the
separate `SAFETY_REVIEW.md`.

Changes are the Stage1 driver, Kconfig/Kbuild hook0011, fragment, driver-overlay
installation route, required-symbol build gates, provider audit and candidate
identity gate, plus eleven new host tests. The charger first opens Q4, applies
bounded ordinary BC1.2 limits, restores/read-verifies4.44V at probe and every
reconfiguration, then enables charging only with valid pack temperature and no
OVP/watchdog fault. Read/write errors attempt to open Q4. The upper float/input
register bits are preserved. Missing battery metadata prevents probe.

The candidate removes the reference's fast-charge controls, SM5440 handoff,
TCPM coupling, OTG and MUIC role-switch writes. It uses conservative external
pack-thermistor limits and lifecycle charge inhibition; no die-temperature
fallback or fault-clearing reset loop. Health describes the implemented
thermal/OVP/watchdog checks, not every part of Samsung's complete battery
policy. A failed bus can also prevent Q4 isolation; source/host checks cannot
guarantee absence of physical damage. The first physical run remains bounded
and must verify current sign, voltage, temperature and actual SOC trend.

## Resolved config and device tree

Compared against the manifest-verified accepted Test249 config
`95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`:

```text
expected:
  CONFIG_BATTERY_SM5714: absent -> y
  CONFIG_QCOM_SPMI_ADC5_GEN3: n -> y
unexpected: none
CONFIG_HVC_DCC: n -> n
```

ADC5 Gen3 is necessary for the already-described PMK8550 pack thermistor.
IIO and plain ADC5 were already enabled but could not provide that channel.
Kconfig makes the Gen3 provider mandatory. The extracted Image.gz embedded
config equals the saved candidate config exactly. Candidate vmlinux contains
`sm5714_probe` and no DCC write/read path. `arch/arm64/mm/mmu.c` equals pinned
upstream. CPU OPP/cpufreq/cpuidle, watchdog/panic, pstore, WCN, display, cmdline,
rootfs and USB gadget were not edited.

**DTS source diff: empty. DTB binary diff: empty.** Candidate and accepted DTB
SHA256 is `eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0`.
The complete resolved delta is retained in `validation/config.diff`, with
the config, kernel notes, symbol-check result and machine verdict alongside.

## Local validation

| Check | Result and practical limit |
| --- | --- |
| Kernel + modules | `JOBS=8 USE_CCACHE=1 BUILD_MODULES=1 ./scripts/build-kernel.sh` exits0; ARM64/LLVM pinned build. Source copied into the worktree matches the reviewed candidate bytes. Existing stock-seed/fragment resolution warnings remain (BASE_SMALL, two panic bool values and repeated GENI console assignment); exact final config diff has no unexpected change. |
| DTB compile | Pass; unchanged accepted binary. |
| DT schema | Isolated dtschema2026.9 environment; `CHECK_DTBS=y qcom/sm8550-samsung-gts9wifi.dtb` exits0 but reports51 existing board/schema diagnostics. **Not schema-clean.** These include vendor-only/missing SM5714 bindings and existing pinctrl/USB/WCN properties. No bindings or DTS were changed; raw log retained. |
| Provider audit | Exit0,108 alias matches,0 unknown and42 explicitly classified remaining gaps. SM5714 and ADC5 Gen3 are now required providers, not exempted gaps. TCPC/SM5440/PS5169 remain intentionally unsupported. |
| Modules | Exact same181-file set,167 `.ko`; saved Test249 files match its sealed accepted module manifest. All167 candidate modules have identical allocated ELF sections and import modversions. Binary hashes may differ because of build/signature metadata; use the complete paired candidate directory/archive. |
| depmod | `depmod -n -e -E Module.symvers` exits0 with empty stderr, no unresolved-symbol diagnostic. |
| Changed-scope checks | `bash scripts/check-stall-offline.sh --changed --base HEAD~1`:1067 selected/executed,0 failures/errors/skips; unittest78.636s. Unknown integration paths correctly select all retained tests. |
| Final full suite | `python3 scripts/run-host-tests.py all --fail-on-skip --report out/host-tests/all.json`:1067 executed,0 failures/errors/skips,71.153s runner time. Raw log/report retained. |
| New safety tests | Eleven tests execute actual C helpers with mocked I2C, including temperature boundaries, ordinary limits, retained bits, OVP/WDT/FULL, failed programming/readback and config/DTB/DCC rejection. They do not emulate electrical behavior. |
| Boot bundle | Build and validation exit0; extracted payload, unchanged initramfs manifest, AVB/footer layout and image hashes checked. Nothing written. |

Two existing historical build-comparison tests now use the retained artifact
whose identity matches their historical record. Their original assertions
remain; the config fixture also has an explicit recorded-hash check. No old
test was deleted, skipped or retiered. GitHub Actions was not launched.

## Artifacts and deployment boundary

Kernel output: `out/kernel-gts9wifi/`. Paired module archive:
`out/kernel-gts9wifi/modules-sm5714-stage1.tar.gz`. Candidate bundle:
`out/boot-bundle-sm5714-stage1/`. `ARTIFACTS.json` lists exact kernel, config,
notes, driver/source, archive and all five image identities; all181 module
hashes are separately retained. Large binaries remain ignored local outputs.

Only boot.img differs from the saved Test249 generated bundle. The candidate
vendor_boot/init_boot/dtbo images match accepted device hashes. **Generated
vbmeta does not match the installed accepted vbmeta**: the bundle contains
`b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4`, while the
sealed Test249/Test250 device record is
`9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4`.
This existing packaging distinction is recorded separately in ARTIFACTS;
generated vbmeta is **never a deployment target** for this Stage1 test.
A future explicitly authorized test deploys only the candidate boot plus its
paired181 module files and preserves all four other partitions. It does not
flash the whole bundle.

`README.md` contains future battery-only,20-minute ordinary charging,
plug-out/USB checks and first-anomaly stop conditions. Expected supply names
are `sm5714-battery` and `sm5714-usb`; Stage1 exposes VBUS/BC1.2/programmed input
limit, not Type-C CC state or a PD contract. Rollback is the verified accepted
Test249 boot plus its full matched181-file module directory, with the other
four partitions preserved. No rollback is needed or performed now.

Stage2 SM5714 TCPM/Type-C/PD transport and Stage3 SM5440 opt-in PPS are not
implemented. Each remains gated by the preceding stage's physical acceptance.
