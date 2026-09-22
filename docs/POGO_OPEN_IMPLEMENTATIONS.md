# Open-source host-side implementations of the Samsung STM32 pogo keyboard

Survey date: 2026-09-22. Scope: every open-source implementation of the host-side
driver for the Samsung pogo-pin Book Cover Keyboard (STM32G0 MCU, I2C bootloader at
`0x51`, application at `0x2a`, active-low ATTN/DATA line) that could be found, and what
each one does to bring the MCU application up.

This document is a survey only. Nothing was built, flashed or written except this file.
Every claim is either quoted from a source with a URL/pin, or taken from a measured
result already recorded in this repository and marked as such. Items that could not be
reached or verified are listed in the last section rather than guessed.

Hardware facts supplied for this survey and treated as given: on SM-X710 the MCU is on
`89c000.i2c`, its ROM bootloader answers a full version session at `0x51`, `0x2a` NACKs
every time (transfer completes, bus idle, nothing acks), the announce line is gpio75
active-low, and stock/TWRP enumerates the same cover as `EF-DX710_v1.4.1.0`.

Local pins used below:

- this port: working tree at `7e9428f` with uncommitted changes to
  `kernel/drivers/keyboard-samsung-pogo.c` and `tests/test_pogo_startup.py`
  (`git diff` shown below where it matters).
- Samsung SM-X710 vendor drop (GPL): supplied locally at
  `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/`
  (header cites `SM-X710_EUR_15_Opensource.zip`); live stock device tree
  `/home/ms/Samsung/x710-live.dts` (decompiled from the tablet, 2026-09-18).
- agcarbajo reference clone: `/home/ms/Samsung/ubuntu-galaxy-tab-s9-ultra`
  (`origin/main` = `32273b0` locally); the remote `main` driver file is byte-identical
  to the clone's, and line numbers below match both `32273b0` and
  `main` @ `f3f7ba0`.

---

## 1. Implementations

| Project | URL / pin | Power + IRQ sequence | First `0x2a` transaction | Reset / boot-pin handling | Reports of `0x2a` not answering |
|---|---|---|---|---|---|
| **This port** (SM-X710 mainline) | `kernel/drivers/keyboard-samsung-pogo.c` @ `7e9428f` + uncommitted diff; DT `kernel/dts/sm8550-samsung-gts9wifi.dts:1878-2039` | `pogo_connect_work()` (371-404): `regulator_enable(vdd)`, `msleep(50)`, then `enable_irq(DATA)` **outside** the mutex. Attach IRQ = both edges, 20 ms work. DATA IRQ = `IRQ_TYPE_LEVEL_LOW` (DT 1916) + `IRQF_ONESHOT`, threaded-only handler. | None at startup. On an IRQ only: `pogo_irq()` (986-1079) writes `{3,0,caps}` (`caps`=1, pogo 989) then reads 3 bytes; a length of 0 or 3 is the model announcement → `pogo_hello()` (973) → `pogo_read_mcu()` (878): `CHECK_VERSION` 0x02, `GET_MODE` 0x01, `ABORT` 0x17 + 200 ms if DFU. | Normal path touches no boot pin. `swclk`=gpio12 requested `GPIOD_OUT_LOW` at probe (1136), `nrst`=gpio13 `GPIOD_OUT_HIGH` (1139). `pogo_boot_disconnect()` (691-699, BOOT0 low, NRST low 2 ms, high, 150 ms) exists but is called **only** from `pogo_bootloader_probe()` (764-798) behind `startup_diagnostics=1`. | Yes — the port's own record: every `0x2a` read NACKs, no address 0x08-0x77 acks, `0x51` answers (`AGENT.md:130-200`, `docs/POGO_EVENT_STARTUP.md`). Test 090 (`reference/boot-tests/test-090-20260922T130214Z/`) measured DATA armed at 4.19 s and **never delivered**, so `0x2a` was never asked at all. |
| **Samsung SM-X710 stock vendor** (`stm32_pogo_v3`, GPL drop) | `stm32_pogo_core_v3.c:255-310`, `stm32_pogo_fw.c:400-436, 778-792, 1086-1160`, `stm32_pogo_interrupt_v3.c:63-74, 236-278`; live DT `x710-live.dts:22212-22238` | **Probe:** instantiate `0x51` client (core 259-263) → `stm32_dev_firmware_update_menu(…,0)` (core 304): request `keyboard_stm/stm32_gts9family.bin`, enter ROM bootloader, read IC version, **BOOT0 low + NRST pulse + 150 ms**, skip the write if the version matches. **Connect edge:** `stm32_keyboard_connect()` (int 110) → `stm32_keyboard_start()` (int 63): regulator on, `stm32_delay(50)`, `stm32_enable_irq(INT_ENABLE)`. IRQ type from DT `stm32,irq_type = <0x2008>` = level-low+oneshot. | `stm32_dev_int_proc()` (int 236): header write `{3,0,caps}` (259), read 3 bytes; invalid/empty payload → `stm32_read_version()` (274) and `check_ic_work` in 10 ms (278). | `stm32_sysboot_connect()` (fw 400-436): NRST low, **SWCLK/BOOT0 high**, 3 ms, NRST high, 50 ms, BOOT0 low, SYNC 0xFF, then the same again (STEP3). `stm32_sysboot_disconnect()` (fw 778-792): **BOOT0 low, 1 ms, NRST low 2 ms, NRST high, 150 ms** — called on every probe path and after any firmware write. `stm32_power_reset()` (fn 45-55, NRST 0/3 ms/1/10 ms) only after an I2C failure at `0x2a`. | No. TWRP log shows `rst:0` (application answered first try, already running). |
| **agcarbajo/ubuntu-galaxy-tab-s9-ultra** (SM-X910 mainline) | <https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/f3f7ba08a7640f0f598a1224fe108cbce72e36a8/kernel/drivers/samsung_stm32_pogo.c>; DTS `kernel/dts/sm8550-samsung-gts9uwifi.dts:1630-1648` | **Probe:** GPIOs `boot`=gpio12 (BOOT0, out-low), `reset`=gpio13 (NRST, active-low, out-low) (1405-1412) → `samsung_pogo_probe_bootloader()` (1414) → `samsung_pogo_start_application()` (457) with the rail still **off**. **Connect edge:** `samsung_pogo_connection_work()` (1187-1244): `samsung_pogo_enable_power()` (579: regulator + MAX77816 `0x03=0x70`, `0x02=0x8e`), `msleep(50)`, `attached=true`, `set_data_irq(true)`. DATA IRQ = `IRQF_TRIGGER_LOW\|IRQF_ONESHOT` with a hard handler (1431-1447). | `samsung_pogo_read_event()` (1024): `samsung_pogo_send_header()` (655) writes `{3,0,caps_request}` then reads 3 bytes; an invalid length whose byte[2] is a model id is the announcement → VERSION `0x02` read **inside the IRQ** (1053) → `application_work` in 10 ms (1073) → `initialize_application()` (701): `GET_MODE` 0x01, `ABORT` 0x17 if not APP/EXCEPTION, 200 ms, CRC `0x03`, TC version `0x18`. | `samsung_pogo_enter_bootloader()` (269-278): NRST low, BOOT0 high, 3-4 ms, NRST high, 50 ms, BOOT0 low. `samsung_pogo_start_application()` (198-211): **BOOT0 low, NRST low 2-3 ms, NRST high, 150 ms**. Comment (200-205): *"The STM32 otherwise remains silent at its application address even when both VDDO and the MAX77816 output are present."* A **second** `start_application()` after the rail settled was added in `a6b7459` but **reverted** in `b9ba7ea`; `docs/development-notes.md:1100` now states: *"Do not reset the STM32 after enabling VDDO: that extra reset keeps the application mute."* No GO/DFU/ABORT to `0x51` anywhere. | Yes. `docs/porting-log.md` session 8: *"the application address `0x2a` kept NACKing and GPIO75 generated no IRQ"*; session 17: *"bootloader alive, application mute"*. Root causes found: (a) their own extra reset after VDDO (`8eafd2a`, `b9ba7ea`), (b) the MCU left on the V34 application (`a137837`, `docs/hardware-status.md:262-296`). |
| **Samsung SM-X910 vendor drop** (mirror of the above ground truth) | <https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/tree/main/kernel/vendor/samsung-stm32-pogo> | Same state machine as the X710 vendor driver, plus a `max77816,kbd_boost@18` on SE4 that the keyboard driver writes before the 50 ms wait. | Same `{3,0,caps}` header + 3-byte read from the DATA IRQ. | Same `stm32_sysboot_connect()` / `stm32_sysboot_disconnect()` pair; `stm32_dev_firmware_update()` ends with `disconnect()` on every path. | n/a; the project's docs record the mainline port hitting the silence instead. |
| **aaronsb/sm-x800-linux** (Tab S8+, SM-X800, working mainline port) | <https://github.com/aaronsb/sm-x800-linux/blob/main/pmaports-overlay/device/testing/linux-postmarketos-qcom-sm8450/stm32-pogo.c>; docs `docs/07-input-and-wireless.md:31-64`, `tools/README.md:132-177` | `stm32_pogo_start()` (587-613): `regulator_enable(vdd)`, `msleep(50)`, `enable_irq(attn_irq)`, plus a 3 s handshake watchdog. ATTN IRQ = `IRQF_TRIGGER_LOW\|IRQF_ONESHOT`, threaded. | `stm32_pogo_attn_isr()` (674-751): **thread-entry level gate** `if (gpiod_get_value(attn_gpio)) return` (682), then header write `{total_lo,total_hi,ep}` (194-204, `ep` doubles as caps LED), read 3 bytes; invalid payload → `read_version()` (703), `handshaken=true`, `ic_work` in 10 ms (709) → `GET_MODE`, `ABORT`+200 ms, touchpad probe, register input. | **None at startup.** `nrst`=gpio97 requested `GPIOD_OUT_HIGH` (794) and pulsed `0/3 ms/1/10 ms` **only** after a failed I2C transfer (160-165). `swclk` is deliberately left unclaimed. | Yes, and it is the project's central diagnosis: *"12,158 userspace probes of 0x2a got zero ACKs because the MCU only serves its I2C address as part of an interrupt-driven handshake — polling can never see it"* (`docs/07-input-and-wireless.md:33-38`). Their ruled-out table (`tools/README.md:138-154`) also rules out nRST held/pulsed, a full rail-off/reset/rail-on cycle, and bootloader `GO 0x08000000` for their device. |
| **Stock SM-X710 vendor tree, public mirror** | <https://github.com/flanter21/gts9wifi_kernel> branch `202505_EUR_15_X710XXU5CYD9`; DTS `kernel_platform/msm-kernel/arch/arm64/boot/dts/samsung/galaxytab/gts9wifi/gts9wifi_eur_open_w00_r04.dts` | Carries the same `stm32_pogo_*_v3` vendor stack as the local GPL drop, so the sequence is the X710 vendor column above. Its DTS rest state is `gpio12` (`swclk_gpio`) `output-low` and `gpio13` (`nrst_gpio`) `output-high` (lines 10243-10281), and the keyboard node is identical to the live tree (`:10294-10320`). **The node's `stm32_vddo-supply` is overridden to `<0x00>` in a later fragment (`:16644-16652`), so `devm_regulator_get()` fails and every `stm32_dev_regulator()` call is a no-op** — on this revision stock's rail control does nothing and the MCU still runs. | Same vendor `{len,0,id}` header + read. | Same vendor `sysboot_connect()`/`sysboot_disconnect()`; the NRST pulse with BOOT0 low is the only host-controlled app-entry on this revision. | No (vendor stack, TWRP `rst:0`). |
| **SM-X710 Android 14 vendor dump (public)** | <https://github.com/samsung-sm8550-tab/samsung_gts9wifi_dump> branch `gts9wifixx-user-14-UP1A.231005.007-X710XXU4BXHB-release-keys` | Not a driver, but the firmware provenance: `vendor/firmware/keyboard_stm/stm32_gts9family.bin` is **52,132 bytes, SHA-256 `1b48d88c23523ae205cd960e6d42725268638a15a47d8a5e52854eb01108caa3`, version field at `0x200` = `00 37 00 37` (V37)** — byte-identical to the blob the SM-X910 port obtained from Samsung, so one V37 application serves the whole gts9 family. `stm32_gts9factory.bin` is 50,164 bytes, SHA-256 `fbc49ffa0e49581cf422941ed4945d3b4698f70a772f6af36833ca40d775b34a`, `0x200` = `00 31 00 31` (V31). The sibling `android_device_samsung_gts9wifi` lists `stm32_pogo_v3.ko` in `modules.load:202` and an IDC `pogo.list = EF-DX715:EF-DX710:EF-DX725:EF-DX720:Neos`, confirming the X710 cover belongs to this protocol family. | Vendor `{len,0,id}` header + read. | Vendor `sysboot_connect`/`sysboot_disconnect`. | n/a (firmware source). |
| **Azkali Ubuntu Touch, SM-X710 (`gts9wifi`)** | <https://gitlab.com/azkali-samsung/gts9/ubports/kernel-samsung-gts9wifi> branch `android13-5.15-halium`; DTS `arch/arm64/boot/dts/samsung/galaxytab/gts9wifi/gts9wifi_eur_open_w00_r04.dts:10294-10309`; vendor driver `drivers/input/sec_input/stm32/` | Carries Samsung's full vendor driver (`stm32_pogo_*_v3`, `kbd_max77816_i2c`), so the sequence is the X710 vendor column above. Its DTS declares the same node as stock: `stm32,irq_gpio`=gpio75, `stm32,irq_conn`=gpio62, `stm32,irq_type`=0x2008, `stm32,irq_conn_type`=0x2003, `stm32,mcu_swclk`=gpio12, `stm32,mcu_nrst`=gpio13, `stm32,fw_name="keyboard_stm/stm32_gts9family.bin"`. | Same vendor path (`stm32_i2c_header_write` `{len,0,id}` + read). | Same vendor `sysboot_connect`/`sysboot_disconnect` (verified at `stm32_pogo_fw.c:778-792` in that tree). | Not documented. The port's published feature list does not mention the keyboard cover; the UT kernel tree's `firmware/keyboard_stm/` contains only Tab S7/S8 blobs (`stm32_birdie.bin` 00 25, `stm32_gts7l.bin` 00 22, `stm32_gts7llite.bin` 00 27) — **no** `stm32_gts9family.bin`, so `request_firmware()` cannot be satisfied from the package alone. |
| **postmarketOS `gts9wifi` port** (Azkali) | <https://gitlab.com/Azkali/postmarketos-gts9wifi> | No pogo/STM32 driver and no keyboard firmware package (Wi-Fi/BT/ADSP/PD-maps/CS35L45 only). | — | — | — (no driver). |
| **Fedora mainline, SM-X710** | <https://github.com/nacht20-de/gts9wifi-fedora> and fork <https://github.com/troikoss/gts9wifi-fedora> | No pogo node in `kernel/files/sm8550-samsung-gts9wifi.dts`, no `keyboard@2a`/`stm32`/pogo reference in the docs; verified the fork's `kernel/patches/` list (19 patches, none pogo) and its README status table ("Power/volume keys, book-cover lid, suspend"). | — | — | — (no driver). |
| **postmarketOS upstream pmaports** | live: <https://gitlab.postmarketos.org/postmarketOS/pmaports> (the <https://gitlab.com/postmarketOS/pmaports> copy is frozen at 2024-11-03) | No device package for `gts9wifi`/`gts9uwifi`/SM-X710/SM-X910/SM-X800 in `device/testing` (1011 entries scanned on the mirror) or `device/community`, and no `firmware-samsung-gts9*` package. The only `stm32_pogo` string in the repository is a config symbol in an archived Tab S5e downstream kernel. The X910/SM-X800 ports are out-of-tree overlays carried by their own repositories. | — | — | — (no driver). |
| **Mobian** | <https://salsa.debian.org/mobian-team>, <https://wiki.debian.org/Mobian>, <https://sources.debian.org>, <https://codesearch.debian.net> | Nothing found for any Samsung pogo keyboard; Debian source and code search are empty for `stm32_pogo`, `pogo_keyboard`, `gts9wifi` and `EF-DX710`. | — | — | — |
| **Linux mainline / LKML** | <https://elixir.bootlin.com/linux/v7.2.6>, <https://lore.kernel.org>, <https://patchwork.kernel.org>, <http://marc.info> | No patch, binding or DT for a Samsung pogo/STM32 keyboard. Verified against the v7.2.6 tree: no `stm32_pogo`/`samsung_stm32_pogo` identifier, no entry in `drivers/input/keyboard/Makefile`, no `pogo` in `vendor-prefixes.yaml` and no registered `stm` vendor prefix, no Tab S9 DT in `arch/arm64/boot/dts/qcom/Makefile`, and no `keyboard_stm`/`gts9`/`pogo` entry in `linux-firmware`'s `WHENCE`. `marc.info` returns "No hits found" for `stm32 pogo` and `ef-dx`; lore and patchwork were behind anti-bot challenges from this network. | — | — | — |

### 1.1 Details worth keeping

**The two working implementations agree on the full bring-up order.**

Samsung's own X710/X910 driver, at every probe, runs a read-only ROM-bootloader session
and then exits it (fw.c:1086-1160 → `stm32_sysboot_disconnect()`, fw.c:778-792):

```
request_firmware(mcu_fw_name); checksum;
stm32_sysboot_mcu_validation();          /* enter bootloader: NRST low, BOOT0 high, 3 ms,
                                            NRST high, 50 ms, BOOT0 low, SYNC 0xFF, STEP3 */
stm32_sysboot_i2c_read(0x08000200, ic_ver, 4);
stm32_sysboot_disconnect();              /* BOOT0 low, 1 ms, NRST low 2 ms,
                                            NRST high, 150 ms  -> run main flash */
if (version matches) skip firmware write;
```

(Citation nuance: `stm32_sysboot_mcu_validation()` itself calls `disconnect()` only on its
failure path, `fw.c:818`; on success the caller at `fw.c:1147` does it. Either way every
bootloader session ends in the NRST pulse before any `0x2a` traffic.)

Only after that does the connection edge start the keyboard
(`stm32_keyboard_start()`, interrupt_v3.c:63-74): regulator on → 50 ms → DATA IRQ enable.
The application then announces on its own; nothing in the connect path resets the MCU.

The X710 vendor ordering is strict and worth stating as one line, because every step is
in a different function (`stm32_pogo_core_v3.c:255-329`): 0x51 firmware session ending in
`sysboot_disconnect()` (BOOT0 low + NRST pulse + 150 ms) → `stm32_slave_device_init()`
→ `stm32_interrupt_init()` (both threaded IRQs requested, DATA IRQ left **disabled**)
→ `stm32_keyboard_connect()` → `stm32_keyboard_start()` = regulator on → 50 ms → DATA
IRQ enable. Reset first, power second, IRQ third, and no reset after power.

The SM-X910 mainline port reproduces that shape (`samsung_pogo_probe_bootloader()`
ending in `samsung_pogo_start_application()`, driver lines 386-458) and its design notes
state the rule explicitly (`docs/development-notes.md:1090-1103`):

> "The working sequence is strict: enter the bootloader, validate/update, drive BOOT0
> low, pulse NRST and wait 150 ms; then, on detecting GPIO62, enable VDDO and the
> MAX77816, wait 50 ms and enable GPIO75. **Do not reset the STM32 after enabling
> VDDO**: that extra reset keeps the application mute even when firmware, option bytes
> and power are all correct."

The SM-X800 port never touches `0x51` or BOOT0 at all and still works, because on that
device the application is already running: its MCU was flash-dumped and found
byte-identical to stock, and it "runs a connection state machine
(`Disconnected_sequence_proc`) and cycles at ~5 Hz because the host never completes the
handshake" (`tools/README.md:156-160`). That is the second, independent failure mode:
the application is up, but it only exposes `0x2a` inside the ATTN exchange.

**Boot-mode semantics are documented by measurement, not inference.** In
`aaronsb/sm-x800-linux` commit
[`1771293`](https://github.com/aaronsb/sm-x800-linux/commit/1771293688459ad78b7a2cd8da0317174b56b833):

> "baseline (BOOT0 low): 0x51 -> NACK / after BOOT0 pulse: 0x51 ACKed: 0x1f, SYNC 0xFF
> ACCEPTED … `gpio99` ("stm32,mcu_swclk") is wired as BOOT0. Driving it HIGH across an
> nRST pulse boots the MCU from ROM instead of application flash, and the ROM bootloader
> ACKs at 0x51 whether or not the app firmware is healthy."

(The same project corrected itself the same day in commit
[`6cce0a9`](https://github.com/aaronsb/sm-x800-linux/commit/6cce0a932b80238d0fee02e64e3da3d735d648a2):
`0x1F` is the bootloader *NACK* byte and `0x79` is the ACK. The boot-mode conclusion
stands; only the byte name was wrong.)

So `0x51` answering is a statement about the *boot mode*, not proof that the application
is healthy — and a part left in system-boot mode never serves `0x2a` until a BOOT0-low
NRST pulse returns it to main flash. The same project's hygiene rule
(`tools/README.md:120-125`): the bootloader "wedges after *any* stray or malformed
traffic and then times out on everything until the next nRST/BOOT0 pulse. A bare read
with no command pending returns `0x1F` and poisons it. **Never pre-probe**".

**V34 vs V37 (SM-X910, firmware revision).** `packaging/…/pogo-keyboard.md` in the
SM-X910 port:

| Version | Under Ubuntu | Under One UI |
|---|---|---|
| **V37** (Samsung's X910 blob) | works | works |
| V34 (older application) | *"announces no protocol ID; cover is dead"* | works |

> "V34 speaks a different one: the controller boots fine, pulses the connection line
> every ~2.1 s and never sends `0xd6`. That is the whole failure, and it looks exactly
> like a wiring or timing problem, which is why it cost several sessions."
> `flash_version=00370037` is healthy; `flash_version=00340034` means the cover will not
> work until the controller is restored.

The reporter explicitly does **not** know what downgraded the MCU ("the most likely
candidate is Samsung's `stm32_pogo_v3.ko` under One UI or Ubuntu Touch"), and rejects
"corrupt flash" as the explanation (`docs/hardware-status.md:262-274`). The official
blob is 52,132 bytes, version bytes at `0x200` = `00 37 00 37`, SHA-256
`1b48d88c23523ae205cd960e6d42725268638a15a47d8a5e52854eb01108caa3`; the ROM command
`GO 0x08000000` was accepted by the bootloader but the application stayed mute.

**SM-X710's own stock version number is 34.** This port's TWRP pretest log records
`EF-DX710, firmware 34, con:1/1, rst:0` (`AGENT.md:199`), i.e. the X710 MCU application
is the same era as the SM-X910's "V34" and stock drives it successfully — so V34 alone
is not proof of a dead cover on this device.

**The shipping V37 application is now publicly downloadable, and this unit is not running
it.** `samsung-sm8550-tab/samsung_gts9wifi_dump` (Android 14 SM-X710 dump) serves
`vendor/firmware/keyboard_stm/stm32_gts9family.bin`, and the file was downloaded and
verified here: 52,132 bytes, SHA-256
`1b48d88c23523ae205cd960e6d42725268638a15a47d8a5e52854eb01108caa3`, `0x200` =
`00 37 00 37`, vector table `SP = 0x200056c0`, reset = `0x0800c515`; the factory image
`stm32_gts9factory.bin` is V31 (`0x200` = `00 31 00 31`, SP `0x200056b8`, reset
`0x0800bd99`). This port's test 049 read `SP = 0x200056c0` but reset `0x0800c4a5` at
`0x08000000` (`AGENT.md`, test 049 entry): the stack pointer matches V37 while the reset
vector does not, so the MCU in this unit holds a **different build** from the shipping
V37 blob. The version bytes at `0x08000200` are the discriminator, and the port's
`pogo_boot_ic_version()` already reads exactly that address.

**Correction to this driver's firmware-header constants:** `POGO_FW_HEADER_L0
0x080000bc` / `POGO_FW_HEADER_G0 0x080000c0`
(`kernel/drivers/keyboard-samsung-pogo.c:53-54`) do not describe this blob — bytes
`0xbc`-`0xd0` are all zero; the `STM32` magic in the raw image is at file offsets
`0x8b1` and `0x978` (verified against the downloaded V37 file). The version offset the
driver uses, `POGO_IC_VERSION_OFFSET 0x08000200`, is correct and matches the vendor's
`STM32_IC_VERSION_OFFSET` (`stm32_pogo_v3.h`). The vendor's update rule compares
byte[3] only (`stm32_pogo_fw.c:974-981`): update if `bin[3] > ic[3]`, or `bin[3] == 0xff`,
or `ic[3] >= 0xA0`.

---

## 2. Differences that could matter

Ordered by how well the recorded evidence explains "`0x51` answers a full session,
`0x2a` NACKs at every address". Each item gives the experiment it implies.

### 2.1 The normal path never releases the MCU from system-boot mode, and BOOT0 is only sampled on an NRST edge

On the STM32G0, BOOT0 is sampled when NRST is released. Driving BOOT0 low therefore does
nothing to a part that is already sitting in the ROM system bootloader: the only way out
is a fresh NRST pulse with BOOT0 low. That is exactly what stock does at every boot
(`stm32_sysboot_disconnect()`, fw.c:778-792, reached through
`stm32_dev_firmware_update_menu(…,0)` from `stm32_pogo_core_v3.c:304`) and what the
SM-X910 mainline port reproduces at probe (`samsung_pogo_start_application()`, driver
198-211, called at 457). The SM-X910 comment is this exact symptom: *"The STM32 otherwise
remains silent at its application address even when both VDDO and the MAX77816 output are
present."* The SM-X800 measurement adds the boot-mode semantics: with BOOT0 low the
bootloader NACKs at `0x51`; only a BOOT0-high NRST pulse selects it
([commit 1771293](https://github.com/aaronsb/sm-x800-linux/commit/1771293688459ad78b7a2cd8da0317174b56b833)).
So `0x51` answering is a statement about boot mode, not about the application — and on
this hardware a Linux reboot does not power-cycle the MCU (this port's test 082), so a
part left in system-boot mode stays there indefinitely.

The rail cannot be the gate either: on the stock `r04` X710 device tree the keyboard
node's `stm32_vddo-supply` is overridden to `<0x00>`
(`gts9wifi_eur_open_w00_r04.dts:16644-16652`), making every vendor regulator call a
no-op, and stock still enumerates the cover. What is left as a host-controlled cause is
the NRST release.

This port's `pogo_connect_work()` (371-404) never does it. `pogo_boot_disconnect()`
(691-699, the correct BOOT0-low + 2 ms NRST + 150 ms sequence) runs only with
`startup_diagnostics=1`, and then only *after* the rail is on and after a bootloader
session — the state the SM-X910 port documents as leaving the application mute
(`docs/development-notes.md:1100`) and the state in which a wedged bootloader already is.

**Experiment:** on one boot, do the app-entry release exactly once and early — with the
rail still off, `swclk`/BOOT0 low, `nrst` low ≥2 ms, high, `msleep(150)` — then enable
the rail, `msleep(50)`, arm DATA, and put **no** traffic on `0x51` in that boot. Stock
runs this unconditionally on every boot, so it is idempotent when the application is
already up. The reset is a plain GPIO sequence: it does not need a preceding `0x51`
session to take effect (stock happens to run it as the tail of one), and it must come
**before** the rail is enabled — never after it. Success = a model packet serviced, or a
`CHECK_VERSION` reply at `0x2a` obtained *inside* an ATTN window. If the pad cannot be
made low first (2.3), at minimum order the pulse before the driver's `regulator_enable()`
and verify the gpio10 level with the io-register read used in test 083.

Note on history: the pulse removed as defect 2 in `docs/POGO_STARTUP_REPAIR.md` fired
after the bootloader helper, which is where the vendor puts it; the defect there was that
it also fired after a successful application read, not its position. Removing the
app-entry reset altogether leaves the port as the only implementation surveyed with no
way out of the ROM bootloader.

### 2.2 `0x2a` is only served inside the ATTN handshake, and this port has no level gate on the ATTN service

The working SM-X800 driver gates the threaded handler on the line still being asserted
(`stm32_pogo_attn_isr()`:682) and states plainly that polling `0x2a` can never work: the
MCU "only serves its I2C address as part of an interrupt-driven handshake". The SM-X910
port samples DATA in a hard handler for the same reason (driver 1120-1141:
`if (data_ready <= 0) return IRQ_HANDLED;`). This port's `pogo_irq()` is threaded-only,
does not re-check gpio75, and counts every interrupt as an announcement (1008-1012); the
uncommitted working-tree change adds a 1.5 s "ask the application directly" version read,
which both working ports predict will NACK. Test 090 already measured DATA armed and
never delivered, so the announcement path was never exercised at all.

**Experiment:** drop the direct-ask poll, add the thread-entry level gate and a hard-IRQ
level check, and log the gpio75 level and IRQ count *at arm time* and on every entry.
Service `0x2a` only from a serviced ATTN. This distinguishes "announcement missed" from
"announcement answered wrongly".

### 2.3 The rail is driven high from early boot by pinctrl, so the driver never controls the MCU's reset state

`pogo_supply` sets `output-high` on gpio10 (`sm8550-samsung-gts9wifi.dts:1996`), so the
pad is driven before the keyboard driver claims `swclk`/`nrst`; the file's own comment
records that the MCU "turns out to be powered independently of this pin". This is not the
primary gate (see 2.1: stock's rail is a no-op on r04), but it does mean the port cannot
place the MCU in a known reset state before releasing it, and any reset it issues is a
reset *after* the rail was already up. Both working implementations keep the level under
driver control (SM-X910 `pogo_vddo` pinctrl `output-low`,
`docs/development-notes.md:1075-1080`; SM-X800 `stm32_pogo_start()`).

**Experiment:** remove the output level from `pogo_supply` (leave the pad to the fixed
regulator, which drives it low until enable), confirm gpio10 reads low before
`regulator_enable()`, and hold BOOT0 low before the 2.1 pulse. If the application answers
in both rail variants, this item is closed as irrelevant to bring-up.

### 2.4 Firmware revision: the unit is not running the shipping V37 build, and a mis-versioned application can run yet never announce

On SM-X910 a V34 application "boots fine, pulses the connection line every ~2.1 s and
never sends `0xd6`", while the mainline sequence only drives V37; the fix there was
restoring Samsung's blob. Two independent measurements now point at this port's MCU
holding a non-shipping build: TWRP reports `firmware 34` for the EF-DX710
(`AGENT.md:199`), and test 049's vector-table read at `0x08000000` gives
`SP = 0x200056c0` with reset `0x0800c4a5`, whereas the shipping V37 image verified here
is `SP = 0x200056c0`, reset `0x0800c515` (see 1.1). The caveat remains that stock X710
drives firmware 34 successfully, so a revision difference alone does not prove the
application is mute for an X710-derived host sequence — but the version read is cheap and
discriminates 2.1/2.2 from a firmware problem before any further host experiment.

**Experiment:** one read-only bootloader session (rail off), `READ 0x11 0xEE` of 4 bytes
at `0x08000200` — the port's `pogo_boot_ic_version()` already does this. `00 37 00 37` =
firmware is the shipping build, so the cause is the release/ordering or ATTN problem
above. Anything else (the unit is expected to read a 34-era value) makes restoring
`stm32_gts9family.bin` — now publicly available with the hash above and the vendor's own
write-verify path — the next step; that is a flash, needs owner approval, and is outside
the scope of this survey.

### 2.5 Bootloader hygiene: stray `0x51` traffic wedges the ROM bootloader until a fresh BOOT0/NRST pulse

Recorded on hardware by the SM-X800 port: a bare read with no command pending returns
`0x1F` and "poisons" the bootloader until the next NRST/BOOT0 pulse; ACK is `0x79`
(`tools/README.md:120-125`). This port's diagnostic path reads `0x51` repeatedly without
a fresh pulse (`pogo_boot_report()` 645-665 is called at 795 and 797, after other
bootloader work) and runs 240-attempt `0x2a` polls plus bus recovery in the same window.

**Experiment:** keep `0x51` out of the normal path entirely; if a bootloader session is
ever used again, give every ROM command its own fresh BOOT0/NRST pulse and treat `0x79`
as the only proof a command landed. Compare the ATTN trace of a run with no `0x51`
traffic against one with a single clean session.

---

## 3. Not found / could not verify

- **No open-source driver for SM-X710/EF-DX710 outside this repository was found**, and
  no mainline (upstream) driver or DT binding for any Samsung pogo keyboard exists. The
  Ubuntu Touch `gts9wifi` kernel carries Samsung's vendor driver unchanged; the Fedora
  and postmarketOS `gts9wifi` ports carry no pogo support at all.
- **`agcarbajo/ubuntu-galaxy-tab-s9-ultra` is SM-X910, not SM-X710.** Its covers are
  EF-DX920/DX925/DX900/DX910/DX915; it never mentions EF-DX710. Its GPIO numbers happen
  to match this board (gpio12 BOOT0, gpio13 NRST, gpio62 CONN, gpio75 DATA, gpio10 rail)
  but its model IDs and protocol revisions are X910-specific. All 17 repositories under
  that account were enumerated; only this one contains pogo code. The further
  `ubuntu-touch-galaxy-tab-s9-ultra` and `postmarketos-galaxy-tab-s9-ultra` repos carry
  no mainline pogo driver (the Ubuntu Touch README claims EF-DX920 support through the
  vendor module). The `kquote03/ubuntu-galaxy-tab-s9-5g` and three other forks could not
  be checked: the unauthenticated GitHub API hit its rate limit (verified byte-identical
  for three forks: `crashTestDummy-droid`, `jstockdale`, `acode001`).
- **No public report of `0x2a` not answering on SM-X710, SM-X716, Tab S10, EF-DX710 or
  EF-DX810 specifically.** The `0x2a`-mute reports that do exist are for SM-X910 with an
  EF-DX920 (agcarbajo) and SM-X800 (aaronsb), both cited above. GitHub issue search for
  `EF-DX710` returns one unrelated browser bug; `EF-DX810`, `stm32_pogo` and
  `samsung_pogo` return nothing; the only EF-DX9xx issue is agcarbajo #2 (touchpad axes,
  not `0x2a`). No LKML/patchwork hit.
- **Reachable-source limits:** GitHub code search needs authentication (401) and grep.app
  is behind a Vercel challenge, so cross-repo code search was done by fetching and
  grepping full trees instead. GitLab global blob search returns 401, and Sourcegraph's
  public stream API returned zero matches even for symbols known to exist in
  `torvalds/linux`, so those two are inconclusive rather than negative. XDA threads
  (Ubuntu Touch Tab S9, Ubuntu 24.04 X910, Fedora gts9wifi) and Samsung Community return
  403 anti-bot pages and were **not read**; Reddit search is blocked; lore.kernel.org,
  patchwork.kernel.org and the postmarketOS wiki API served anti-bot challenges;
  `opensource.samsung.com` answered every endpoint with a Cloudflare 403, so nothing was
  downloaded from Samsung's own portal. Mobian and UBports were searched only through
  general web search, `sources.debian.org` (empty for `stm32_pogo`/`gts9wifi`) and
  `codesearch.debian.net` (0 results for `stm32_pogo`, `pogo_keyboard`, `EF-DX710`), not
  exhaustively.
- **Upstream mainline is verified empty rather than merely unsearched:** Bootlin Elixir
  `linux/v7.2.6` has no `stm32_pogo` or `samsung_stm32_pogo` identifier,
  `drivers/input/keyboard/Makefile` has no such entry, `vendor-prefixes.yaml` contains no
  `pogo` and has no registered `stm` vendor prefix (so `stm,stm32_pogo` is unofficial),
  `arch/arm64/boot/dts/qcom/Makefile` has no Tab S9 DT, and `linux-firmware`'s `WHENCE`
  has no `keyboard_stm`/`gts9`/`pogo` entry.
- **Upstream pmaports is verified empty:** the live repository is
  `gitlab.postmarketos.org/postmarketOS/pmaports` (the gitlab.com copy is frozen at
  2024-11-03); it has no `gts9`/`x710`/`x716`/`x910` device package and no such issues or
  MRs. The only `stm32_pogo` string in the whole repository is a config symbol in an
  archived Samsung Tab S5e downstream kernel
  (`device/archived/linux-samsung-gts4lvwifi/config-…:2060: CONFIG_KEYBOARD_STM32_POGO=y`)
  — a second downstream tree that could be diffed against the X710 one. Also, Azkali's
  pmOS `gts9wifi` port ships a `gts9wifi-bookcover-input` service for a **Bluetooth**
  cover (vendor `0x04E8`, product `0x7021`); it is not pogo support.
- **The quoted `[sec_input]` log gists are Tab S7 (`gts7l`), not SM-X710.** All five
  `BUP-BIP-BOP` gists show `4.19.113-samsung-gts7l` / `4.19.81-samsung-gts7l`,
  `mcu_fw_name:keyboard_stm/stm32_gts7l.bin`, `model_name:EF-DT870/EF-DT630`, and in every
  one the cover was absent (`connect_state 0` → `keyboard_stop`), so none of them ever
  reaches `0x2a`. They are evidence for the `0x51` protocol only.
- **General web searches** for the SM-X710/EF-DX710 Linux pogo keyboard return only
  retail accessory listings; no port, patch or forum thread surfaced.
- **V34 is not publicly available** and its origin is unexplained; the public dumps and
  the Ubuntu Touch `gts9wifi` tree ship only V37/V31 and Tab S7/S8 blobs respectively.
  Whether the EF-DX710's `firmware 34` corresponds to the SM-X910 "V34" was not verified;
  if the unit's `0x08000200` reads a 34-era value there is no public V34 image to restore
  it with, only the V37 blob.
- **The X710 vendor source and live device tree are local copies**, not URLs: the
  `stm32_pogo_v3` line numbers above refer to
  `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/` and
  `/home/ms/Samsung/x710-live.dts`, whose provenance is the Samsung GPL drop named in
  the driver header. The public download page for that drop was not re-fetched here.
- **No keep-alive, heartbeat or wake command was found in any implementation.** The
  closest things are the vendor's own `check_ic_work` (10 ms after the model announce),
  `check_conn_work` (250 ms) and `check_init_work` (500 ms), and the SM-X800 port's 3 s
  handshake watchdog. The MCU's own ~2.1 s CONN pulse in the failure state is the
  accessory asking to be acknowledged, not a host keep-alive.
