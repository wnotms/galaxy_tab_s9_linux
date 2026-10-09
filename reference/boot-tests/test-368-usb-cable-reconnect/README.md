# Test368 — bounded USB cable reconnect

Independent follow-up to Test367 STOP; old evidence/runner unchanged. Reuse its
qualified exact three-file transaction and unchanged lifecycle/adbd source.
The only runtime runner fix is loading frozen helper source without generating
an untracked helper bytecode cache. Normal GNOME/interim XKB remain unchanged;
native Escape will be included in the next kernel test. No kernel build/flash,
reboot, SSC, DT/module/adbd/descriptor/charging change, PPS or pump activation.

Purpose: test one same-boot PC reconnect cycle with event-driven, stable1s
Type-C/configfs lifecycle management, avoiding repeated manual resets. Exact
Test331 boot/machine/config/notes and raw existing error counts are frozen.
Old GMU and both historical ep0 errors remain open evidence, not a clean-boot
claim. The source-bounded teardown classifier is documented in
[the audit](../../../docs/USB_EP0_TEARDOWN_AUDIT.md), source-audit.json and
registration.json. Full logs remain evidence; no kernel log is suppressed.

Sequence: fresh read-only preflight while physically unplugged; commit/push
registration and affected tests; install three initially absent files with
durable ledger; start transient368 unit once/1200s backstop/no restart/no enable;
confirm one initial unbind; PC attach30s with one bind/ADB shell/device NCM;
unplug15s with one unbind/normal discharge; reattach30s with one bind/ADB/NCM.
Capture full kernel/unit JSON and Windows PnP at boundaries. Device completion
is primary; host NCM TCP is a separate observation. No pressure discharge.

Safety: SOC20..100 only for this non-flashing same-boot scope, Good/present,
temperature10..<42°C and actual VBAT3.4..<4.44V. Old sensor flash20..85 gate
unchanged. Sink/Device/DCCoff/directdisabled/GNOME/Wi-Fi remain required.

Stop on first unclassified new priority<=3 kernel error, CPU/panic/stall,
unbounded/ambiguous/repeated ep0 diagnostic, Code43, lost rescue/evidence,
new failed unit, identity/layout/roles drift or repeated binding action. Record
first failure before cleanup; no retry or second start. Stop transient service,
read back its restored original binding, remove only exact ledger-owned files
and temporary copies. Reject unknown edits; retain ledger/raw evidence. No
partition rollback needed. SIGKILL/hung kernel write cannot be guaranteed;
never silently adopt an unknown empty UDC or blind reboot.

Persistent enablement is a later recorded change only after actual physical
qualification. These bounded observations do not prove long-term reliability,
charger→PC, suspend or a root cause for all USB incidents. Sensors/rotation/full
port unfinished; no charging-current expansion. No Actions or test-routing
change; rebuild not needed because all kernel/build inputs stay unchanged.
