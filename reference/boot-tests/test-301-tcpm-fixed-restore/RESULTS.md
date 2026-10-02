# Test301 results — offline fixed restoration qualified

Source **2207d132d9aa29b270acfbf8a3b3bfefbe4ae8cc**. No device command, deployment,
reboot, PPS activation/tuning, pump ON, switching release or current increase.
Device remains Test299 source9173df11, retained under Test300's accepted scope.

Fixed snapshots now distinguish advertised capability from active contract:
ONLINE=1 accepts PD/PPS/AVS-capable sources while retaining exact mirrors,
generations and 5V/1.8A or 9V/1.5A limits. ONLINE=2/3 is never accepted as fixed.
The actual TCPC Request guard remains `pps_authorized=false`.

The new kernel-only restoration operation uses the real standard TCPM
power_supply setter, only ONLINE=1 and only to leave ONLINE=2. It requires the
current instance/source token and an acquired, inhibited switching lease, checks
both again before the call, drains on removal, refuses concurrent operations and
returns a stable bounded fixed observation or zero output on error. It does not
release a lease or prove physical VBUS/pump OFF. Callback budget changes still
revoke the lease while retaining inhibition. No live consumer is installed.

| Check | Result |
| --- | --- |
| Explicit affected host tests | 143 PASS, 4.549s, no failure/error/skip |
| Actual restore/provider C | 19 tests, lock-aware setters/getters and teardown |
| Actual snapshot C | 29 tests, capability/ONLINE and lifecycle |
| Actual battery ownership C | 17 tests, including read-only lease check/no I2C |
| ARM64 Image/DT/modules | PASS, 92.282s, standard profile/pin/toolchain |
| Changed objects W=1/C=2 sparse | PASS; exact linked-object bytes with project ccache environment |
| Checkpatch | Final 0 errors/warnings; initial whitespace failures retained |
| Test299 resolved config / DTB | Both byte-identical; exact diff files empty |
| Protected sources / overlay audit | 96 unchanged, all 8 compiled overlays match source |
| Module archive | Exact paired 181-file directory/archive |
| Test299/Test300 evidence | 29/181 sealed files unchanged |
| Full regression / CI | executed:false; no Actions or CI |

The conservative changed selector preview selected 1664 tests, executed:false.
The latest owner instruction permits explicit affected tests; it is not a new
full-regression pass. Tests still exist and remain discoverable. The snapshot's
old whole-driver ban on any setter is now scoped to its actual read functions;
the new restoration tests additionally enforce the only allowed ONLINE=1 write,
no activation/tuning/release and unchanged default fixed-only Request gate.

Initial W=1/sparse compilation itself succeeded, but its additional object-byte
assertion failed. The standalone command had omitted build-kernel.sh's
CCACHE_BASEDIR, changing cached compilation path handling. A W=0 invocation
without matching environment also differed; setting environment alone did not
force make to rebuild an up-to-date target. Preserve all three raw reports.
After saving those two objects and recompiling them with project CCACHE_BASEDIR,
both matched the original linked objects exactly and vmlinux stayed unchanged.
Final W=1/C=2 with the same environment also matched both original objects.
No source correction, full relink or additional kernel build was required.
The only sparse warning is the existing upstream vDSO `__kernel_getrandom`
declaration; neither changed SM5714 driver produces a warning.

Configuration SHA f2891de2b636820c8ad10b8682d7e68a9f4447c4af70cdfcd2b953de942f40b5;
DTB SHA 233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e.
Image/notes/module hashes and all raw evidence are in summary.json and validation.
Artifacts: out/kernel-x710-301-passive. Old299 build/artifacts were retained.
DTS/config/TCPM core/DWC3/gadget/adbd/roles/SM5440 hardware/thermal/4.44V/ordinary
input ceilings are unchanged; no HVC DCC restoration or container config loss.

This is a **compiled and host-tested fallback prerequisite**, not hardware PPS
acceptance or completed direct charging. The actual transport still cannot enter
PPS. Mock exit success is not hardware proof. Next implement owned PPS callback
and exact bounded RDO authorization for the future live consumer; retain genuine
ADC/OCP/PM gates. A separate physical registration can test PPS-capable fixed
classification and an idempotent kernel restoration with pump OFF and rollback,
without escalating charging power or replaying failed ADC-delay profiles.

**Active Stage3: NOT READY. Full wired charging port remains in progress.**
