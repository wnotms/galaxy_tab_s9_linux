# test-087 — read the MCU *during* its announce pulse: invert the interrupt polarity

- date: 2026-09-22T11:37:39Z, **prepared but NOT executed** (see "Status")
- source: `87e0a88` (test 086)
- images built and hashed here: `boot.img` `463e2ffa…`, `vendor_boot.img`
  `10dff26a…` (`IMAGE-SHA256SUMS`), initramfs `357bf6d2…`

## Why this is a new direction and not a repeat

Two of this project's own measurements, which until now were only ever *recorded*,
point at the interrupt sense:

- test 076/082: with the rail low the announce line **rests low** and the
  application **pulses it high** (~200 ms every ~600 ms).
- stock reports the opposite sense at rest (`int:1`) and takes its ISR on the
  falling edge, which is how the vendor driver's `stm32,irq_type = 0x2008`
  (`IRQ_TYPE_LEVEL_LOW`) and this repository's `interrupts = <75
  IRQ_TYPE_LEVEL_LOW>` are both written.

If the interrupt is level-low while the line rests low, the handler runs **while
the line is low — i.e. exactly while the application is not asking** — and is
deasserted for the whole pulse. Every read this project has ever performed on
0x2a therefore landed outside the announce window, and a level-triggered handler
that only samples between pulses can never observe the event itself.

The hypothesis under test is the consequence: the application pulls the line
*because* it has something to serve, and serves its slave while the line is
asserted (a normal STM32 pattern — assert an attention line, then answer the
host). If so, inverting the sense is the difference between reading inside the
window and reading outside it, and it explains the standing asymmetry without any
new hardware theory: the system bootloader answers because it always serves,
while the application is only ever asked at the wrong moment.

Nothing in the excluded list covers the interrupt sense: the rail, BOOT0, NRST,
addresses, rates, driver logic, firmware path and power-on ordering have all been
measured, but the polarity had only been *observed*, never tried.

## Change (one purpose: the interrupt sense only)

```
dts:  interrupts = <75 IRQ_TYPE_LEVEL_LOW>  -> <75 IRQ_TYPE_LEVEL_HIGH>
      stm32,irq_type = <0x2008>             -> <0x2004>   (vendor port)
cfg:  CONFIG_KEYBOARD_SAMSUNG_POGO_VENDOR_PORT  ->  CONFIG_KEYBOARD_SAMSUNG_POGO
```

The second line of the change puts the mainline port back in charge, because its
handler performs the event read (`pogo_write({3, 0, caps})`) inline on the
interrupt, so with a correct sense the read happens inside the pulse without any
further edit. The vendor port's sense is changed at the same time so the A/B
comparison stays single-variable if it is ever re-selected.

## Procedure (to run once the bench link is back)

```sh
# 1. console: boot the tablet to recovery
powershell.exe -ExecutionPolicy Bypass -File scripts/console-session.ps1 \
  -Port COM17 -Out 'D:\android\gts9-test087\console-087.log' \
  -Commands 'gts9-to-recovery' -Seconds 45
# 2. flash (recovery), clear the BCB, verify read-back, then reboot to system
#    boot.img 463e2ffa…  vendor_boot.img 10dff26a…  init_boot unchanged aed8f3c5…
# 3. console: watch for announce edges and for reads inside the pulse
```

## What the log must show, and what falsifies it

- Watch for the handler running **once per pulse** (`pogo_irq`), the announce
  level report around each event, and whether the read issued at that moment
  returns data or `-EREMOTEIO`/`ret:-6`.
- Stage 1 is met if 0x2a answers (any byte, any value) while the line is
  asserted.
- The hypothesis is falsified if reads taken inside the pulse still NACK exactly
  as they do between pulses: then the sense is not what separates the two kernels
  and the controller comparison in `docs/GENI_TRANSFER_DIFF.md` becomes the lead.

## Status — not executed, no device claim

Both links to the bench are physically down at the time of writing:

- the host lists **no present serial port**
  (`Get-PnpDevice -Class Ports -PresentOnly` matches nothing) and
  `scripts/console-session.ps1` fails to open COM17 for 240 s, so the tablet
  cannot be taken to recovery over the console;
- `adb devices` is empty, so nothing can be flashed or verified either.

The images above are therefore **built, hashed and unflashed**. No result is
claimed for this test; the row stays open in `docs/MAINLINE_VS_STOCK_POGO.md`
until it has been run. The only evidence attached here is the build log
(`build-kernel.log`, "Build complete", no `error:`) and the image hashes.
