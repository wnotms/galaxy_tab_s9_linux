# Test330 — first Fedora PPS 1.8 A short acceptance

New independent execution after Test328 host-only command-line whitespace stop.
Same source376693d7, buildf105ffed, opt-inbootc064e61a, config/notes/DTB and181
modules. Same device-local Test328 guard, unchanged thresholds/cleanup. No new
kernel build, driver/config/DTS/ADC/power policy change or current escalation.

Only corrected host identity: require one exact opt-in and Y parameter, remove
that token, compare the entire remaining ordered token sequence including all
duplicates with the recorded baseline. Only separators are insignificant;
changed/missing/extra/reordered parameters, config/notes or identity still fail.
Original Test328 raw/error/rollback remain intact; it was not a PPS pass.

Pushed registration → exact52%/healthy PC/Wi-Fi/Windows/181/OFF preflight →
boot-only TWRP install/readback → unique healthy PCboot/OFF → guard armed →
owner C1alone/C2empty → bounded30s PPS1.8A → checked worker unbind/OFF/fixed9
fallback → ownerPCreturn → unconditional Test327defaultOFF boot restore. Any
first real PPS/safety fault: no retry, exact323boot/saved327original181 restore.
No5min/20min/higher-current test or permanent opt-in retention.

All detailed source, entry20–<80%/pack20–<38C/VBAT<4.3V, live<42C/VBAT<4.4V/
die<85C/physicalIBUS<=1.8A/VBUS7.7–10.5V/requestmatch, wait240s, refreshOFF<=2s,
full source-timestamp journals and firstfault/rescue rules in the frozen Test328
README/registration apply unchanged. No independent ADC calibration/power-meter
claim or45W acceptance. Rootfs/ADB/gadget/DWC3 untouched. Guardian finally stops
worker and proves OFF/fixed9/switching<=1.5A; source unplug immediately on
unknownOFF/lostrescue, then PC/TWRP recovery. Full port remains NOT_READY.
