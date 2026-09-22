# test-064 — regulator comparison (no flash): the pogo rail is on in both

- date: 2026-09-22T08:21:00Z, no kernel flashed, no partition written
- authorization: standing device-test authorisation; the tablet was already
  running mainline (test 063 candidate)
- source: mainline's `/sys/kernel/debug/regulator/regulator_summary` read over
  the console, compared with the stock kernel's own summary archived in
  `test-045-20260922T004902Z/twrp-regulator-summary.txt`

## What it tested

The last host-side difference class left after test 063: a supply that the stock
kernel enables and mainline does not, feeding the keyboard connector (level
shifter / boost), rather than gpio10 alone.

## Result — the method cannot see it, and nothing pogo-specific is missing

- `pogo-vdd` is present and enabled in mainline (`use 1`), matching stock's
  `fixed_regulator${#}` (also `use 1`, consumer `44-002a-stm32_vddo`).
- The PMIC rails stock lists (`pm_humu_l5`, `l12`–`l17`, `pm_v6e_l3`, …) have
  **no entry at all** in mainline's summary. That does not mean they are off: the
  display works in mainline while `pm_v6e_l3` (the DSI 1.2 V rail) is equally
  absent from the list, so unregistered rails are simply left in their boot state
  by the PMIC. A registered-regulator comparison therefore cannot answer this
  question on this port.
- The stock summary's only keyboard-adjacent consumers are `44-002a-stm32_vddo`
  (gpio10, on in both) and `40-004f-vdd3` / `40-004f-vdd18` — a device at I2C
  address 0x4f that mainline does not instantiate at all. Its 32 mA at 1.8 V
  points at a display/touch level shifter rather than the keyboard, and with the
  PMIC rails unregistered there is no way to read its state from mainline.

## Conclusion

The "missing supply" hypothesis is not supported by anything measurable here, and
this method is exhausted: the port would need the PMIC rails registered (a much
larger change) to compare them at all. The pogo rail itself is identical in both
kernels, and test 063 already showed the bus is idle and the NACK is real, so the
STM32 is powered and reachable — it just does not serve `0x2a`.
