# test-145 — the stock-style detach/reconnect machine runs; the physical test is still owed

State: `boot.img a19a5cbb` (detach + hot reconnect), flashed and read back.  The owner has
not yet performed the physical unplug/replug, so nothing here claims the hotplug fix
works; what follows is what could be verified without touching the cover, plus one
correction to an earlier claim of mine.

## Verified

- The rail helper is idempotent in practice: `echo soft` three times in a row leaves
  `regulator_enabled=1`, `irq_armed=1`, `powered=1`.  Three writes did not accumulate the
  regulator's enable count and did not add a second enable_irq.
- No warning in the log comes from this driver: the three matches for
  `unbalanced|Disabling IRQ|WARNING` are boot-time and older - the kernel's x1-x3 boot
  protocol warning, `clk-rcg2.c:136` and `base/core.c:1020`.  Nothing from
  keyboard-samsung-pogo.
- The new state machine does fire on its own: `pogo: hot reconnect: rail on, DATA armed,
  no reset (stock model)` appears at 50.24 s, i.e. the 250 ms state check saw an attach
  transition and took the stock path with no reset and no rail drop.

## Correction

I described `soft` as having no side effects on the MCU.  It does: the announcement count
went from 2 to 11 across those three writes and the handshake did not complete afterwards
(`ready=0`, `state=STARTING`, `keep-alive: GET_MODE NACKed (-71)`,
`event transfer failed: -6`).  `soft` is safe with respect to the regulator and the
interrupt - that is what the three writes above show - but it does re-raise the rail and
the application reacts to that.

## Owed: the owner's section 21 acceptance test

Five unplug/replug cycles followed by three to five minutes idle, then the five questions
answered from the log:

  why GPIO10 goes low on detach, why the driver brings it back on re-attach, why the hot
  path needs no NRST, why the enable/disable pair cannot unbalance, and why repeated
  cycles do not accumulate the regulator's enable count.

The evidence is already instrumented: `cat /sys/bus/i2c/devices/5-002a/rearm` prints
state/powered/event_enabled/irq_armed/ready/connect/announce/announcements/regulator_enabled,
and the driver logs `pogo: confirmed detach`, `pogo: DATA IRQ disabled`,
`pogo: rail off, state=DETACHED`, `pogo: connect line reads N (was M) after the 250 ms
check` and `pogo: hot reconnect: ...`.

At the time of writing the line reads `connect=0` with `powered=1`: a transition was in
flight when this was captured, so the next session must read the log before drawing any
conclusion from those numbers.
