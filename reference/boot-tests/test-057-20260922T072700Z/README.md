# test-057 — the bus-silence candidate (result never captured)

- started: 2026-09-22T07:27:00Z
- source commit: `e13f667` ("pogo: leave the bus silent before the first poll")
- images: `boot.img e087592f…`; init_boot/vendor_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-056

## What it tested

Whether the application's I2C slave latches an error from traffic it sees while
it is still starting: `connect_work` left the bus alone for 30 s after the MCU's
power-up before the first poll, instead of polling every 250 ms from ~4 s.

## Result — not captured

The candidate was flashed and verified on the device (`boot` read-back
`e087592f…`), but by the time the console was queried the tablet had already
returned to recovery and the CDC-ACM console was gone, so no log from this boot
exists. The candidate was superseded by tests 058 and 060, which measure the same
question with a defined window and with side-effect-free polling, and was
reverted in `e2db2ed` because it did not belong to the P0 hypothesis.

Its one lasting contribution is procedural: a candidate whose result is not
captured is recorded as such rather than dropped, and the flash/read-back
transcript below is the only evidence it ran.
