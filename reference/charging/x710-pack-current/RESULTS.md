# Native X710 measured pack-current guard

**Offline qualification PASS; full charging port NOT READY.** The design in
`docs/X710_PACK_CURRENT_GUARD.md` preceded code. No physical operation occurred.

## Actual change

The existing native SM5714 pack provider already reads real gauge CURRENT SRAM,
but the linked controller dropped it. Six actual-C fault cases reproduced the
missing refusal in first/second pack reads, active monitoring and paused refresh
before this fix; before-fix-tests.log.gz retains those failures. Provider I2C
failure already propagated correctly; no duplicate current provider was added.

The native controller now preserves signed current with its original acquisition
bracket, validates both readings independently, and propagates mandatory current
validity/value to the transaction, real actuator and supervisor. Native mapping
of consumer epoch preserves the current fields. Missing/current excursions stop
before another ON/resume/watchdog feed and use once-only OFF/fixed physical proof/
lease release. Unknown OFF still forbids protocol or lease release. Status retains
an excessive measured value; failed reads clear validity/value rather than reuse
a preceding good sample. Read-valid is not healthy/fresh/OCP-qualified.

Signed −3.6A..+3.6A is a new conservative **bringup refusal envelope**, not Samsung
production OCP, current programming or a physical protection grant. Its positive
bound uses approved1800mA input and source-backed2:1 current policy; negative
bound refuses excessive discharge without labeling it a hardware reverse fault.
Zero/ordinary negative current are allowed with a successful real read. Direct
comparisons avoid abs(INT_MIN)/unit truncation; gauge resolution remains1000uA.
No ordinary switching/fixed-current setting or safety parameter changes.

Source reread also corrected the existing vendor audit: pd_preset_dc_work uses
`target_ibus *50/100`, not target_ibat; separate work config uses cc_gl=ci_gl*2.
Exact source excerpts/hashes and distinction from bringup limits are retained.

## Local validation

Final **351 affected tests PASS,11.072s,0skip** across16 related suites; no routing
change/full regression/Actions. Cases exercise exact signed endpoints, real zero,
invalid current and INT_MIN/MAX, first/second spikes, provider read errors, actual
controller active cleanup, actual native mapping/actuator start, supervisor OFF
before/during conversion and refusal of paused resume. All previous tests and
assertions remain. The first expanded run had two new harness method-name errors;
its log is retained; correcting self.case to existing self.run_case fixed them.
The348-pass intermediate log is retained separately before three native cases.

ARM64 Image/DTB/modules build **PASS90.621s**, eight jobs/ccache/existing native
profile cache. W=1/sparse **PASS7.376s**, only known upstream vDSO declaration
warning, no changed-driver warning. Strict checkpatch and diff-check:0 issues.

Resolved embedded config exactly matches prior native active-session/control:
SHA2566f70dd31a582efc0464c37b505693f7fe8af3949a9c2a573a1ca116a7e73f42d.
Accepted311 delta remains only policy n->y, native-control absent->y and existing
ADC-condition !policy dependency n->absent; no new config changes. HVC_DCC=n,
SM5714/ADC5 and Test254 USER_NS/mqueue/container requirements preserved. DTB
exact accepted311 SHA256233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e.

**53 protected source /30 frozen formal hashes preserved.** 181 paired module
files archived/verified.167 module ELF differences are only recorded BTF/build-ID/
DWARF-directory/debug relocations; all other runtime bytes/shape/relocations and
nondebug symbols match accepted311. Built-in metadata/index exactly matches the
previous active-session candidate. Actual compiled copies/embedded config/notes/
linked controller current helper and supplier/core/hardware references verified.
Full machine-readable detail is in artifact-audit.json.gz and summary.json.

Formal output: `out/kernel-x710-pack-current/`. Reused one native-profile cache;
its historical303 name is not old303 qualification. No new complete build tree,
Windows staging or repeated partition/rollback checks. Current paired module
unpack is the new formal qualifier's consumer; previous sealed artifacts preserved.

## Boundaries / next full-goal work

The private kernel activation/OCP grants remain closed; host-only mock grants
are not compiled into the kernel. No public control knob, automatic sampling/PPS/
pump activity or physical current/calibration/timing claim. The complete port
still needs physical ADC and gauge current freshness/calibration/cutoff evidence,
then independent PPS-OFF/<=1.8A pump/fault/PM and higher-power acceptance. Passing
this guard does not establish a worker can protect against I2C hangs/CPU stalls.

SM5714 Stage1 driver/float4440/thermal/suspend, TCPC/TCPM protocol, DWC3/USB/gadget/
adbd/rootfs, DTS/config, input/PPS limits and original accepted311 device are not
modified by this increment. No flash/reboot/partition/module write/pump ON/PPS.
Latest separately recorded reconnect has unavailable ADB/Wi-Fi; current screen/
IP/boot/power attribution remains pending. It is not CPU-stall proof. Do not deploy
or repeat an unchanged failed ADC profile without new source-backed scope and
normal/current SOC>=20% safety/rescue entry evidence.
