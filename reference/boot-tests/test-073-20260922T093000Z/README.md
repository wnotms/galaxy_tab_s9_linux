# test-073 — the connect line is pulsed, not floating: the MCU looks like it is resetting

- started: 2026-09-22T09:30:00Z
- source commit: the bias change (`dts: bias the announce and connect lines high,
  as stock observes them`)
- images: `boot.img 2a84a835…`, `vendor_boot.img 3ec6c8d1…` (new DTB);
  `init_boot aed8f3c5…` (firmware-carrying initramfs), `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-072

## Hypothesis

Test 072 reproduced stock's complete firmware path with the vendor driver but the
driver still never reached `stm32_read_version`, because the connect line
oscillates and its state machine therefore alternates
`keyboard_start`/`keyboard_stop`. Stock reads `con:1/1` steadily with the same pin
configuration, so a pull-up should reproduce that level and let the state machine
reach the application read.

## Result — the pull-up changed nothing, and that is the finding

```
22.287646 stm32_conn_isr (1)
24.322055 stm32_conn_isr (0) / (1) / (0)
24.469856 stm32_keyboard_connect: 0
24.566078 stm32_check_conn_work: con:0, current:1
24.575512 stm32_keyboard_connect: 1
26.592817 ... the same burst two seconds later
```

The line still reads 0 in bursts every ~2 s. A bias cannot be overridden by
nothing: `conn_isr (0)` means the pin really was low at that moment, so something
**actively pulls it low about twice a second-ish**, and it is not floating drift
as the earlier tests assumed.

The most consistent explanation of everything measured so far is that under
mainline **the MCU is resetting in a loop**:

* a periodic low pulse on the line the application drives while it runs;
* `0x2a` never answering, because a part that resets every ~2 s never brings its
  I2C slave up;
* the announce line also behaving erratically (levels 1 then 0 within 130 ms,
  test 067/068) instead of the steady high stock reports;
* and the system bootloader answering perfectly whenever the driver's SWCLK dance
  puts the part into boot mode, where no application watchdog runs.

Stock's application, on the same part with the same rail and pins, runs stably
for minutes at a time (its status lines repeat unchanged at 33 s, 64 s, 95 s, …).

## Next step

Stop treating the pulses as a line-level question and measure the MCU's own reset
behaviour: the two signals that describe it are NRST (gpio13, which the driver
leaves released) and the rail (gpio10), and the part itself can be asked - a
bootloader probe immediately after a pulse would show whether it is in boot mode
each time it comes back. If the MCU is reset-looping, the cause is in what the
application sees at startup under mainline, and the vendor driver's now-complete
firmware path gives a faithful reference for the startup sequence it expects.
