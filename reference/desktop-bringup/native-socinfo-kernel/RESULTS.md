# Native SoCinfo kernel — compiled offline, not deployed

Enable the existing Linux 7.2-rc3 `QCOM_SOCINFO` driver to obtain native SMEM
board identity for Samsung SSC. Resolved config changes **only**
`CONFIG_QCOM_SOCINFO: n → y` relative to accepted Test331. QCOM_SMEM/SOC_BUS,
UPower/OCI, SM5714 and DCC-off remain unchanged. Full embedded config matches
the saved resolved config. DTB is byte-identical to Test348; no DTS change.
This commit does not change charging, USB, ADSP, input or firmware sources.
It inherits current qualified charging source, not a claim of all-driver
binary identity with historical Test331.

## Build and pairing

JOBS=8/ccache/LLVM/Image.gz/DTB/modules standard build completed, exit 0.
The existing profile build directory was reused; formal Test331/Test348 artifacts
remain hash-identical. Its previous external-module-provider qualification is
invalidated. Upstream pin and exact input/output hashes are in BUILD_AUDIT.json.
All 181 module-directory regular files match their newly created archive.
Kernel notes and Image/config/DTB/module hashes are saved; binaries stay in out.

Attempt 01 stopped before compilation because the historical charging-only
config gate rejected the new identity symbol. A separate explicit
`--native-socinfo` gate admits only that reviewed change and requires built-in;
its default historical behavior is unchanged. Attempt 02's handle disappeared
across incoming turn activity, with no terminal build result or live process;
its raw log is retained as **interrupted, not successful**. An incremental
resume of the same build/provider completed as attempt 03, not another profile.
Only inherited stock-seed Kconfig warnings appeared (BASE_SMALL, two BOOTPARAM
integers and GENI console override); resolved gates and DCC-off assertions pass.

The accepted Wacom + palm-aware FTS source was copied unchanged to a separate
small external-module output directory and rebuilt with W=1 against the new
provider. Both builds pass; 29 pen/38 touch imported symbol CRCs match the new
provider/pen exports, and vermagic matches. Existing accepted modules/loaders
remain untouched. This is ABI/build validation, not physical touch acceptance
on the new kernel or permission to relax their Test331 identity guards.

## Host validation and limits

41 affected SoCinfo/config/UPower/OCI tests pass, 0 skip. Shell syntax passes
for 52 scripts. One exhaustive run executed **3032** tests and **did not pass**:
8 failure records, 22 error records, 25 skips. Complete report/log retained.
Do not label this full regression green or silently waive its failures.

Failures include historical retired-image prerequisites, old deployment/source
freeze/state fixtures and a binary-location test that also counts ignored local
desktop .debs. One relevant sensor bug was exposed: `build.py` imports a generic
`prepare` module and receives GNOME's same-named module in combined discovery.
Fix that import isolation separately and rerun affected tests. Do not regenerate
out-of-window historical images just to make archive prerequisites pass.

## Endpoint and next work

No device command/install/flash/reboot/SSC daemon/ADSP start was executed.
The restored Test331 Debian state from Test348 remains the last accepted device
baseline, without an end-in-TWRP requirement. No new charging attempt/cap change.

Native-kernel status: **COMPILED / NOT DEPLOYMENT READY**. Finish explicit
new-identity loader packaging and controlled early signed ADSP availability;
register a separate boot scope before deployment. Actual SoCinfo capture,
firmware PAS authentication, sensors PD, IIO/D-Bus/rotation and input regression
are unverified. Never late-start ADSP on the current live desktop.
The full hardware port and higher-power charging goal remain unfinished.
