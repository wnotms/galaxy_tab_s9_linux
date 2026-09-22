# test-107 — boot works, a hot re-seat does not: the state of that problem

Owner-verified outcome after test 106 (`boot.img c74e6725`): the keyboard works after
boot, and it stays usable, but unplugging and re-attaching it leaves it dead.

## What has been established about a hot re-seat

- The re-seat is a *physical* event that no host-side detector can be trusted to see:
  the connect line carries 1492-2431 edge interrupts per boot on this board, so it
  toggles at about 10 Hz even with the cover seated (tests 099-105).
- Re-arming on it is harmful: test 105 re-armed on every level change (rate-limited to
  10 s) and the owner saw no keys at all after boot - a working keyboard reset every ten
  seconds. Test 100 was the same failure from a 6 s poll threshold. Both are reverted;
  no automatic re-arm is triggered by the connect line or by silence any more.
- After a re-seat the part does come up at least once - test 104 counted 34 announce
  interrupts, three "MCU announced itself" lines and 32 decoded key events - and then it
  stops serving reads on an idle bus (`geni_ios:0x7`), in a state that is
  indistinguishable from a healthy idle application by any host-side probe.
- Running the bring-up sequence again does not revive it reliably: test 101's re-arm
  after a re-seat produced no announcement at all, through a 1 s power cycle, and the
  3 s cycle added afterwards did not change that (owner's report after test 103).
- A reboot always restores it: the boot bring-up has worked on every flash in this
  series. That is the reliable workaround, and it is why the boot path is left alone.

## The one host-side difference never fairly tested

The imported vendor copy - the only implementation here that carries Samsung's own
application-phase logic - returns early from every real interrupt:
`samsung-pogo/stm32_pogo_interrupt_v3.c:360` gates on `gpiod_get_value()` of an
ACTIVE_LOW descriptor, so it sees 1 exactly when the MCU asserts and skips the packet.
Stock's integer-GPIO `gpio_get_value()` read the physical level. That one line has to be
negated before the A/B can be compared, and until it is, "Samsung's own driver also
fails here" (test 070) is not a valid data point.

## Not to be repeated without new evidence

Changing the reset/air timing again, adding another silence-based trigger, or treating
a NACK from an idle application as a fault. Each of those has already cost a device
cycle and one of them cost the owner a working keyboard for a round.
