# X710 source-authorized 5V PC charging budget

**Offline candidate PASS; hardware PC charging acceptance NOT EXECUTED; complete
charging port NOT READY.** Design: `docs/X710_PC_CHARGING_BUDGET.md`.

## Evidence and behavior

Pinned mainline TCPM maps Rp1.5A/3A to current budgets; default Rp uses our existing
BC1.2 callback. Samsung `sec_bat_set_usb_configure()` applies Rp current votes and
same-model Fedora prioritizes Type-C budgets. We port that precedence only, not
Fedora5V3A/2800–3150mA pack targets, fast-charge or weakened thermal policy.
Source excerpts and exact hashes are in `source-references.json`.

Historical Test307 raw journal already contains fixed5V3000 then1800mA budgets
and500/500 ordinary configuration logs. This directly supports software underuse
of a logical grant, not current PC capability, measured VBUS/watts or low-battery
root cause. The last independently saved PC snapshot had SDP500mA and negative
pack current; owner now reports current low-battery shutdown. No new device
measurement/probe is fabricated and an earlier unaccounted boot is not attributed.

Only `sm5714_configure_charging_locked()` changes. After all existing safety gates,
a TCPM-owned fixed5V grant above500mA authorizes input up to the shared1800mA
ceiling even if MUIC reports SDP/UNKNOWN/CDP. A lower ordinary pack target rises
only to that capped input current; DCP2100mA remains unchanged. The subsequent
contract minimum and reduced thermal500/500 clamp still apply. Default SDP500,
subminimum/OFF/suspend/fault/PPS/switching inhibition, fixed9V1500/2100, float4440,
FULL and AICL protection remain. There is no USB3-speed-only900mA permission,
blind limit override, TCPC/TCPM protocol change or user control interface.

## Local validation

Actual-C pre-fix charge/companion tests reproduced **12 failing subcases**;
`before-fix-tests.log.gz` and `development-finding.json` retain them. Final
**109 affected tests PASS 4.604s, zero skips** across six suites,
including every consumer of the modified shared actual-C fixture, ownership,
program recovery and fixed-charge evidence parser. New cases prove higher5V
SDP/UNKNOWN/CDP grant precedence, explicit default500, integer/register rounding
and cap, DCP/9V/float, thermal/fault/FULL/OFF/suspend, real companion downgrade,
detach/re-enable and sticky first-fault refusal. No old test removed or skipped.

The first affected run caught two existing recovery expectations: its fixture
modeled a valid1800mA grant but expected500mA programming. The original exact500mA
assertions remain with a default500 grant; the same recovery/poller tests also
assert exact1800mA programming for an1800 grant. Initial failures/log are retained
under `initial-affected-*`; no failing assertion was silently dropped.

ARM64 Image/DTB/modules **PASS 76.045s**, eight jobs/ccache and the same
native-profile cache. The build overlapped correction of test expectations;
kernel code did not change after the build started. Final compiled source hashes
match. W=1/sparse **PASS 6.998s**, known upstream vDSO warning only,
no driver warning. Standard object bytes equal the initial build after restoring
flags; formal Image/vmlinux were not relinked by the static check.

Patch checkpatch and whitespace checks are clean. Whole-file strict checkpatch
reports seven pre-existing style CHECK notices with zero errors/warnings; an exact
HEAD comparison confirms identical contexts and no new notice. We did not mix
unrelated style edits into this patch. The first host assertion expecting a clean
whole file failed; source-style-comparison.json records correction, including an
initial non-C filename probe that was not used as qualification.

Exact resolved/embedded config equals the preceding cancel-drain native candidate:
`6f70dd31a582efc0464c37b505693f7fe8af3949a9c2a573a1ca116a7e73f42d`.
DTB equals accepted311 byte-for-byte:
`233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e`.
No new config/DT delta; HVC_DCC remains disabled and container/SM5714/ADC5 remain.
Existing native-profile differences from installed accepted311 are still recorded
in artifact-audit.json.gz and are not claimed to be installed.

**56 protected source /42 frozen formal artifact hashes preserved.** All181 paired
module files are verified; runtime bytes/shape/relocations and nondebug symbols
retain prior qualification. Recorded module ELF differences from accepted311 are
BTF/build-ID/DWARF directory only; built-in metadata exactly matches preceding
cancel-drain. Actual compiled copies, kernel notes, embedded config and existing
native/core/provider linkage are checked. Full details: `summary.json` and
`artifact-audit.json.gz`. Formal output: `out/kernel-x710-pc-current/`.

## Physical boundary and full-goal next work

No device deployment/reboot/partition/module/service/rootfs/current register
write, PPS Request or pump ON. Native/OCP private grants remain closed. Same
native cache reused, not a new full build tree or revived originalTest303 provider.
No Windows staging, full host regression/routing change or Actions.

Recover current low battery using the already accepted18W source before any
normal-boot/SOC>=20% physical entry. Current PC port/cable/capability is unknown;
read raw Rp/TCPM budget/MUIC/input register/pack current when available. If actual
source grants only500mA, this correction intentionally does not raise it or prove
net charging. A future accepted higher5V grant needs its own bounded temperature/
pack/input/downgrade/unplug/ADB/deviceNCM regression. Preserve accepted311 rollback.

The full direct-charge goal remains incomplete: physical ADC/gauge calibration/
freshness/current/cutoff proof, then PPS-OFF/<=1.8A pump/fault/PM and independent
higher-power steps. PC5V host qualification does not grant direct activation or
qualify the failed ADC profile for replay.
