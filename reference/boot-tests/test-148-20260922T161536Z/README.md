# test-148 — the hotplug fix works on hardware: detach, hot reconnect, handshake, keys

Build `boot.img c12590a8` (stock-style detach, hot reconnect, bounded handshake retry).
The owner ran a physical unplug/replug cycle and this is the device's own log, in order:

```
[57.42] key 0x39 released (from the MCU packet)          <- keys working before the cycle
[58.84] pogo: connect line reads 0 (was 1) after the 250 ms check
[58.85] pogo: confirmed detach (connect line 0)
[58.86] pogo: DATA IRQ disabled
[58.87] pogo: rail off, state=DETACHED                   <- the rail really goes down
[61.27] pogo: connect line reads 1 (was 0) after the 250 ms check
[61.34] pogo: hot reconnect: rail on, DATA armed, no reset (stock model)
[61.49] MCU model 0x1 hw 0 firmware 1.4 mode 1           <- handshake completed, no reset
[62.46] key 0x39 pressed (from the MCU packet)           <- keys work again
[62.60] key 0x39 released (from the MCU packet)
[62.77] key 0x39 pressed (from the MCU packet)
[62.85] key 0x39 released (from the MCU packet)
[62.99] key 0x39 pressed (from the MCU packet)
[63.05] key 0x39 released (from the MCU packet)
[65.40] pogo: connect line reads 0 (was 1) after the 250 ms check
[65.41] pogo: confirmed detach (connect line 0)
[65.42] pogo: DATA IRQ disabled
[65.43] pogo: rail off, state=DETACHED                   <- a second cycle, caught mid-test
```

While the cover was off, the state attribute read:

```
state=DETACHED powered=0 event_enabled=0 irq_armed=0 ready=0 connect=0 announce=0
announcements=14 regulator_enabled=0
```

That is the section 18 criterion demonstrated end to end: on detach the rail is off and
`regulator_enabled` is 0 (the fixed regulator's GPIO is pad 10, so the pad is low), the data
interrupt is disabled, `ready` is cleared; on re-attach the rail comes back, DATA is armed
with no NRST pulse and no bootloader access, the application announces and answers the
verified handshake (`MCU model 0x1 hw 0 firmware 1.4 mode 1`), and real key events follow.
Two detach cycles appear in this log and keys worked after the reconnect in between.

## Still owed for the owner's section 21

- five consecutive cycles in one run (this log shows two detaches and one completed
  reconnect, with keys working after it),
- the three-to-five-minute idle run,
- a pad-level reading taken while the cover is off, to go with `regulator_enabled=0`.
