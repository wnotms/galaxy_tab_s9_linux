# test-147 — the five questions, answered from measurements (one gap left open)

Build: `boot.img c12590a8` (stock-style detach + hot reconnect + bounded handshake retry).
The owner's five-cycle acceptance test has not been run on this build yet; what follows is
answered from what has already been measured, and the one item that still needs a pad-level
reading is marked as owed rather than assumed.

## 1. Why does GPIO10 go low when the EF-DX710 is unplugged?

`pogo_conn_check_work()` reads gpio62, sees 0 where the last state was 1, and calls
`pogo_detach()`, which ends in `pogo_power_off()` -> `regulator_disable(p->vdd)`.  The rail
is a `regulator-fixed` with `gpio = <&tlmm 10 GPIO_ACTIVE_HIGH>` and `enable-active-high`,
so disabling it drives pad 10 low.

Measured: `pogo: rail off, state=DETACHED` at 46.556 s in test 145's log, and earlier (test
088) the explicit reading `rail off: regulator off` with the same fixed regulator.  **Owed:**
a pad-level reading taken *while the cover is off* (`regulator_enabled=0` in `cat rearm`,
and the pin-state report) - the log line is the driver's statement, not the pad's.

## 2. Why does the driver turn it back on when the cover returns?

The same check work sees the transition to 1 and takes the stock path: `pogo_power_on()` ->
`regulator_enable()`, 50 ms settle, then `enable_irq()` if `irq_armed` is false.

Measured: `pogo: connect line reads 1 (was 0) after the 250 ms check` at 50.177 s and
`pogo: hot reconnect: rail on, DATA armed, no reset (stock model)` at 50.244 s (test 145).

## 3. Why does the hot path need no NRST pulse?

Because a hot-plugged MCU has just been powered with BOOT0 already low, so it starts its
application by itself; the host only has to raise the rail and listen.  This is what
Samsung's own driver does: the vendor A/B logs `stm32_keyboard_connect: 1` after a re-seat
followed by `stm32_dev_regulator on` and `stm32_enable_irq` - and never touches nrst.  The
cold path keeps its BOOT0-low NRST pulse because at power-on the part may instead be sitting
in its system bootloader (that was the original fault, test 092).

Measured: the hot path's own log line above; source: `pogo_conn_check_work()` calls only
`pogo_power_on()`, `msleep(50)` and `enable_irq()`.

## 4. Why can the enable/disable pair not unbalance?

Both directions are guarded by one flag.  `pogo_detach()` calls `disable_irq_nosync()`
only inside `if (p->irq_armed)`, and the hot path calls `enable_irq()` only inside
`if (!p->irq_armed)`; `pogo_irq()`'s error path no longer disables anything, it schedules a
bounded retry instead (the previous port disabled the IRQ on failure and could double-count).

Measured: no `unbalanced` / `Disabling IRQ` line has ever come from this driver; the three
matches in test 145's log are boot-time kernel warnings (x1-x3 boot protocol, clk-rcg2,
base/core).

## 5. Why does the regulator enable count not accumulate over many cycles?

Every rail operation goes through `pogo_power_on()` / `pogo_power_off()`, each of which
returns immediately when the state already matches, and only two direct regulator calls
remain in the file - inside those helpers.  `p->powered` follows the regulator instead of
leading it, so no caller can fake the state.

Measured: three consecutive `echo soft` writes left `regulator_enabled=1`, `irq_armed=1`,
`powered=1` (test 145).  The detach/reconnect cycle exercises the same two helpers.

## Still owed

The five-cycle and the three-to-five-minute idle runs of the owner's section 21, plus the
pad-level reading in item 1 taken while the cover is off.
