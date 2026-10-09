# Test371 — bounded PC USB lifecycle PASS

One actual PC attachment → unplug → reattachment cycle passed on the accepted
Test370 kernel/native inputs/GNOME. Owner-confirmed manual boot d1977159-8330-4c90-
b5be-e7cf8c67ea0f was enrolled before the first formal attempt, Wi-Fi10.49.219.156.
The earlier unstarted enrollment and transport timeout are preserved; no failed
physical attempt was retried. No static Wi-Fi change.

First PC30s and final PC30s both recovered actual ADB shell (machine/boot matched)
and device NCM169.254.42.1, Windows PnP no Code43. Unplug15s showed normal negative
battery current/Discharging, exactly one additional unbind. Lifecycle events
were exactly unbind/bind/unbind/bind; no repeated healthy reset, adbd restart or
role change. Full boot kernel and unit JSON/source timestamps retained at every
boundary; no detected new HFI/CPU/panic/unclassified kernel fault or failed unit.

Two exact empty-ep0 dequeue diagnostics (initial detached and physical unplug)
were uniquely attributed to owned unbinds within the frozen250ms source timestamp
window. Raw parser classification still says pending transport gate; both real
transport gates now passed. Diagnostics are retained, not erased, and do not
prove all historical USB failures share this source.

After acceptance the bounded transient was stopped, original UDC binding read
back, and the three ledger-owned files removed/hash-verified. Same boot/config/
notes and desktop/rescue health retained. Cleanup status rolled_back means the
userspace test payloads were removed, not a kernel rollback. Current accepted
Test370 kernel/native inputs/GNOME remain installed. No flash/reboot/modules/
DTS/USB driver/charging current/PPS/pump/ADSP change.

77 affected host tests qualified; actual371 transaction24 cases rerun after
pre-start enrollment, remaining53 exact unchanged source qualification reused.
Results-only tests/build executed:false. No full regression or CI/Actions.
No images produced; retention362–371 unchanged, active370+original331 rollback
retained. Evidence hashes EVIDENCE_SHA256.json; exact windows/health summary.json.

This validates one bounded PC cable cycle. Persistent enablement, reboot startup
and charger→PC recovery remain separate scopes. Next apply the qualified helper
with a separate recorded persistent deployment, then resume SSC/sensor work.
