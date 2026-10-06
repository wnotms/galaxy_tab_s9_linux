# Test326 — installed; awaiting one owner fixed9V boot

Candidate f338eeb3 / ee59e368 qualification installed via TWRP. Boot and all five
partition readbacks match; 181 paired modules verified. BCB cleared and Debian
root unmounted. No automatic candidate boot was issued. Device is in TWRP,
rollback_required=true; exact accepted323 modules saved as .gts9-test326-original.

Owner must replace PC with Lenovo C2 (18W, C1 empty), choose Reboot System once,
wait >=30s after Debian login, then return to PC without reboot. Capture original
retained ADC/boot/kernel evidence once, then unconditionally restore exact323
boot/modules in finally. No repeat/rebind/PPS/pump/current/protection/USB change.

Build/tests executed:false for installation; unchanged ee59e368 kernel/artifact
qualification and registered 22 packet/parser tests reused. Full port NOT READY.
