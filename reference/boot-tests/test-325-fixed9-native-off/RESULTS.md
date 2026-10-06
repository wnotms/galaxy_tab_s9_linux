# Test325 — stopped before native acquisition; accepted323 restored

The original capture stopped on duplicate @@boot-end sections. Raw packet is
preserved. Both closing boot IDs and leading ID are identical; analysis removes
only the redundant early pair in a separate derived file, not the original
runner/result. Normal candidate/config/notes and unique boot history match.

Device evidence: initial OFF sample 9.437V, VBAT4.0795V, IBUS0, die28C,
INT00/00/62/00 vs liveSTATUS00/00/20/00. Gauge4.160V, gap80.5mV; no calibration.
Diagnostic admission retained initial inactiveREVBLK and set confirmations=2,
but the later generic sample-fault block still called only the ordinaryPC
classifier. It immediately set fault=true, preventing requeue/confirmations.
No native request ran (attempt0/count0); this does not prove100ms timeout.
This is a missing diagnostic dispatch in new source80d590f0; isolated predicate
tests were insufficient to cover the full worker. Old tests were not weakened.

Full kernelJSON/source times/raw retained. No detected CPU-stall/panic signature;
known startup display/SMMU context variants are separately counted. No second
candidateboot/rebind/replay/PPS/pump/current/protection/USB change. Registered
finally restored exact323 boot/original181/allfive, clearedBCB/unmounted and one
normal boot; ADB/NCM/hostNCM/Wi-Fi checked. Final abc27877 normal,70%4.127V29.3C,
rollback_required=false. Existing ordinary passive refusal remains separate.

Next: fix diagnostic dispatch in BOTH initial admission and generic fault block,
and replay the actual full worker through two fresh confirmations plus terminal
fault/PM cases. Remove duplicate closing marker in a NEW registration; do not
rewrite Test325 capture asPASS. Unchangedbuild/158kernel and32host qualification
reused, build/tests executed:false for this results stage. FullportNOTREADY.
