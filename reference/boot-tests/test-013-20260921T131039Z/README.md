# Test 013 — power-off delay telemetry (2026-09-21T13:10:00Z)

Hypothesis: the state of storage and USB can be read from the delay before the
initramfs powers the tablet off, avoiding one-bit-per-test diagnostics:

    code  = 1*microSD + 2*SCSI(UFS) disk + 4*USB device controller
    delay = 20s + 10*code

Artifacts: `init_boot 2d1cad6b…`, `vendor_boot 197ec0fe…` (flashed and read
back); `boot 57a973a7…` unchanged; `vbmeta` untouched. Validator passed.

## Result

Owner timed the power-off at **60-70 seconds**, i.e. code 4 or 5:

| Bit | Meaning | Value |
|---|---|---|
| 1 | microSD device present | uncertain (60 s = no, 70 s = yes) |
| 2 | SCSI/UFS disk present | **no** |
| 4 | USB device controller present | **yes** |

So the TCSR clock fix did bring the USB controller up, and **mainline UFS does
not enumerate** on this board. The host-side USB monitor (started before test
012 and still running) recorded no `0525:a4a7` device, so a UDC exists while the
port never presents itself - the next hypothesis, and the reason for the
`dr_mode = "peripheral"` change in test 014.

No ring capture: it cannot retain mainline output (test 007).
