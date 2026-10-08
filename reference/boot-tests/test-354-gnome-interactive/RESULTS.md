# Test354 — owner-confirmed functional GNOME keyboard session

One GDM start succeeded on unchanged Test331 boot be1baaaa-47fc-41f5-8255-8f7092c01653. Initial 10.294-second observation: GDM active, Wi-Fi SSH responsive, no new kernel fault, no failed system unit, no render-permission/software-fallback signature. Battery 86%, 32.2°C, Good/Discharging. Raw command outputs/journals are preserved in raw-gdm.tar.gz with hash.

Desktop is left **active for owner keyboard use**, with no automatic 60-second shutdown. All three existing persistent masks were restored without --now, preventing future automatic startup while preserving this session. This is an initial opening check, not ongoing monitoring or a long-duration acceptance. Test353 contains owner-confirmed keyboard/password login. For Test354 the owner subsequently reported “已测试，功能正常”; record this as manual desktop functionality confirmation. No additional feature-by-feature result, touch acceptance or long-duration reliability claim is inferred.

No flash/reboot, kernel/config/DT/module/charging change, package installation, PPS/pump activation or touch load. Charging Test348 remains paused and unused; its eventual fresh admission requires GDM stopped. Test348's original final TWRP endpoint remains unchanged.

Host suites and kernel build executed: false. Python syntax and raw evidence SHA checked; existing unchanged source qualification reused. To end this interactive session later: systemctl stop gdm.service.

Owner confirmation was recorded without further device operations. The desktop was left active by the preceding activation; this update does not stop it, change automatic startup, or resume charging Test348.

Subsequent incident: the owner reported poweroff before Test355 loaded touch. Test355 separately preserves the prior boot's power-key/GNOME VM-policy/orderly shutdown evidence. This ends the active desktop session; manual functional confirmation is retained, but it is not a power-key regression pass. The new boot starts with GDM masked/inactive.
