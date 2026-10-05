# Test319 — one unchanged accepted311 normal reentry

Test318 candidate has not been deployed. Owner confirmed today's boot647d50c8
was a manual reboot. Its accepted311 embedded config/notes match, but the
bootloader appended the exact captured lpcharge profile instead of the accepted
normal command line. This is not an exemption for Test318. Test281 previously
demonstrated an ordinary unchanged PC warm reboot restoring normal boot args;
reuse that method, independently attributed to the current baseline.

Purpose: exactly one normal `systemctl reboot` of installed accepted311 on PC
USB. No flash, module replacement, BCB write, kernel/cmdline/config/charging/USB
change, PPS or pump ON. The actual incoming full command line is frozen in
registration.json and accepted only as this test's entry, never the endpoint.
No rollback is necessary because installed software is unchanged.

First recharge the real pack to20–<80%SOC,20–<38°C,3.5–<4.3V/Good/present;
then connect PC and establish Sink/Device/SDP/device NCM/ADB/Wi-Fi/WindowsCode0.
Read full baseline once: exact allfive partitions and181 paired modules,
config/notes/current incoming cmdline, real pack thermal, cached pumpOFF,
full boot-attributed kernel journal and boot list. No repeated hash loop.

Commit/push registration before the single reboot request. Keep boot history;
readiness≤150s with bounded read-only shell polling. Require one changed boot
ID uniquely attributed, exact NORMAL cmdline/config/notes, health/rescue and
no new kernel fault. One15s same-boot endpoint; this is not a reliability proof.
Any fault/extra boot/wrong args/missing evidence stops; no second reboot or
automatic repair. Preserve first failure and kernel evidence.

After completion, Test318 still requires its own fresh NORMAL preflight before
candidate boot/modules are installed. This does not activate the ADC diagnostic.
Reuse the frozen baseline classifiers; new identity/no-replay host tests only,
no kernel build/full host regression/Actions. Use explicit host_flow.py preflight
and run; import is offline.
