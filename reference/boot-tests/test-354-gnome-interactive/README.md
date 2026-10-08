# Test354 — interactive GNOME keyboard session

Owner asks to reopen the desktop and confirms password login in Test353. Start GDM once on the unchanged Test331 boot, check the first 10 seconds, then leave it active for manual use. No 60-second automatic shutdown. Restore the existing persistent /dev/null masks after starting, without --now: this blocks subsequent automatic startup while preserving this active session. Do not change default target.

No package/firmware/kernel/config/DT/module/charging change, flash, reboot, touch load, PPS or pump activation. Record boot/config/notes, battery and failed units once, then new journal and active session. Abort startup on identity/health/new kernel fault; stop GDM on activation failure and restore masks. No continuous monitoring is claimed after the initial observation. To end later: systemctl stop gdm.service; persistent masks already remain.

Test348 stays paused and unused. Desktop must be stopped and its rootfs delta included in fresh admission before future charging work. Existing charging return-to-TWRP endpoint is unchanged.

Tests/build executed: false for this registration; existing Test352/353 qualification reused, new one-shot Python syntax checked. No CI. Retired expired Test344 staging/boot/Image; source/config/DT/modules/raw retained, current331/348 protected.
