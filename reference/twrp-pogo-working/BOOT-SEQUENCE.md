# Stock's boot-time pogo sequence, and one correction it forces

Captured on 2026-09-22T10:16Z by booting TWRP and reading `dmesg` within twenty
seconds, before the ring rotated. Raw log: `boot-time-dmesg.log`, filtered copy:
`boot-time-pogo-sequence.txt`.

```
1.640277 init: Loading module /lib/modules/stm32_pogo_v3.ko
1.641345 deferred_flag boot stm32_dev_probe
1.740124 stm32_dev_probe++
1.740139 stm32_i2c_new_dummy: client_boot address:0x51
1.740171 stm32_parse_dt: irq_type property:2008, 8200
1.740174 stm32_parse_dt: irq_conn_type property:2003, 8195
1.740299 stm32_parse_dt: scl: 407, sda: 373, int:376, conn: 363, mcu_swclk: 313, mcu_nrst: 314
1.740326 stm32_dev_firmware_update_mode start
1.740350 stm32_dev_firmware_update_mode: succeeded to request firmware retry_count:9
1.740361 stm32_dev_checksum: cal checksum:0x7E2341C8 last_sector_number:25 size:52012
1.740364 stm32_sysboot_mcu_validation start
1.740365 stm32_sysboot_connect start
1.796919 stm32_sysboot_i2c_sync
1.797032 stm32_sysboot_i2c_sync succeed to connect to target
1.852933 stm32_sysboot_mcu_validation Connection OK
1.852938 stm32_sysboot_i2c_get_info cmd[0]:0x2, cmd[1]:0xfd
1.853394 stm32_sysboot_i2c_get_info succeed to get info id 1120          (PID 0x460)
1.853397 stm32_sysboot_i2c_get_info cmd[0]:0x1, cmd[1]:0xfe
1.853791 stm32_sysboot_i2c_get_info succeed to get info version 18        (0x12)
1.853793 stm32_sysboot_mcu_validation Get target info OK Target PID: 0x460 Bootloader version: 0x12
1.853795 stm32_target_option_update
1.854673 stm32_target_option_update optionbyte is 0, success              (no write)
1.854675 stm32_target_empty_check_status
1.855553 stm32_target_empty_check_status Flash Word: 0x200056C0           (our vector table's SP)
1.878585 stm32_sysboot_disconnect start                                   (first disconnect)
2.036960 stm32_sysboot_mcu_validation start                               (second cycle)
2.036961 stm32_sysboot_connect start
...
```

## Two things this settles

**Stock *does* use the system bootloader at boot.** Test 055 concluded the
opposite - that `stm32_dev_firmware_update_mode()` aborts at
`request_firmware()` and the bootloader is never touched - from the sysfs
attribute `get_fw_ver_bin` reading `EF-DX710_v0.0.0.0`. That inference was
wrong: the boot log says `succeeded to request firmware retry_count:9`, so the
firmware *is* available to the stock driver and the whole update path runs -
checksum, validation (dance and SYNC), Get Id, Get Version, option-byte check,
empty check, IC read, and **disconnect** - twice over, before
`stm32_interrupt_init()` and the rail. The port's own dance is therefore not an
invention; stock performs the same one at boot, and the vendor port in mainline
only skips it because *mainline* has no firmware file, which makes
`request_firmware()` fail and the path return early.

**Two independent confirmations of the port's flash reads.** `Flash Word:
0x200056C0` is exactly the stack pointer this port read at 0x08000000 in test
049, and `optionbyte is 0, success` matches the bit-24-clear option word
measured in test 053.

## The open question, precisely

Where does stock's firmware come from? It is **not** in the firmware partition
(`/vendor/firmware_mnt/image` has no `keyboard_stm/` and no 52012-byte file),
**not** embedded in the kernel (`/proc/kallsyms` has no `__fw_...` symbol for it),
and the kernel's `firmware_class.path` is `/vendor/firmware_mnt/image`. Finding
it is what lets mainline run stock's complete path: the vendor port is already
built and selectable, and the only thing standing between it and a faithful
reproduction of this sequence is the firmware file.
