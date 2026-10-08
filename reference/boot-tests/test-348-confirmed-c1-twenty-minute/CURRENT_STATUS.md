# Test348 execution status

**STOP_FIRST_NON_CLEAN**. One activation only; no retry. Native raw input
current reached 1,811,875 µA against the registered 1,800,000 µA ceiling,
1196.693 seconds after the pump-start log. Temperature at the native stop:
pack 27.5°C, die 42.5°C; ADC VBAT 4.0995 V and VBUS 8.718 V.

Native stop reports primary -34, cleanup 0, lease 0, no restart. Fixed return
verified physical VBUS 9.283 V, zero raw input and pump OFF. Guardian cleanup
also confirms OFF/unbound/fixed 9V, with no cleanup error. Raw evidence and
full kernel journal have been retrieved; collection correctly says STOP.

Exact Test331 boot plus original 181 modules restored; all five partitions
verified, root unmounted and TWRP endpoint confirmed. Owner subsequently
changed the endpoint to normal Debian: see `OWNER_ENDPOINT_UPDATE.md` and
`owner-endpoint-update.json`. Registered ordinary return completed: restored boot ba4d8404 is attributed;
exact config/notes/all-five/181, DCC absence, ADB/NCM/trusted Wi-Fi and kernel
health passed. Final endpoint is Debian, Wi-Fi 10.175.236.100. No new PPS
attempt or current ceiling change is authorized by this update.

Tests/build for these results: `executed: false`; frozen qualified inputs
unchanged. Detailed results and verified raw archive/index are in RESULTS.md and summary.json.
