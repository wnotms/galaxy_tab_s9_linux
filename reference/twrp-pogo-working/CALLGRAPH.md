# Samsung `stm32_pogo_v3` as executed — call graph and the 20 questions

Sources: `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/*`
(the official SM-X710 tree; byte-identical to the X910 copy this port was written
from, see `test-055/official-driver-diff.txt`), and the trace in
`bringup-cycle-dmesg.log`, captured in TWRP by driving the driver's own
`keyboard_connected` 0 → 1.

**The driver has no module_init of its own.** It is a pure i2c driver: the entry
point is `stm32_pogo_v3_start()` reached from the i2c probe, and everything else
is workqueues.

```
i2c_probe (stm,stm32_pogo on 0x2a)
└─ stm32_pogo_v3_start()                       core_v3.c
   ├─ stm32_i2c_new_dummy(stm32, 0x51)         → the "bootloader" client (name dummy)
   ├─ stm32_parse_dt()                          all stm32,* properties, incl. mcu_swclk/mcu_nrst
   ├─ stm32_init_cmd()                          sec_keypad sysfs, sec_device_create
   ├─ stm32_wakeup_source_register()
   ├─ stm32_init_mutex() / stm32_init_pinctrl() pinctrl "default" → gpio12 low, gpio13 high
   ├─ stm32_init_voting() / stm32_init_completion() / stm32_init_workqueue()
   ├─ stm32_dev_firmware_update_menu(stm32, 0)  ← the only path that could touch 0x51
   │  └─ stm32_dev_firmware_update_mode()
   │     ├─ request_firmware("keyboard_stm/stm32_gts9family.bin")  → FAILS here (no such file)
   │     └─ goto err_request_fw  ⇒ returns -1  ⇒ checksum/validation/IC-read/disconnect NEVER run
   │        (logged as "Failed to update stm32_mcu_dev firmware -1")
   ├─ stm32->pogo_enable = true
   ├─ stm32_slave_device_init() / stm32_interrupt_init()
   │  ├─ gpio_to_irq(gpio75) → request_threaded_irq(irq_type)     event IRQ, registered
   │  ├─ gpio_to_irq(gpio62) → request_threaded_irq(irq_conn_type) connect IRQ, registered
   │  ├─ stm32_enable_conn_wake_irq(true)
   │  └─ stm32_enable_irq(INT_DISABLE_NOSYNC)   event IRQ starts DISABLED
   ├─ connect_state = gpio_get_value(gpio62)
   ├─ stm32_keyboard_connect()
   │  └─ if connect_state: stm32_keyboard_start()
   │     ├─ stm32_dev_regulator(1)             ← RAIL ON (fixed_regulator@1, gpio10)
   │     ├─ stm32_delay(50)
   │     └─ stm32_enable_irq(INT_ENABLE)        ← event IRQ enabled
   │     else: stm32_keyboard_stop()            → IRQ disable + RAIL OFF
   └─ stm32_register_notify()
```

## The cycle that was captured, line by line

```
69.901730  keyboard_connected_store: current 0
69.901733  stm32_keyboard_connect: 0
69.901746  stm32_enable_irq: disable dev irq nosync
69.901752  stm32_dev_regulator off: vdd:off          rail OFF
69.901755  stm32_keyboard_stop: done
70.142278  stm32_conn_isr (0)                        connect line IRQ
70.311094  stm32_conn_isr (1)                        cover attached
70.311133  stm32_check_conn_work: con:0, current:1
70.311143  stm32_keyboard_connect: 1
70.311157  stm32_dev_regulator on: vdd:on            rail ON      (410 ms after off)
70.364327  stm32_enable_irq: enable dev irq          +53 ms       (the stm32_delay(50))
70.499288  stm32_dev_isr                             +135 ms      MCU asserts the announce line
70.499906  write_burst 03 00 01 / read 03 00 02      event read
70.501938  stm32_dev_int_proc: support_keyboard_model 0x2
70.502110  write_burst 04 00 01 / 02 / read 07 00 01 / 00 01 04 01
70.504048  stm32_read_version: [IC] version:1.4 …    CHECK_VERSION
70.512457  write_burst 04 00 01 / 01 / read 04 00 01 / 01
70.513587  [MODE] 1 ; stm32_set_mode: already same mode buff:1, mode:1
70.716437  write_burst 04 00 01 / 03 / read 07 00 01 / 6E 37 DF EA
70.722599  stm32_read_crc: [IC] BOOT CRC32 = 0xEADF376E
70.722769  write_burst 04 00 02 / 18 / read 09 00 02 …   touchpad, ed_id 2
```

**The decisive line is `stm32_dev_isr` at 70.499288**: 135 ms after the rail came
up, and *before any host transaction*, the MCU drives its announce line. The
application starts by itself on power-up; the driver only reads it. Mainline arms
the same interrupt and sees nothing in 30 s (test 061), which is the single
behavioural difference this whole investigation has to explain.

## The 20 questions

1. **Entry point**: no `module_init`; i2c probe → `stm32_pogo_v3_start()`.
2. **DT parsing**: `stm32_parse_dt()` reads `stm32,irq_gpio`, `stm32,irq_conn`,
   `stm32,irq_type` (0x2008 = level-low | ONESHOT), `stm32,irq_conn_type`
   (0x2003 = edge-both | ONESHOT), `stm32,mcu_swclk`, `stm32,mcu_nrst`,
   `stm32,sda_gpio`, `stm32,scl_gpio`, `stm32,fw_name`, `stm32,model_name`,
   `stm32_vddo-supply`; gpios through the legacy `of_get_named_gpio()`.
3. **Regulator**: first enabled in `stm32_keyboard_start()` via
   `stm32_dev_regulator(1)` — i.e. *after* probe, in the connect path, and only
   when the connect line reads high; `stm32_keyboard_stop()` switches it off
   again. It is never enabled inside `stm32_interrupt_init()`.
4. **SWCLK/BOOT0**: only ever touched by the vendor's `stm32_sysboot_connect()`
   / `stm32_sysboot_disconnect()` (fw-update path, dead here); otherwise the
   pinctrl "default" state holds it `output-low`.
5. **NRST**: same — only the fw-update path; otherwise pinctrl holds it
   `output-high`. **The working path never pulses NRST.**
6. **Connect IRQ**: registered in `stm32_interrupt_init()`, enabled there
   (`stm32_enable_conn_wake_irq(true)`) and never disabled on the normal path.
7. **Event IRQ**: registered in `stm32_interrupt_init()` but deliberately left
   *disabled* (`stm32_enable_irq(INT_DISABLE_NOSYNC)`) until
   `stm32_keyboard_start()` enables it, 50 ms after the rail comes up.
8. **First I2C transaction**: after that, in `stm32_dev_int_proc()` — the
   *interrupt* work, not a poll: the MCU announces first and the host reads the
   event (`write_burst 03 00 01`).
9. **Delay before CHECK_VERSION**: 50 ms (rail) + however long the MCU takes to
   assert the line — 135 ms in the captured cycle. No fixed sleep.
10. **First failure**: `stm32_dev_int_proc()` error path logs and returns; the
    driver retries through `stm32_power_reset()` (NRST pulse) in the *poll* path
    used when the cover announces itself on the connect line instead.
11. **Controller reset**: never. No register of the GENI SE is touched by this
    driver; it only calls `i2c_transfer`/`i2c_master_send`.
12. **STM32 reset**: `stm32_power_reset()` (NRST low 3 ms, high 10 ms) exists, but
    the captured working boot never calls it (`rst:0` in the status line).
13. **System bootloader**: only inside `stm32_dev_firmware_update_mode()`, which
    on this device aborts at `request_firmware()` because
    `keyboard_stm/stm32_gts9family.bin` is not present.
14. **Firmware failure path**: `goto err_request_fw` → `release_firmware` is
    skipped → returns -1 → the caller only logs "Failed to update stm32_mcu_dev
    firmware -1" and continues to `pogo_enable = true` and
    `stm32_interrupt_init()`. Nothing on the STM32 side happens.
15. **`stm32_interrupt_init()` order**: IRQ workqueues → `INIT_DELAYED_WORK` ×3 →
    `gpio_to_irq(75)` → `gpio_to_irq(62)` → `request_threaded_irq(75)` →
    `request_threaded_irq(62)` → `stm32_enable_conn_wake_irq(true)` →
    `stm32_enable_irq(INT_DISABLE_NOSYNC)`.
16. **Around `stm32_read_version()`**: it is called from `stm32_check_ic_work()`
    *after* the event was read, then `stm32_set_mode(MODE_APP)` (which reads
    `GET_MODE` and writes `STM32_CMD_ABORT` only if the mode is neither APP nor
    EXCEPTION), then `stm32_read_crc()`, `stm32_read_tc_version()`,
    `stm32_read_tc_crc()`, `stm32_read_tc_resolution()`.
17. **Input device**: created by the keyboard child device
    (`stm32_pogo_keyboard_v3.c`), registered when the keyboard child probes after
    the announcement (`keypad_set_input_dev_bypass`, "input dev already exist" in
    the trace); the touchpad is a second child (`stm32_pogo_touchpad_v3.c`).
18. **Model announcement**: not polled — the MCU asserts gpio75, the ISR reads the
    event (`03 00 01` header) and `stm32_dev_int_proc()` reports
    `support_keyboard_model 0x2`; that is what authorises the keyboard child.
19. **IRQ → key event**: `stm32_dev_int_proc()` reads the event payload and
    dispatches by event id to the keyboard/touchpad children, which translate row
    and column data into input events through the matrix keymap module.
20. **Children**: `pogo_kpd` (keyboard) and `pogo_touchpad` are platform children
    declared in the same DT overlay, bound after the announcement
    (`stm32_send_conn_noti: CONNECT=1`).
