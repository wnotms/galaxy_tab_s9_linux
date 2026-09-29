# Test256 build and host verification

All builds use Linux7.2-rc3 pin a13c140cc289c0b7b3770bce5b3ad42ab35074aa,
clang21.1.8/LLVM,ccache4.12.3,JOBS=8,USE_CCACHE=1,BUILD_MODULES=1.
Each source commit uses an immutable repository snapshot; the disposable pinned
kernel worktree/build cache is reused sequentially. Accepted Stage2 outputs and
worktree are not overwritten. No generated .config manual edit or device access.

## Commit checks and preserved failures

| Source commit | Build / identity | Host verification |
| --- | --- | --- |
| a9ab1daf audit | first shell wrapper interrupted by concurrent script editing after kernel compile; immutable-snapshot retry passes, config/DT delta empty |1200 pass |
| fc19c12d TCPC bounds/cache | full Image/DT/modules +181-file archive audit pass, config/DT delta empty | changed1211/full1211 pass |
| ce4705bc passive monitor | FAILED: four missing case-label colons; raw failed log retained | changed1223/wrapper1223 pass before getter coverage correction; host result did not prove complete kernel compilation |
|73a75a48 getter fix | full retry + source/config/DT/protected audit pass; passive one config enable/one DT status | actual getter unit tests pass |
| eb552530 inactive transaction | full build/audit pass; two config enables/one DT status | changed1237 then wrapper/full1238 including strengthened getter test |
|61336aff IRQ fault latch | final isolated and default full builds/audits pass; no unexpected delta | full1239 + final changed wrapper1239 pass |

Each successful audit checks96 protected files, frozen Stage2 outputs, committed
driver overlay bytes, actual embedded config, DT properties,181 paired regular
module-directory files and exact normalized install archive contents. New inactive
Kconfig absent->n is explained, not treated as a hardware configuration change.
The original failed source/packaging logs remain separate from retries.

Commands (snapshots replace `.work/charging-source-final` per commit):

```sh
GTS9_WORKDIR="$PWD/.work" GTS9_CHARGING_PROFILE=sm5440-policy-offline \
  JOBS=8 USE_CCACHE=1 BUILD_MODULES=1 \
  KERNEL_WORKTREE="$PWD/.work/build/linux-src-x710-charging" \
  KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-x710-charging" \
  KERNEL_OUT_DIR="$PWD/out/kernel-x710-stage3-final" \
  .work/charging-source-final/scripts/build-kernel.sh
# Empty GTS9_CHARGING_PROFILE builds final default fixed refactor separately.
bash scripts/check-stall-offline.sh --changed --base HEAD~1
python3 scripts/run-host-tests.py all --fail-on-skip \
  --report out/host-tests/x710-charging-final-all.json
```

## Qualified final artifacts

Large images/archives stay in ignored out, hashes/config/notes/identity reports
are sealed under validation. No flashing package was installed or deployed.

| Artifact | Default fixed refactor | Offline monitor/transaction |
| --- | --- | --- |
| Directory | out/kernel-x710-fixed-refactor | out/kernel-x710-stage3-final |
| Image.gz SHA256 | bcd9304c301b235ce66578a8a357d7740c21ca5bd9382f23837c0cb1c8a83f03 | a9bb5bd98286e13c8fd9218a880809e6a3a159faafa37b5acadc8cbb34a6f4ca |
| Config SHA256 | db85d66a2ce9c68b1bc060f637aac1f9b9259d24c3acd05878ca2ef1ce735e95 | 8dd8de24726ef8f185590066cfffdf03f42f2a7257fde96a2cfdbbdfa0788645 |
| DTB SHA256 | c6148471113c5cb7589c64dee776e17b2fc20235cfeff4482616817a8b4e1c0b | 233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e |
| Paired regular files |181 (167 kernel modules) |181 (167 kernel modules) |

Notes/module archive hashes and individual file hashes are in artifact audit JSON
and per-profile SHA256.json. See exact unified config diff and identity-diff.json.
The source revision is61336aff; a later docs/evidence commit has identical code.

## Static checks and limits

W=1 C=2 CHECK=.work/tools/sparse-src/sparse checks sm5714-battery.o,
sm5714_usbpd.o,sm5440-direct.o,x710-charging-policy.o. Sparse source is official
kernel.org commit37156835e3d725b6d750f000be33ba3814bb2310,version0.6.5-rc1.
No changed-driver warnings. Retained VDSO __kernel_getrandom declaration warning
is preserved. Old distro sparse0.6.4 fails __typeof_unqual__ feature validation;
its nonexecuted checker attempt is not represented as success.

dtschema2026.9/pylibfdt1.7.2 installed in a task-local environment, no system
package/sudo change. New binding dt-doc-validate passes; dtbs_check with
DT_SCHEMA_FILES=siliconmitus,sm5440.yaml runs, exit0. Both Test255 and candidate
retain the same unbound PS5169 role-switch type diagnostic; no SM5440 binding
diagnostic. Do not infer whole-board validation from make's exit0 (upstream
dt-validate command tolerates diagnostics). BASE_SMALL/old panic-symbol and
SERIAL_QCOM_GENI_CONSOLE override warnings originate in retained config merging;
final exact config gate resolves all expected values.

Final report selected1239 (core1134,artifacts18,archive87),executed=true,
failures/errors/skips empty; report wall111.428s. Final shell wrapper1239,
unittest111.616s. Earlier per-phase runs and all original1200 checks retained.
No zero-selection invocation is claimed as a regression pass.

After the results commit, repeat immutable-source build/host/config/DT/protected
review into separate ignored out/x710-record-* / out/host-tests/x710-record-all.json.
Do not overwrite the qualified artifacts or re-label them with another revision.
