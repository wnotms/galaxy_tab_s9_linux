# test-127 — neither a soft nor a hard re-arm revives a silent application; a reboot does

Owner-verified: boot works, a hot re-seat leaves the keyboard dead.  With the manual
re-arm commands now working (test 125 fixed the placement bug that made them no-ops),
the decisive experiment was run on the silent state.

```
cat rearm                    powered=1 event_enabled=1 armed=1 announcements=2
echo soft > rearm    [21.80] re-arm(soft): rail on and DATA armed, no reset, no rail drop
                     -> announcements still 2, no new packet
echo hard > rearm    [25.76] re-arm(hard): running the full boot sequence
                     [25.98] application-entry reset: BOOT0 low, NRST 2 ms low then high,
                             150 ms settle, rail on
afterwards           announcements=2, "announced itself" count=2, key count=0,
                     keep-alive: GET_MODE NACKed (-6)
```

Conclusions this fixes in place:

- **A silent application is not recoverable from software**, through either the no-reset
  path or the full app-entry reset.  The only action that brings the keyboard back is a
  reboot of the tablet, which has worked on every flash in this series.
- Therefore the difference is **not in the MCU's reset sequence** - that sequence is the
  same one the boot path uses successfully - but in something a reboot provides and a
  driver-side re-arm cannot: the bootloader's own initialisation of the accessory's rail
  and pins before Linux claims them, or an electrical reset of the cover that only the
  host power cycle produces.
- The connect line produced no PROBE line during the re-seat either, so the physical
  event is still not observable host-side.  No automatic trigger can be based on it.

Not to be repeated without new evidence: further variations of the reset timing, any
automatic re-arm from the connect line or from silence, and treating an idle NACK as a
fault.  Each of those has already cost a device cycle, and two of them cost the owner a
working keyboard for a round.

Next measurement, host side only: capture what the bootloader leaves behind versus what
the driver does - the pogo rail's regulator state and the pin state of gpio10/12/13/75
at driver probe, compared with the same lines after a hard re-arm.  If the bootloader's
initialisation is what matters, that difference is visible without touching the MCU.
