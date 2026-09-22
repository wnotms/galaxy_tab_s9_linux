# test-050 — stock's bring-up, byte for byte, and the IC version it predicts

- started: 2026-09-22T06:41:17Z
- source commit: `b74f0eb` + `ad2a7f1` ("pogo: start the MCU the vendor's way,
  without GO" and its build fix)
- upstream: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3)
- images: `boot.img 31060e4d…` (from `out/boot-bundle-test050`), `init_boot.img
  2fb24cd0…`, `vendor_boot.img 828dadec…`, `dtbo.img c17418be…` unchanged
- authorization: owner asked to continue the repair ("检查仓库变化，继续修复") and
  asked to reduce the wait between system switches

## Hypothesis and predictions

`GO` is not how this part is started. Stock's probe
(`stm32_dev_firmware_update_mode()`) never sends GO: it enters the system
bootloader (`stm32_sysboot_mcu_validation()`), reads the IC version at
`0x08000200` through `stm32_sysboot_i2c_read()`, and then calls
`stm32_sysboot_disconnect()` — BOOT0 low, one NRST pulse, 150 ms — which releases
the part so the application runs from flash.

1. the IC read must return four bytes whose last byte is `0x34`, the value stock
   prints as `mcu_fw(ic):34`;
2. after the single reset of the disconnect the application must answer
   `CHECK_VERSION`;
3. if it reports mode 2 (DFU) the driver sends ABORT `0x17` and reads again.

## Result — prediction 1 confirmed, predictions 2 and 3 not reached

```
[    3.854192] MCU application did not answer; entering its bootloader
[    4.268003] MCU bootloader took the 0xFF sync
[    4.284812] MCU bootloader version 0x12
[    4.302536] MCU IC version 00340034
[   10.103695] application after bootloader start: -6 after 5072 ms without reset (no version response)
[   10.160883] attempt 0 failed: scl:-1 sda:-1 conn:1
[   10.233665] attempt 1 failed: scl:-1 sda:-1 conn:0
...
```

`MCU IC version 00340034`: the last byte is `0x34`, exactly the value stock's
driver prints as `mcu_fw(ic):34` after reading the same address over the same
bootloader command. The READ path is therefore byte-correct against an
independently known stock value — the first hard confirmation that the port talks
to the MCU's bootloader the way Samsung's driver does.

The application still did not answer, with or without the disconnect reset, and
the 40 reset retries that follow did not bring it up either. Note the connect line
in the same log: it reads `conn:1` before the first NRST pulse and `conn:0`
afterwards, i.e. whatever drives that line stopped driving it once the MCU was
reset — the cover itself is attached (stock reports `con:1/1`).

## The hardware configuration is stock's

The device's own `dtbo.img` carries Samsung's pogo overlay, and every value in it
matches the mainline port (see `stock-dtbo-stm32-node.txt`):

| stock `stm32@2a` property | value | mainline port |
| --- | --- | --- |
| `stm32,irq_gpio` | gpio 75 | gpio75, `IRQ_TYPE_LEVEL_LOW` |
| `stm32,irq_conn` | gpio 62 | gpio62, `IRQ_TYPE_EDGE_BOTH` |
| `stm32,mcu_swclk` | gpio 12 | gpio12, `output-low` |
| `stm32,mcu_nrst` | gpio 13 | gpio13, `output-high` |
| `stm32,sda_gpio` / `scl_gpio` | gpio 72 / gpio 106 | gpio72 / gpio106 |
| `stm32_vddo-supply` | `fixed_regulator@1`, gpio 10, active high | `vreg_pogo`, gpio10, active high |
| `stm32,irq_type` / `irq_conn_type` | `0x2008` / `0x2003` | level-low / edge-both |
| `stm32,model_name` | `EF-DX715`, `EF-DX710` | `EF-DX710` (0x02) |

So the rail, both reset pins, the bus pins, the interrupt types and the model id
are not the difference. What is left to separate is whether the part stays in its
bootloader after the reset or runs an application that does not answer — which is
what test 051 measures.
