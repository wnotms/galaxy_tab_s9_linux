# Test348 offline registration results

Status: REGISTERED_OFFLINE_PENDING_PHYSICAL_AUTHORIZATION. No device commands,
Windows staging, flash, reboot, PPS request or pump activation were performed.
Device remains in TWRP with exact Test331 and its original 181 module files,
as recorded by the completed Test347 restoration. Twenty-minute hardware
acceptance has not occurred; the full charging port remains NOT_READY.

49 affected host tests passed in 0.643s: 33 deployment/registration/restoration,
11 duration parser and 5 Windows transport cases. Python AST and shell syntax
checks passed; PACKAGE artifact sizes and SHA-256 all match. Initial mock-only
failures are preserved separately, with corrected deadline and restoration
folder fixtures. The final mock exercises 1200 seconds, not the old 300s window.

No kernel build or full regression was rerun (executed: false). Reuse the
unchanged 0b731b4a qualification: 167 affected tests, ARM64/modules build and
W=1/sparse passed, exact Test331 config/DT/release and protected inputs retained.
Only offline armed boot packaging adds the separately registered 1200000ms
one-shot flags; no hardware current, voltage, thermal or fault gate changes.

The independent runner uses SOC <=60% for preparation/activation (natural
headroom target58%), native1200s/guardian1260s/hostmonitor1300s/outer1500s.
Fault and transport deadlines remain unchanged. It requires a fresh explicit
physical scope and candidate-bound C1 reply, permits one launch only, and
retains the original process after host observation timeout. Restoration ends
with verified exact331/allfive/181 and unmounted Debian in TWRP, without a
restored Debian reboot or runtime acceptance.

The Test339–348 retention window expired Test338. Nine verified obsolete
image/transfer files totaling371499694 bytes were deleted; current331,
qualified candidates, source/config/DT/modules and raw evidence were retained.
See retention-check.json. ADB tooling remains under D:\android\platform-tools.
