# test-079 — 100 kHz with the vendor path: the same NACK

- started: 2026-09-22T10:30:00Z
- source commit: the 100 kHz DTS change
- images: `boot.img c1fb38a7…`, `vendor_boot.img 7bd7dcf9…` (new DTB);
  `init_boot aed8f3c5…` (with firmware), `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-078

## Why this combination had never been measured

The bus was raised to 400 kHz in test 059 on the strength of the downstream
binding's default, and that comparison used the mainline port *before* the stock
firmware was available. The combination built here - Samsung's driver running its
complete stock firmware path at 100 kHz - had never run.

## Result — excluded too

```
[    6.144255] stm32_sysboot_mcu_validation Get target info OK Target PID: 0x460 Bootloader version: 0x12
[    8.565105] stm32_i2c_write_burst: I2C retry 3, ret:-6
[   10.917166] stm32_i2c_write_burst: I2C retry 3, ret:-6
[   13.282624] ... the same, every ~2.3 s for the rest of the boot
```

The complete stock firmware path runs (the bootloader is read at 100 kHz without
difficulty) and the application's address is NACKed exactly as at 400 kHz. The
bus rate is now excluded for both drivers and both firmware states.

## The host side is closed

| host-provided input | test | outcome |
| --- | --- | --- |
| rail, BOOT0, NRST at the application's startup | 075 | identical to stock |
| stock's firmware path, value for value | 072 | reproduced |
| no traffic early; the application announces itself | 076 | the application runs |
| real address probe, whole 7-bit range | 077 | nothing acknowledges |
| both driver implementations | 070, 078 | both fail identically |
| bus rate, 100 kHz and 400 kHz | 059, 079 | both fail identically |

Nothing the host can set or observe changes the outcome, and the same board,
cover, firmware and driver code succeed under stock. What remains is what the
host neither sets nor sees: the application's own decision to enable its slave,
which depends on what it finds inside the cover over its own internal bus - and,
on the host side, the *transitions* of the pins during boot rather than their
final states.

## Next step

The last host-side item the owner's plan lists and this project has not measured
is P3: the order and timing of the transitions themselves - TLMM probe, the
pogo pin states being applied, the regulator probe, the keyboard probe, the first
transaction - with one-shot timestamps at each, compared against the same
sequence in the stock boot log. Every final state is known to match; whether the
mainline boot passes through a state stock never visits (a pin briefly muxed or
driven differently, before the driver owns it) is the one thing left that the
host controls and has never looked at.
