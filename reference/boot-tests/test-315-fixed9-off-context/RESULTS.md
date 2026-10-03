# Test315 — fixed9 source-bound OFF context

Verdict: **FIXED9_OFF_CONTEXT_OFFLINE_QUALIFIED_NOT_DEPLOYED**.
Full direct-charge port: **NOT READY**. Source `30cf862a8dbacb1a2cba373ae163c555f64a1cec`.
Accepted311 ordinary kernel remains installed; no physical315 command, flash,
reboot, partition/module replacement, PPS request or pump enable occurred.

The actual one-shot diagnostic worker now refuses PC5V/PPS before converter or
switching writes. It checks real fixed9 source/instance/budget epochs, standard
pack presence/health/SOC5..<80/VBAT3.5..<4.3V/temp20..<38C and actual OFF
VBUS8.5..9.5V/zeroIBUS/die22.5..<42C. An initial exact inactive REVBLK retains
its raw event and needs two new fault-free unchanged-setting samples. Live,
repeated or different faults stop. Oldest500ms ADC age is rechecked after slow
supplier calls; it remains diagnostic ONLY, never a100ms active/release grant.

Uses real checked SM5714 switching acquire (Q4 OFF/min100mA), then new physical
measurement and the Test314 regmap settings at actual fixed budget<=1500mA.
Live STATUS is captured before ENHIZ changes. Exact ADC-off/ENHIZ/settings
restore keeps pending, first operation error and cleanup error; PM/remove drain
before their bounded cleanup. Raw readings, timing, controls/witnesses/lease
are available in read-only debugfs; no core charger/TCPC lock across a wait.
The lease stays inhibited even after a successful comparison: no fabricated
freshness, looser release or stale-cache charging authorization. A future physical
registration must unconditionally restore exact accepted311 after capture.

122 affected actual-C/profile/source tests PASS in 1.632s, no
failure/error/skip. Includes every coordinator bus failure, uncertain cleanup,
source/physical/pack/thermal/PM/lease faults, pre/post live STATUS, inactive-latch
confirmation, delayed suppliers and malformed gauge integers. All old tests
retained; condition fixture indices account for the added pre-status read.
Default preprocessed driver paths and existing converter/teardown are unchanged.
No full regression, test routing change or GitHub Actions.

Standard8-job pinned ARM64 Image/DTB/modules build PASS 86.218s.
W1/sparse actual two objects exit0; no changed-driver warning; known upstream
vDSO missing declaration and config-seed warnings retained. Initial static
object-equality guard failed and is NOT presented as a pass: W1 objects differed
from standard objects, while vmlinux was unchanged. A seeded CHECK retained the
same W1 hashes. Restoring only the two standard objects (6.057s)
reproduced exact qualified build hashes and reproducible compile identity;
vmlinux/Image/modules remained unchanged. No second full build or host rerun.
Raw original guard failures and both invocations remain in validation.

Exact accepted311 config diff: only CONFIG_SM5440_ADC_CONDITION_TEST n->y.
Unexpected delta empty, existing X710 policy remains n. DCC remains n; Docker/
UPower USER_NS/mqueue and SM5714/ADC5Gen3 retain resolved values. DTB identical,
96 protected files unchanged,12 compiled overlays match source, embedded config
exact, notes/181 matching module hashes and deterministic archive retained.
SM5714 fixed5V1.8A/fixed9V1.5A/float4.44V/thermal policy unchanged; no DTS/TCPM
core/DWC3/gadget/adbd/rootfs/OPP or active protection-mask/reset modification.

Before reusing the one incremental cache, formal314 artifacts and symbols/79
CRC/config/generated inputs were frozen and verified. Cache is now315 diagnostic
provider, not314 policy provider; formal314 and accepted308 remain unchanged.
Window306-315 cleanup removed4 expired305 Image/boot files (193656116 bytes),
without moving/archive evasion. Source/config/DTB/modules/raw logs/debug retained.
No new complete build tree or Windows staging copy.

Next separate physical test needs fixed9 charger attached before the single boot
worker, fresh safe pack/Wi-Fi rescue, raw pre/post STATUS and unconditional
accepted311 rollback. Do not replay old PC5V Test313 or claim9V cures REVBLK.
This is offline source-bound preparation, not physical ADC calibration, PPS,
software OCP/watchdog, pump ON, runtime fallback/PM or full charging acceptance.
