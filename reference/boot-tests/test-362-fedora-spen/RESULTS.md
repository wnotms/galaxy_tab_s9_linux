# Test362 — pen controller enumerated; no physical pen input observed

Registration ab638aa9 was pushed before one ordinary insmod. Same331 boot
25ff0ad0/config/notes, client6-0056 bound to wacom-wez01 and event5 classified
ID_INPUT_TABLET=1. Controller query firmware0x4018/maxX14752/maxY23603/
pressure4095; actual axes X0..23603/Y0..14752,resolution100 units/mm. No
query fallback/unexpected MPU, no new kernel fault/failed unit; GNOME/touch/
SSH normal,66%25.6C GoodDischarging. Taint remains12804; no force flags.
Initial five-second IRQ delta0 without pen interaction is not an input pass.

PID5264/start311022 was the live non-grabbing pen collector for600.606s. It
ended at its registered deadline with reason `deadline`,0 events,0 frames and
0 trailing bytes. The owner did not provide pen interaction during the window,
so this is an incomplete physical-input observation, not a driver failure or a
pass. Do not infer pen functionality from probe or absence of SSH.
Owner hover/tap/strokes/button/grid and finger-after-removal acceptance remain
pending for a future fresh boot scope. Sleep inhibitor was only for this
bounded capture. Root original evidence is /var/log/gts9-test362-pen;
initial-device-files.tar.gz stores the boundary evidence and
final-device-files.tar.gz stores terminal state and the final health check.

Only optional currentboot module under var/tmp was loaded. No flash/reboot/
firmware/config/DTS/charging/181dir/autoload change. Accepted FTS stub build
has no pen-proximity palm suppression; no claim that feature is complete.
No suspend/hot-unbind/tilt-calibration or long-duration input acceptance.
Existing15 affected tests/W1/29CRC qualification reused; no new host tests,
kernel build, fullsuite or CI. Test3481200s grant unused; eventual331/TWRP and
fresh desktop-inactive charging admission including pen delta retained.
