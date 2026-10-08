# Test362 — pen probed and captured, owner input acceptance pending

Registration ab638aa9 was pushed before one ordinary insmod. Same331 boot
25ff0ad0/config/notes, client6-0056 bound to wacom-wez01 and event5 classified
ID_INPUT_TABLET=1. Controller query firmware0x4018/maxX14752/maxY23603/
pressure4095; actual axes X0..23603/Y0..14752,resolution100 units/mm. No
query fallback/unexpected MPU, no new kernel fault/failed unit; GNOME/touch/
SSH normal,66%25.6C GoodDischarging. Taint remains12804; no force flags.
Initial five-second IRQ delta0 without pen interaction is not an input pass.

PID5264/start311022 is the live non-grabbing pen collector,600s maximum. The
initial live snapshot confirms same process/stateS, no terminal and0raw bytes.
Do not infer pen functionality from probe or restart merely because SSH ends.
Owner requested hover/tap/strokes/button/grid and finger after pen removal;
physical positioning, pressure/proximity events and release remain pending.
Sleep inhibitor is only for this bounded capture. Root original evidence is
/var/log/gts9-test362-pen; initial-device-files.tar.gz stores full boundary
kernel JSON, loader/I2C/input/IRQ/udev/taint commands and capture metadata.
A final evidence retrieval must include raw events and terminal state.

Only optional currentboot module under var/tmp was loaded. No flash/reboot/
firmware/config/DTS/charging/181dir/autoload change. Accepted FTS stub build
has no pen-proximity palm suppression; no claim that feature is complete.
No suspend/hot-unbind/tilt-calibration or long-duration acceptance. Existing
15affected tests/W1/29CRC qualification reused; results-only execution:false
for new tests/build/fullsuite/CI.3481200s grant unused; eventual331/TWRP and
fresh desktop-inactive charging admission including pen delta retained.
