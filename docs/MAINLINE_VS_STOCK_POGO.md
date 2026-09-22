# Samsung `stm32_pogo_v3` versus this port: stage-by-stage diff

Reference for the stock column: `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/`
and the executed trace in `reference/twrp-pogo-working/` (`bringup-cycle-dmesg.log`,
`CALLGRAPH.md`). The mainline column is `kernel/drivers/keyboard-samsung-pogo.c`.
Every "measured" line refers to a test under `reference/boot-tests/`.

| stage | Samsung stock | mainline port | equivalent? | risk / evidence |
| --- | --- | --- | --- | --- |
| entry point | i2c probe → `stm32_pogo_v3_start()`; no `module_init` | i2c probe → `pogo_probe()` | yes | structurally the same (CALLGRAPH.md) |
| DT parsing | `of_get_named_gpio()` for `stm32,irq_gpio`, `mcu_swclk`, `mcu_nrst`, `sda_gpio`, `scl_gpio` | `devm_gpiod_get*()` for `connect`, `swclk`, `nrst`, `sda`, `scl`, `announce` | equivalent in effect | same pins, same states (test 055/067) |
| rail ownership | `regulator-fixed` on gpio10, consumer `44-002a-stm32_vddo`; driver switches it | same regulator, consumer `pogo-vdd`; driver switches it | yes | test 064: both `use 1`, same single consumer |
| pinctrl ownership | pinctrl "default" from the node: gpio12 `output-low`, gpio13 `output-high`, gpio75/62 input | identical + a "recovery" state for gpio72/106 | yes | test 055/064: `function gpio` for all seven pins |
| GPIO request flags | legacy API (`gpio_direction_output`) | gpiolib descriptors | equivalent | "GPIO UNCLAIMED" in stock's pinmux vs claimed in mainline |
| SWCLK / BOOT0 | only the fw-update path touches it; otherwise pinctrl low | held low in `connect_work` | yes | tests 058/065/068 |
| NRST | only the fw-update path; **the working path never pulses it** | never pulses it in the first bring-up | yes | stock trace has no NRST line; test 058+ |
| connect line | IRQ on gpio62, edge-both, drives `connect_state` | same IRQ, same type, used only for logging | partly | the port does not gate the bring-up on it; stock does |
| IRQ polarity/type | `0x2008` (level-low, ONESHOT) on 75; `0x2003` (edge-both, ONESHOT) on 62 | identical | yes | test 055 (official DTS + overlay) |
| IRQ enable timing | event IRQ registered **disabled**, enabled 50 ms after the rail | armed 50 ms after the rail | yes | test 065/068 |
| workqueue timing | `check_ic_work` 500 ms after connect; announcements serviced by the ISR | poll every 250 ms for up to 60 s | **no** | the port polls where stock is event-driven; measured harmless (test 060/068) |
| runtime PM | `pm_runtime` on the controller; driver does not touch it | same | yes | test 064 |
| I2C transaction pattern | `write_burst {4,0,1}` + command; read 3-byte header then payload | identical | yes | byte-for-byte in test 055 |
| STOP | `samsung,stop-after-trans` in DT **but no consumer in the official tree** | STOP per `i2c_master_send/recv` | equivalent | test 058/063: no consumer exists |
| retry | `stm32_power_reset()` on a failed poll (NRST pulse) | patient re-poll, no reset | **no** | the port's choice is measured better (tests 048/052) |
| controller reset | never | never | yes | - |
| bus recovery | none anywhere | `pogo_recover_bus()` in the deep failure path only | **no** | moved out of the poll window in test 060; the announce handler never calls it (verified this round) |
| firmware path | aborts at `request_firmware()`; never reaches `0x51` | not attempted at all | equivalent | tests 055 |
| model handshake | MCU announces on gpio75; host reads the event; that authorises the children | the port reads the event if the IRQ fires; no children | **no** | test 067/068: the pulse happens, the read fails with a real NACK |
| input registration | keyboard/touchpad children after the announcement | one input device registered at probe | **no** | never reached: the announcement read fails |
| failure recovery | resets per failed poll attempt (up to 100000) | recover + scan + one bootloader visit | **no** | by design |

## What the table says

Every *configuration* row is equivalent, and the rows that are not are all in the
port's favour or irrelevant to the failure: the port polls instead of waiting for
an event, it does not gate on the connect line, and it has no children to
register. The two rows that matter - **model handshake** and **input
registration** - are both downstream of the one measured symptom: the MCU pulls
its announce line low ~130-190 ms after the rail rises (identical to stock,
test 068), and the host's read of that event is NACKed on an idle bus (test 063)
where stock's identical read succeeds.

So the difference is not in the driver's stage order, not in the pin or rail
ownership, and not in the protocol. It is in what happens between the MCU
asserting its line and the controller's address phase - the one layer left is the
controller driver itself: the stock kernel runs `i2c-msm-geni.c`
(`CONFIG_I2C_MSM_GENI`, the value in `kalama-gki_defconfig`), mainline runs
`i2c-qcom-geni.c`, and the two are different drivers, not two configurations of
one. That is what the vendor-port A/B (the owner's stages five and six) is for.
