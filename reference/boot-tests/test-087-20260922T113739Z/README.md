# test-087 — the announce interrupt sense was changed for the wrong reason: result and correction

- date: 2026-09-22T11:37:39Z (prepared), executed 12:32–12:34Z
- source: `87e0a88` (test 086); images `boot.img 463e2ffa…`, `vendor_boot.img
  10dff26a…`, both read back from their partitions byte-for-byte before boot
- authorization: standing device-test authorisation, `刷入测试`
- raw logs: `console-087.log` … `console-087e.log`, hashes in
  `EVIDENCE-SHA256SUMS`

## What was believed, and what is wrong with it

The prepared version of this test argued that the announce line "rests low and
pulses high", that both drivers were written level-low, and that therefore every
read the project had made happened outside the window in which the application
serves its slave.  The DTS interrupt and the vendor property were both inverted
to level-high on that reasoning.

**That reasoning was wrong, and the owner's audit (`0f0b759`,
`docs/POGO_EVENT_STARTUP.md`) says why:** `announce-gpios` is declared
`GPIO_ACTIVE_LOW`, so the descriptor value this driver logs is *logical
assertion*, not the pin's level - a logged 1 means the physical line is low.
Stock's `stm32,irq_type = 0x2008` and `IRQ_TYPE_LEVEL_LOW` were right from the
start, and both are restored in `0f0b759`.  A second overreach was reading the
pin-state register dump (patch 0010) as a line level: `pin 75: io 0x1` is a
register value, and for input pins it carries no level at all.

## What the boot actually measured

```
[   32.069889] no-action: announce 1 -> 0 after 26300 ms
[   32.702275] no-action: announce 0 -> 1 after 26900 ms      <- logical values:
[   32.918098] no-action: announce 1 -> 0 after 27100 ms         a train of
   ...  (same ~600 ms cadence) ...                              transitions from
[   32.9 s]  last transition logged                             11.8 s to 32.9 s
[   36.725923] MCU rail on with BOOT0 low, announce line armed (level 0)
[   36.726165] MCU announced itself (1)                        <- the one and only
                                                                 handler entry
[   41.217994] i2c-5 acknowledges: (nothing)
[   36.016643] after the no-action window: application -6, bootloader -6, announce level 0
```

- `cat /proc/interrupts`: **`169: 1 msmgpio 75 Level 5-002a`** - the announce
  interrupt was delivered exactly once in the whole boot.
- `dmesg | grep -c "event transfer failed"` = **0**: the handler never put a byte
  on the bus, so no read ever happened inside any assertion window.
- `geni_i2c 89c000.i2c: NACK … m_cmd:0x8005400, geni_status:0x0, geni_ios:0x7`
  reproduces the standing result: the transfer to `0x2a` ran, completed, and
  nothing acknowledged it, on an idle bus.

## Result, and what it is worth

**Negative, and not evidence about the interrupt sense.** Stage 1 is not met:
`0x2a` never answered. The one delivery the level-high arm produced came from the
diagnostic startup path and found `p->powered` false, so it read nothing; by then
the application's transition train was over.

The useful finding is a *defect*, and it is the one the owner fixed: the
diagnostic `pogo_connect_work()` held `p->lock` across its 30 s observation
window, its rail cycle and up to 60 s of version polling, while `pogo_irq()` needs
that same mutex - so during the entire window in which the application was asking
for attention, the handler could not have serviced it even if it had been
delivered. `0f0b759` moves the normal startup out from under the lock (enable
rail, 50 ms, arm DATA, unlock), leaves the intrusive experiments behind
`keyboard_samsung_pogo.startup_diagnostics=1`, and makes the model handshake a
single version attempt.

Two further measurements in this boot are worth keeping: the rail's
`regulator_disable()` **did nothing** and warned `unbalanced disables for
pogo-vdd` because no reference had been taken, so the "stock's own cycle" this
driver claimed to perform had never actually happened (test 088 measured the
claimed cycle explicitly); and the whole application transition train happens
once, early (here 11.8–32.9 s), and never repeats.

## Next step

Test 090 boots `0f0b759`, whose handler can now take the lock. The images were
flashed and verified (`a6fce2f9…` / `b5f3cda0…`), but the console link was lost
before the result could be read, so this test claims nothing about it.
