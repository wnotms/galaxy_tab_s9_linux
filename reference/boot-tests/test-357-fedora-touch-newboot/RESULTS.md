# Test357 — ordinary touchscreen functional acceptance

Fedora X710 ab123e7d FTS1BA90A driver is byte-identical and loaded once on exact331 boot1adc0f13-a210-4856-bb15-c6e9df17867a. Normal kernel loader accepted the module after all37 consumed export CRCs (including module_layout) matched the exact running Image/config/notes. Existing DT client7-0049 bound; input event4/udev touchscreen property/landscape axes X0..2559,Y0..1599 verified. Module remains outside the original181-module directory, in /var/tmp only; no persistent autoload or kernel image change.

Owner confirmed “触摸位置、方向正确，桌面正常” after requested corners/center, drag/scroll and two-finger use. Non-grabbing raw recording:191.244s,12777 events,2113 SYN frames,113 contact starts/112 releases at reader stop, maximum2 simultaneous contacts. Recorded coordinates X42..2486,Y1..1541 stay within transformed bounds. Reader stopped while slot0 still active; a subsequent EVIOCGMTSLOTS snapshot shows all10 IDs=-1, no remaining active slot. This confirms release after recording, not a fictitious zero-contact end snapshot. Raw binary24-byte records match JSON exactly with no trailing bytes.

Fresh authenticated sameboot/GDM remained responsive, zero failed system unit or new serious kernel signature in full final journal. Pack80%,32.8°C,Good/Discharging. Initial5sIRQdelta126; no IRQ storm observed. External unsigned-module warning is preserved: taint516→12804 adds only unsigned/out-of-tree bits; production SIG_FORCE=n. No signature/version/BTF bypass, no forced loading. Full raw journal/events/command evidence in raw-touch.tar.gz and SHA identity.

The sole capturePID3294 was verified live by startticks, then stopped by its owned marker after owner reply; terminal confirms host_requested_after_owner_result. No restart on timeout; sleep inhibitor lifetime ends with collector. GNOME and touch module stay active. No unload, firmware update, S Pen, double-tap, suspend/resume, ten-contact or long-duration reliability acceptance is claimed.

No flash/reboot/config/DT/charging/GPU/USB/ADB service change. Test356 power-key correction remains accepted; original355stop and354functional result retained. Test348's authorized1200s scope is still unused, full charging acceptance incomplete; fresh desktop-inactive admission/rootfs delta and eventual exact331/TWRP endpoint preserved.

Qualification: existing8 actual-C decoder tests and W=1 build reused unchanged; new exact331 CRC replay passed. Tests/build executed:false for this results-only update; raw hashes/summary consistency/protected-file diff checked, no CI.
