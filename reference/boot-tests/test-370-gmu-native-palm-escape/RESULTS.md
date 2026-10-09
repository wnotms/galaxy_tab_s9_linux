# Test370 — bounded kernel/desktop and owner input acceptance PASS

One uniquely attributed Test331 -> corrected GMU/native-Escape boot,
78ec1906-4713-4837-9acc-fe245647d7cf ->
0cdf0b75-9334-46bb-adcf-8e2ea97c3517. Exact five partitions, candidate embedded
config/notes and181 module hashes/link layout passed. Only boot changed; original
vendor/init/dtbo/vbmeta unchanged. DCC off, ADSP offline, direct defaultN.

Text admission36.02s and normal GNOME63.75s passed with full raw kernel journals
and no detected new GPU/HFI/CPU/kernel fault or failed unit. Native palm service
loads both paired Wacom/FTS modules; GPU/GMU runtime PM suspended after real GDM
activity. These bounded observations do not prove permanent GPU/CPU reliability
or a single cause for historical faults. Test369 read-only STOP remains unchanged.

Owner replied “都通过，设备时间不正常” to login, Ctrl+Alt+T, plainEsc, Fn+Esc
grave, touch/drag and optional pen/palm checks. Native keyboard mapping is active
with only the interim XKB swap removed. No raw pen-pressure/side-button claim.
Final same-boot Wi-Fi snapshot/journal after owner unplug:77%31.6C/Good/
Discharging, GNOME+palm+SSH+adbd active, no new kernel fault. Leave normal GNOME
on this candidate; retain exact namespace370 modules/input/boot rollback.

Separate clock issue: timezoneAsia/Shanghai already correct, device dateSep30
versus trusted hostOct9, no NTP client available. Registered kernel/input scope
completed before any clock correction; preserve original source timestamps and
use monotonic timestamps/bootIDs for attribution. Clock repair is independent.

25 affected host tests PASS/0skip; exact existing ARM64 build/bundle reused, no
rebuild/full-suite/Actions. Stage37019files; exact unused369 Windows duplicate
removed,361-370 retention. No PPS/pump/current increase, USB helper, sensor runtime
or ADSP activation. USB permanent reconnect and SSC/rotation remain incomplete;
next use this exact accepted boot/config/notes for separate USB qualification.
