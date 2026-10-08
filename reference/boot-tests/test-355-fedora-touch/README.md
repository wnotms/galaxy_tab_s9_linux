# Test355 — Fedora X710 ordinary touchscreen

Reuse the byte-identical Fedora X710 FTS1BA90A module already compiled with W=1 and eight actual-C decoder tests. No kernel rebuild/flash/DT/config/charging change. The new compatibility gate reads the exact331 Image exports at runtime-reported section addresses, validates sorted PREL32 entries, and compares all 37 consumed CRCs including module_layout. Matching vermagic alone is insufficient. The normal loader must still accept version, signature and distilled BTF.base; no bypass or retry.

Load once from /var/tmp outside the accepted 181-module directory. The existing actual client is 7-0049 (charger's 2-0049 is unrelated); firmware stays factory-flashed. Verify IRQ/input/udev, five-second IRQ rate, full journal boundaries, current identity/health and active GDM. Raw non-grabbing evdev recording lasts up to 900s with a sleep inhibitor only while it runs. Capture process identity is saved for re-polling, never restarted on observation timeout.

Owner acceptance: tap corners/center; drag across the panel; use two fingers in Settings; then confirm direction, accuracy and GNOME responsiveness. Ten-contact limits, edge accuracy, screen keyboard, S Pen, double-tap wake and suspend/resume require their own evidence and are not inferred. Leave GDM and successfully loaded module active for normal owner touch testing; no permanent autoload yet.

First anomaly stops further experiments: preserve failure/raw journal, no forced unload, rail cycle, scan or automatic reboot. First physical probe is not qualification for remove/suspend. No partition rollback needed; conservative fixed charging remains unchanged. The Test348 charging grant stays unused; its next fresh admission must account for this rootfs/runtime delta and desktop inactive. Its eventual exact331/TWRP endpoint remains unchanged.

Validation: eight affected decoder tests pass; pairing gate pass; one-shot Python syntax reviewed. Existing external-module W=1 build reused. Kernel rebuild/full suite executed:false, no routing/input change and no CI. Expired345 images/stage retired; current331/348 and raw/source/config/DT/modules preserved.
