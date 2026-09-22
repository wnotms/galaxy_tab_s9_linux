# test-077 — the whole address range is silent: the slave is not participating

- started: 2026-09-22T10:10:00Z
- source commit: `7b477b9`
- images: `boot.img e8218c85…`; vendor_boot/init_boot/dtbo unchanged
- authorization: standing device-test authorisation recorded for tests 046-076

## What it asked

Test 076 showed the application running and announcing itself unprompted;
test 074's probe had covered only five addresses. If the application serves an
address outside that set, this sweep finds it; if the whole range is silent while
its own line is being driven, the slave itself is not participating.

## Result — nothing, anywhere

```
[    4.807984] MCU rail on with BOOT0 low, announce line armed (level 1)
[    4.807992] MCU announced itself (1)
[    6.778405] i2c-5 acknowledges: (nothing)
[   12.334119] right after the rail cycle: application -6, bootloader -6, announce level 0
```

The sweep covers 0x08-0x77 with the one-byte write that really ACKs an address,
and it ran six seconds after the rail rose, while the MCU was announcing itself
on its own line. **Not one address answered.**

## What that settles, and what it does not

* **The controller is exonerated.** The same controller, in the same boot,
  completes the SWCLK dance and then reads the bootloader's version at `0x51`
  (tests 067-072), so its address phase is well formed and a participating slave
  does acknowledge it. Any suggestion that `i2c-qcom-geni` presents addresses
  differently from the downstream driver would have to explain why the *same*
  slave answers it in boot mode and not in application mode.
* **The application is running** - it drives the line only it drives, with no
  host traffic (test 076).
* **Its I2C slave is not on the bus at all**, at any address, while the same
  peripheral is on the bus in boot mode.

That leaves the application's own decision to enable its slave as the only
remaining variable. Everything the host controls at its startup has been
measured and matches stock: rail rising, BOOT0 low, NRST released (test 075),
stock's complete firmware path reproduced value for value (test 072), and no
traffic during the first seconds (test 076). What the host cannot see or set is
what the application checks for itself inside the cover - the touchpad, the hall
or booster the vendor driver also queries - and the reference for that is the
vendor driver, which is now able to run here and whose own reads of those parts
are the next thing to compare against its stock behaviour.
