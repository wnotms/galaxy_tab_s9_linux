# Test360 — installed driver loads on new boot; visible UI pending

Owner manual331 boot25ff0ad0 was in text mode with touch absent. Starting GDM
once triggered its enabled Wants touch unit **without a separate manual
insmod**. Service verdict loaded/1insmod, ordinary kernel loader return0; the
existing7-0049/input4/event4 bound, doubletap remained0. Final readonly status
already-loaded. All3persistent GDM masks were restored without --now; desktop
and driver remain active for owner login/touch confirmation. This validates
GDM-triggered installed loading in an actual new boot, not automatic graphical
startup (which remains deliberately masked) or suspend/Spen/doubletap.

10s startup observation: sameboot/SSH/GDM active/zero failedunit. Kernel journal
1104->1111 records; seven added touch/GPU startup messages, zero new recorded
severe fault. O/E signature/outoftree warnings and taint516->12804 match the
accepted357 normal unsigned external load; no signature/version/BTF bypass.
Full original journal, input/commands/service/GDM logs and hashes preserved.

For the owner's heat question, read-only snapshots span11.649monotonic seconds:
pack25.4°C before/after,73%,Good/Discharging. GPU uses simple_ondemand and final
frequency220MHz (minimum), so this sample does not show it stuck at maximum.
CPU uses schedutil; CPU7 reports2.9568GHz before/after even before GUI. Cached
frequency alone does not prove sustained active CPU or locate heat. These
startup samples do not establish long-term temperature stability, SoC/surface
heat or the cause of the owner's observation. Next separate idle/ordinary-use
analysis should prioritize background rendering, screen settings and optional
GNOME animations; do not change OPP/governors/thermal/charging limits here.

No rebuild/fullsuite/CI:17loader+8actualC/W1/37CRC inputs unchanged and reused;
results-only tests/build executed:false. No package/kernel/config/DT/181 module
change, firmware update, USB/ADB/charging change, flash or reboot command.
3481200s grant unused; fresh desktop-inactive admission/final331TWRP remain.
Owner new-boot visual login/touch confirmation is pending; previous357 physical
coordinate acceptance is not silently substituted for this new UI observation.
