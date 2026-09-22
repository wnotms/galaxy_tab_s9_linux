# test-052 — a patient, read-only wait is not what the application needs

- started: 2026-09-22T06:57:03Z
- source commit: `a72e728` ("pogo: wait for the application instead of resetting it")
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img fbf16935…` (from `out/boot-bundle-test052`), `init_boot.img
  2fb24cd0…`, `vendor_boot.img 828dadec…`, `dtbo.img c17418be…` unchanged
- authorization: owner asked to continue the repair ("检查仓库变化，继续修复") and
  asked to reduce the wait between system switches

## Hypothesis

The application needs time from power-on before its I2C slave answers, and the
port had been resetting it every ~50 ms while polling at 4 s, restarting that
delay forever. Evidence for it: the connect line read 1 at power-on and 0 after
the first reset, no address answered after the resets (test 051), and stock's
driver first reads the application 33 s into its boot without resetting it
(`rst:0`).

## Result — disproved

The candidate polls `CHECK_VERSION` every 250 ms for 60 s without touching NRST,
SWCLK or the bus, and gives the application another 60 s after the bootloader
visit. Nothing answered:

```
[    3.669914] input: Book Cover Keyboard Slim (EF-DX710) as .../5-002a/input/input0
[   67.165083] no answer from the MCU application after 60000 ms (-6)
[   67.245834] i2c-5 answers at: (nothing)
[   67.253541] MCU application did not answer; entering its bootloader
[   67.389945] MCU bootloader took the 0xFF sync
[   67.404728] MCU bootloader version 0x12
[   67.427546] MCU IC version 00340034
[   67.456034] no STM32 header at 0x80000c0 or 0x80000bc, first bytes 0000...
[   67.645711] after the disconnected reset: application -6, bootloader -6, connect 1
[   97.677316] application after bootloader start: -6 after 30020 ms without reset (no version response)
[   97.693939] five seconds later: application -6, bootloader -6, connect 1
[  161.118193] no answer from the MCU application after 60000 ms (-6)
[  161.177164] i2c-5 answers at: (nothing)
```

Sixty seconds of undisturbed polling from 3.7 s to 67 s, and another sixty from
97 s to 161 s, with no reset in either window, produced no answer — while
`CHECK_VERSION` on the same part under the stock stack does answer. Time is
therefore not the missing ingredient.

Two things this run also settles:

- the connect line is not an "MCU is alive" signal: during the patient poll it
  toggles 1/0 every few samples (it is a bias-disable input on a floating
  connector), so the earlier reading of `connect 1` as "the MCU is driving it"
  was wrong and is withdrawn;
- the bootloader side keeps working through all of it — sync, version `0x12` and
  the IC version `00340034` came back again on the first attempt each time.

## Where this leaves it

Under mainline the part answers as a bootloader and never as an application, in
every sequence tried: read-only at 4 s, read-only for 60 s, after a vendor
disconnect reset, after GO, and after 40 reset retries. Under the stock stack the
same part answers as an application. The stock overlay for this bus carries two
quirks the mainline controller does not implement -
`samsung,reset-before-trans` and `samsung,stop-after-trans` - and the vendor's
one piece of bring-up the port still has not done is
`stm32_target_option_update()`, which reads the MCU's option bytes at
`0x1FFF7800` and clears bit 24 when it is set. Test 053 reads that word (read
only) before anything is written.
