# Test354 — interactive desktop opened

One GDM start succeeded on unchanged Test331 boot be1baaaa-47fc-41f5-8255-8f7092c01653. Initial 10.294-second observation: GDM active, Wi-Fi SSH responsive, no new kernel fault, no failed system unit, no render-permission/software-fallback signature. Battery 86%, 32.2°C, Good/Discharging. Raw command outputs/journals are preserved in raw-gdm.tar.gz with hash.

Desktop is left **active for owner keyboard use**, with no automatic 60-second shutdown. All three existing persistent masks were restored without --now, preventing future automatic startup while preserving this session. This is an initial opening check, not ongoing monitoring or a long-duration acceptance. Test353 already contains owner-confirmed keyboard/password login; no new visible-screen result is fabricated for Test354.

No flash/reboot, kernel/config/DT/module/charging change, package installation, PPS/pump activation or touch load. Charging Test348 remains paused and unused; its eventual fresh admission requires GDM stopped. Test348's original final TWRP endpoint remains unchanged.

Host suites and kernel build executed: false. Python syntax and raw evidence SHA checked; existing unchanged source qualification reused. To end this interactive session later: systemctl stop gdm.service.
