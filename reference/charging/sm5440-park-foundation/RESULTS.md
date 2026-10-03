# SM5440 PPS park/resume offline foundation

The prior terminal actuator stop could not serve the transaction core's PPS
refresh/retarget pause. Added distinct checked park/resume operations on the
existing register layer: actual OFF across native negotiation, new producer
budget generation, same attach/source/lease, newly acquired physical OFF VBUS
and zero IBUS, then checked ON and mandatory fresh post-ON monitoring.
ADC acquisition must follow the new native completion, including same-voltage
refresh; an earlier still-young sample is refused.

The bounded pause retains prepared settings/ENHIZ/watchdog. Current may only
fall, within existing 1.0–1.8A bounds; voltage stays within 8.2–10.5V. Original
bytes remain terminal cleanup targets. This does not authorize real PPS/pump
operation or expand fixed 5V/1.8A and 9V/1.5A policy.

An uncertain first OFF write/readback latches unknown mode and retained ownership,
with no hidden second OFF from cleanup. Other failures terminate once, preserving
first and cleanup errors. Resume cannot be retried; another successful cycle
needs a newly advanced native receipt. Pending ADC, changed generation/source,
expired watchdog/clock, PM, missing OCP qualification or invalid physical proof
refuse admission. No driver lock or sleep across negotiation/ADC waits.

88 affected actual-C tests PASS (no errors, failures or skips), including 12
new park test methods with every bus-transfer failure, persistent loss, stale
receipt/ADC, source/PM/epoch change, repeated successful cycles and reduced
current cleanup. Raw host output and coverage are in host.txt/host.json.
Two unlinked ARM64 objects compile with W=1 and sparse, exit0; only the known
unrelated upstream vDSO declaration warning. The six cached provider files,
98 Test317 sealed inputs and nine candidate/rollback artifacts remain exact.
Configuration and DTB diffs are empty. No Image/modules relink, full regression,
new Kbuild hook, TCPM core change or GitHub Actions.

Fedora ab123e7d's renegotiation sequence supplies the same-model cross-check;
Samsung register provenance is retained from the actuator audit. Native Linux
7.2-rc3 TCPM property setters own AMS/PD negotiation; existing TCPC token/generation
and switching-inhibit gates are unchanged. Excerpts/hashes are in source-audit.json.

This is compiled and host-tested offline code, not device-accepted direct charging.
Native worker integration, actual 100ms ADC/current/cutoff qualification, fixed
fallback and PM acceptance remain open; device software_ocp_verified remains false.
Test317 capture remains NOT EXECUTED and unconditional accepted311 rollback is
pending restored access/current owner IP and connection. No new physical result
is inferred from the powered-on report or empty ADB list. Full port NOT READY.
