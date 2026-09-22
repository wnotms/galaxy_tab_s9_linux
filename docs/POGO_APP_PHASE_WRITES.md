# The vendor's application phase, write by write (SM-X710 / EF-DX710, `stm32_pogo_v3`)

Scope: every I2C transaction Samsung's own X710 driver performs **once the application
at `0x2a` is in use**, in the order it performs them, plus what that says about the
"start reporting" step. Sources, all read locally:

| label | path |
| --- | --- |
| **VENDOR** | `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/` (official SM-X710 GPL drop, `CONFIG_KEYBOARD_STM32_POGO_V3=m` in `arch/arm64/configs/vendor/kalama-gki_defconfig:1367`) |
| **IMPORT** | `kernel/drivers/input/samsung-pogo/` in this repository (the same driver adapted for mainline; `stm32_pogo_interrupt_v3.c` line numbers differ) |
| **PORT** | `kernel/drivers/keyboard-samsung-pogo.c` in this repository |
| **DT** | `/home/ms/Samsung/kernel_platform/msm-kernel/arch/arm64/boot/dts/samsung/galaxytab/gts9wifi/gts9wifi_eur_open_w00_r04.dts` (fragment@70/71) |
| **STOCK-LOG** | `reference/boot-tests/test-055-20260922T071600Z/stock-i2c-byte-log.txt` and `reference/twrp-pogo-working/bringup-cycle-dmesg.log:20-54` — the vendor driver's own `debug_level=1` byte log, captured on this unit in TWRP, where the keyboard works |

Notation: `W:` is one `i2c_master_send()` transaction to `0x2a`; `R n:` is one
`i2c_master_recv()` of `n` bytes. The MCU reports its own device id in the third byte
of the reply header, so `03 00 02` means "total size 3, model/event 2".

## 1. How a frame is built (three primitives, no others)

| primitive | vendor | bytes it puts on the wire |
| --- | --- | --- |
| `stm32_i2c_write_burst(client, buf, n)` | `stm32_pogo_i2c_v3.c:80-141` (`i2c_master_send_dmasafe`, `:103`) | `buf[0..n-1]` as one write |
| `stm32_i2c_header_write(client, ed_id, payload)` | `stm32_pogo_i2c_v3.c:143-154` | `W: (payload+3)&0xff, (payload+3)>>8, ed_id` |
| `stm32_i2c_reg_write(client, ed_id, reg)` | `stm32_pogo_i2c_v3.c:156-171` | `W: 04 00 ed_id`, then `W: reg` |
| `stm32_i2c_reg_read(client, ed_id, reg, len, out)` | `stm32_pogo_i2c_v3.c:173-211` | `W: 04 00 ed_id`, `W: reg`, `R 3`, `R payload` |
| `stm32_i2c_read_bulk(client, buf, n)` | `stm32_pogo_i2c_v3.c:22-78` | `R n` |

Endpoint ids are named in `pogo_notifier_v3.h:17-23`: `ID_MCU 1`, `ID_TOUCHPAD 2`,
`ID_KEYPAD 3`, `ID_HALL 4`, `ID_ACESSORY 5`. The port implements exactly these
primitives (`pogo_write` `:98`, `pogo_read` `:105`, `pogo_read_reg` `:112`,
`pogo_write_reg` `:132`), so any difference below is a difference in *which* frames are
sent, not in how they are framed. The stock byte log confirms the framing byte for byte
(`04 00 01` + `02` → `07 00 01` + `00 01 04 01`, i.e. hw 0, model 1, fw 1.4).

## 2. `stm32_interrupt_init()` — and the two device-tree values

`stm32_pogo_core_v3.c:312` calls `stm32_interrupt_init()` (`stm32_pogo_interrupt_v3.c:482-535`).
It performs **no I2C at all**:

* `gpio_to_irq(gpio_int)` / `gpio_to_irq(gpio_conn)` (`:501`, `:509`);
* `request_threaded_irq(dev_irq, NULL, stm32_dev_isr, dtdata->irq_type, ...)` (`:518`);
* `request_threaded_irq(conn_irq, NULL, stm32_conn_isr, dtdata->irq_conn_type, ...)` (`:524`);
* `stm32_enable_conn_wake_irq(stm32, true)` (`:531`), then `stm32_enable_irq(stm32, INT_DISABLE_NOSYNC)` (`:532`) — the DATA IRQ is requested **disabled** and is only enabled later by `stm32_keyboard_start()` (`:74`).

**`stm32,irq_type = <0x2008>` and `stm32,irq_conn_type = <0x2003>` are host IRQ flags and
are never written over I2C.** They are parsed at `stm32_pogo_core_v3.c:130-144` and their
only consumers are the two `request_threaded_irq()` calls above. The stock capture prints
them as decimal Linux flags — `irq_type property:2008, 8200` and `irq_conn_type
property:2003, 8195` (`reference/twrp-pogo-working/boot-time-pogo-sequence.txt:8-9`) — and
they decode exactly to the driver's own fallbacks (`stm32_pogo_core_v3.c:132`, `:140`):
`0x2008 = IRQF_ONESHOT(0x2000) | IRQF_TRIGGER_LOW(0x8)`,
`0x2003 = IRQF_ONESHOT(0x2000) | IRQF_TRIGGER_FALLING(0x2) | IRQF_TRIGGER_RISING(0x1)`.
No command in `stm32_pogo_v3.h:87-103` carries those values, and no vendor code path
sends them.

## 3. Ordered table — every write on the normal application-phase boot path

Order is the boot order. "Stock capture" cites the observed frame where the byte log
covers that step. The 0x51 ROM-bootloader traffic that precedes all of this
(`stm32_pogo_fw.c:1086-1160`) is out of scope except for its tail:
`stm32_sysboot_disconnect()` (`stm32_pogo_fw.c:778-792`, BOOT0 low → NRST low 2 ms →
high → 150 ms) is the reset that actually starts the application, and it is what the port
reproduces at `pogo_connect_work()` `:412-425`.

| step | when / function + file:line | bytes on the wire (all to `0x2a`) | purpose | mainline port |
| --- | --- | --- | --- | --- |
| 1 | **ATTN asserted**, `stm32_dev_isr` → `stm32_dev_int_proc`, `stm32_pogo_interrupt_v3.c:259` (import `:266`) | `W: 03 00 <caps>` — `<caps>` = `stm32_caps_led_value`: **`01`** normally, **`02`** when the Caps Lock LED is on (`stm32_pogo_keyboard_v3.c:250-263`) | the only read-out request in the protocol: "hand me your next queued packet"; the third byte carries the Caps-Lock LED state | **YES** — `pogo_irq()` `:1023`, `:1070` writes `{3,0,caps}`; `p->caps` is 1 (`:1200`) or 2 (`pogo_led()` `:1151`). Stock capture: `03 00 01` → `R 3: 03 00 02` |
| 2 | same branch (`payload_size == 0`), `stm32_read_version()`, `stm32_pogo_fn_v3.c:114` (called at `interrupt_v3.c:274`) | `W: 04 00 01` + `W: 02` (CHECK_VERSION), then `R 3` + `R 4` | reads hw rev / model / fw minor / fw major | **YES** — `pogo_read_reg(p, POGO_CMD_CHECK_VERSION, …)` in `pogo_read_mcu()` `:932` |
| 3 | **+10 ms**, `check_ic_work` → `stm32_set_mode(MODE_APP)`, `stm32_pogo_fn_v3.c:222` (`check_ic_work` scheduled at `interrupt_v3.c:278`) | `W: 04 00 01` + `W: 01` (GET_MODE), then `R 3` + `R 1` | reads the MCU mode (1 = APP) | **YES** — `pogo_read_mcu()` `:978` |
| 4 | only if the mode is neither APP nor EXCEPTION, `stm32_pogo_fn_v3.c:234` (`cmd = STM32_CMD_ABORT 0x17`) | `W: 04 00 01` + `W: 17` | leave DFU, run the application bank | **partly** — `pogo_read_mcu()` `:990` writes `17` only when the mode reads 2 (DFU). On this unit the mode reads 1, so stock does not send it either (capture: `stm32_set_mode: already same mode buff:1, mode:1`) |
| — | `stm32_set_mode()` ends with an **unconditional** `stm32_delay(200)` (`stm32_pogo_fn_v3.c:242`) | *no bytes — 200 ms of bus silence* | separation between the mode query and the info reads | **NO** — the port's only `msleep(200)` is inside the DFU branch (`:991`), so its bus goes quiet ~200 ms earlier than stock's |
| 5 | `check_ic_work`, `stm32_read_crc()`, `stm32_pogo_fn_v3.c:99` (called `interrupt_v3.c:203`) | `W: 04 00 01` + `W: 03` (CHECK_CRC), then `R 3` + `R 4` | 32-bit application CRC (fw-update comparison) | **NO** — never sent. Stock capture: `04 00 01`/`03` → `07 00 01`/`6E 37 DF EA` |
| 6 | `check_ic_work`, `stm32_read_tc_version()`, `stm32_pogo_fn_v3.c:182` (called `interrupt_v3.c:209`) | `W: 04 00 02` + `W: 18` (GET_TC_FW_VERSION **on endpoint 2**), then `R 3` + `R 6` | touch controller version; `major 0xFF, minor 0` is the vendor's "no touchpad" signature | **NO** — never sent. Stock capture: `04 00 02`/`18` → `09 00 02`/`09 00 FF 00 00 00` |
| 7 | only if TC major != 0xff **or** TC minor != 0: `stm32_read_tc_crc()`, `stm32_pogo_fn_v3.c:167` (called `interrupt_v3.c:216`) | `W: 04 00 02` + `W: 19`, then `R 3` + `R 2` | touch controller CRC16 | **NO** — and skipped in stock on this unit too: TC major reads `0xFF`/minor `0`, so `interrupt_v3.c:215` is false and neither this nor step 8 happens (the byte logs contain no `19`) |
| 8 | same condition: `stm32_read_tc_resolution()`, `stm32_pogo_fn_v3.c:151` (called `interrupt_v3.c:222`) | `W: 04 00 02` + `W: 1A`, then `R 3` + `R 4` | touchpad geometry | **NO** — skipped in stock on this unit as well |
| 9 | **every later ATTN** (`interrupt_v3.c:292-341`) | `W: 03 00 <caps>` then `R 3`, and if the size is > 3, `R payload` | event drain: id `2` touchpad, `3` keypad, `4` hall, `5` accessory; payload `03 00 05` is dropped as noise (`:297`) | **YES** — same fetch at `pogo_irq()` `:1070-1100` |

Host-only steps interleaved with the above, for completeness: `atomic_set(check_ic_flag)`
and `schedule_delayed_work(check_ic_work, 10 ms)` (`interrupt_v3.c:277-278`),
`check_conn_flag` + `stm32_send_conn_noti()` (`:279-280`), and
`kbd_max77816_control(booster_power_voltage)` (`:282`).

### The booster call is provably a no-op on this board

`kbd_max77816_control_init()` (`kbd_max77816_i2c.c:88-89`) and `kbd_max77816_control()`
(`:117-120`) both `return 0` before touching I2C when
`stm32->dtdata->booster_power_model_cnt == 0`, and the X710 node has **no**
`stm32,booster_power_models` property at all
(`gts9wifi_eur_open_w00_r04.dts:10294-10318`; the property is counted at
`stm32_pogo_core_v3.c:198-219`, and the node itself prints `booster_power_cnt:0(0)`,
`reference/twrp-pogo-working/boot-time-pogo-sequence.txt:14`). The device's own stock log
says the same thing: `stm32_dev_int_proc: kbd_max77816_control : not support device`
(`reference/boot-tests/test-047-20260922T060344Z/last_kmsg.txt:303`). Whatever is missing,
it is not the keyboard booster.

## 4. Writes that are not on the boot path (same protocol, different triggers)

| function + file:line | bytes | purpose |
| --- | --- | --- |
| sysfs `write_cmd` (non-SHIP builds), `stm32_pogo_cmd_v3.c:483` | `W: 04 00 01` + `W: <reg>` | raw MCU register write, factory/debug |
| `stm32_fw_update()`, `stm32_pogo_cmd_v3.c:342` → `stm32_set_mode(MODE_DFU)` (`fn_v3.c:218`) | `W: 04 00 01` + `W: 06` | ENTER_DFU_MODE |
| `stm32_fw_update()`, `cmd_v3.c:358/363/370/382/400` | `W: 04 00 01` + `W: 00/12/13/04/05` | GET_PROTOCOL_VERSION, GET_PAGE_SIZE, START_FW_UPGRADE (unprotect+erase), GET_TARGET_FW_VERSION, GET_TARGET_FW_CRC32 |
| `stm32_write_fw()`, `cmd_v3.c:284-288` | `W: <page+8 LE> 01` (e.g. `88 00 01` for 128-byte pages) then `W: 14 <page data> <crc32 LE>` | WRITE_PAGE (`15` = WRITE_LAST_PAGE for the TC) |
| `stm32_fw_update()` exit, `cmd_v3.c:413` / `:434` | `W: 04 00 01` + `W: 16` (GO) / `W: 17` (ABORT) | switch to the target bank / stay on the boot bank |
| `stm32_tc_fw_update()`, `cmd_v3.c:682` | `W: 04 00 02` + `W: 13` | START_FW_UPGRADE on the touchpad endpoint; the same function ends by sending `17` to **`ID_MCU`** (`cmd_v3.c:734`) |
| `stm32_pogo_i2c_v3.c:103` | *transport* | every `W:` above is one `i2c_master_send_dmasafe()`; every `R:` is one `i2c_transfer()` read |

## 5. What the commands are called

The vendor header names them (`stm32_pogo_v3.h:87-103`, identical in
`stm32_pogo_i2c.h:86-102`): `0x00` GET_PROTOCOL_VERSION, `0x01` GET_MODE,
`0x02` CHECK_VERSION, `0x03` CHECK_CRC, `0x04` GET_TARGET_FW_VERSION,
`0x05` GET_TARGET_FW_CRC32, `0x06` ENTER_DFU_MODE, `0x11` GET_PAGE_INDEX,
`0x12` GET_PAGE_SIZE, `0x13` START_FW_UPGRADE, `0x14` WRITE_PAGE,
`0x15` WRITE_LAST_PAGE, `0x16` GO, `0x17` ABORT, `0x18` GET_TC_FW_VERSION,
`0x19` GET_TC_FW_CRC16, `0x1A` GET_TC_RESOLUTION. The ROM bootloader has its own set
(`stm32_pogo_v3.h:173-186`). No payload semantics are documented anywhere in the drop;
the reply layouts above are inferred from the vendor's own parsing code and confirmed by
the stock byte log. Modes: `MODE_APP 1`, `MODE_DFU 2`, `MODE_EXCEPTION 3`
(`stm32_pogo_v3.h:298-302`).

## 6. The key-reporting path, end to end, and what the host must have done first

```
MCU scans its matrix
  → queues a packet with id 3 (ID_KEYPAD) and payload = N × u16 LE
  → asserts ATTN (active-low, gpio75)
host: stm32_dev_isr()             interrupt_v3.c:347   first act is a level gate:
                                                     return if the line is *released*
  → stm32_dev_int_proc()          interrupt_v3.c:236
  → W: 03 00 <caps>               :259
  → R 3 → payload_size = size-3   :263-268
  → R payload                     :292
  → pogo_notifier_notify(3, payload)  :302-305
  → keyboard notifier             keyboard_v3.c:308-310 → pogo_kpd_event()
  → pogo_kpd_event_bypass()       keyboard_v3_bypass.c:107-145
      struct stm32_keyevent_data { u16 key_value:15; u16 press:1 }  (keyboard_v3.h:51-58)
      input_report_key(input_dev, key_value, press)   :140
```

For the ROW models the same payload is `{press:1, col:5, row:3}` and is mapped through the
DT keymap (`keyboard_v3_row.c`, `struct stm32_keyevent_data_row`, `keyboard_v3.h:39-49`);
the EF-DX710 announces model `0x02`, which `keypad_check_input_dev()`
(`keyboard_v3_common.c:16-28`) classifies as `STM32_BYPASS_MODEL`, i.e. the pre-decoded
`key_value` form the port already implements (`pogo_irq()` `:1115-1141`).

Host-side state that must be true before a key packet can arrive **and be accepted**:

1. the rail enabled and 50 ms elapsed, then **the DATA IRQ enabled** —
   `stm32_keyboard_start()`, `interrupt_v3.c:67-74`; the IRQ is requested disabled
   (`:532`) and firmware probing disables it again (`stm32_pogo_fw.c:1112`, re-enabled
   `:1172`);
2. the MCU's own announcement consumed — the model id from that exchange is what selects
   the keypad handler (`keyboard_v3_common.c:20-27`); without it `pogo_kpd_event` is
   `NULL` and events are dropped (`keyboard_v3.c:289-291`);
3. the ATT**N handshake is the only way in**: `0x2a` is answered while the line is
   asserted, and the vendor's first ISR act is the level gate (`interrupt_v3.c:353-354`).
   The port gained the equivalent gate in `f9a0361` (`keyboard-samsung-pogo.c:1052-1056`);
4. `connect_state` true, otherwise `stm32_i2c_write_burst()`/`read_bulk()` return
   `-ENODEV` while `conn_lock` is held (`stm32_pogo_i2c_v3.c:31-35`, `:88-92`).

Nothing else is written to make the MCU raise ATTN: the MCU pushes by itself, and the
host's only write in steady state is the `03 00 <caps>` fetch.

## 7. The most likely missing step

Samsung's sources contain **no explicit "start reporting" command** — no mode-set, no
caps/LED write, no enable, no keep-alive, no settings write, no interrupt-configuration
write anywhere in the application phase (sections 3 and 4 are the complete set). So the
candidate has to come from the one place where the port's traffic and stock's diverge:
the port stops after GET_MODE, stock sends four more frames. In both stock captures the
MCU's **next** ATTN — the hall event `R 3: 04 00 04` + `R 1: 02` — arrives 0.2 ms after
the last of them (touchpad-version payload read at `70.723751`,
`bringup-cycle-dmesg.log:50`; next fetch at `70.723943`, `:52`), i.e. the application's
next report follows the *completed* sequence and never comes when the sequence is cut
short. (In the second capture the same two frames are 0.19 ms apart at 18.531993 →
18.532184, `stock-i2c-byte-log.txt:30` → `:32`.)

### Candidate 1 (most likely): finish stock's post-announcement sequence

Send, in this order, right after the port's existing GET_MODE read — and keep stock's
200 ms of silence between the mode read and the next frame
(`stm32_pogo_fn_v3.c:242`):

```
W: 04 00 01      (header, ep 1 = ID_MCU, payload size 1)
W: 03            CHECK_CRC                -> R 3 (07 00 01) + R 4 (crc32 LE)
W: 04 00 02      (header, ep 2 = ID_TOUCHPAD)
W: 18            GET_TC_FW_VERSION        -> R 3 (09 00 02) + R 6 (09 00 ff 00 00 00)
```

If only one frame is to be tried, use the second pair: `W: 04 00 02` then `W: 18` — it is
the frame stock sends **immediately before** the MCU produces its next ATTN, and it is the
only frame in the whole sequence that addresses the other endpoint.

Evidence: (a) the two independent stock byte captures show exactly this order and nothing
else (`stock-i2c-byte-log.txt:22-31`; `bringup-cycle-dmesg.log:42-51`); (b) the MCU's
hall ATTN 0.2 ms after the last frame; (c) the working SM-X800 mainline port implements
this same post-handshake step (`stm32_pogo_ic_work()`: GET_MODE → ABORT → GET_TC_FW_VERSION
→ GET_TC_RESOLUTION, then it registers the input device) and reports working keys;
(d) the vendor calls the whole thing from `check_ic_work`, whose final act is
`atomic_set(&stm32->enabled, true)` (`interrupt_v3.c:233`) — the vendor's own name for
"the IC is up".

Counter-evidence, stated plainly: steps 5-8 are reads, and the vendor's own comments
describe them as informational (CRC for the fw-update comparison, TC version/resolution
for the touchpad driver), never as a precondition for reporting. They are the only
difference left on the wire, but "the MCU gates reporting on it" is an inference from
timing, not a documented rule.

### Candidate 2 (cheap discriminator): one polled fetch that is not ATTN-driven

Immediately after the frames above, without waiting for the announce line, write the
port's existing fetch once more:

```
W: 03 00 01      (03 00 02 when the Caps Lock LED is on)
```

Evidence: the MCU retries its own announcement when the host does not answer — the port's
announce line toggled with a ~600 ms cadence for ~20 s in tests 087/088
(`reference/boot-tests/test-087-20260922T113739Z/README.md`), and the SM-X800 project
describes the same "connection state machine cycling because the host never completes the
handshake". If the hall packet is queued behind the model announcement but its ATTN
re-assertion fell inside the window in which `IRQF_ONESHOT` had the line masked while the
port's threaded handler ran the version/mode reads, a single polled fetch returns
`R 3: 04 00 04` + `R 1: 02` — or an empty header, which equally settles the question.

Counter-evidence: stock never polls without ATTN in either capture — the second fetch is
always an interrupt — so this is a diagnostic probe, not a reconstruction of stock, and it
puts a request on the bus in a state the vendor never requests in. Treat a negative result
as informative only if the port first reproduces candidate 1's sequence exactly.

## 8. Leads these sources close (do not spend a device run on them)

* **The MAX77816 keyboard booster.** `booster_power_model_cnt == 0` on this node
  (`kbd_max77816_i2c.c:88`, `:117`), the DT has no `stm32,booster_power_models`, and the
  device's own stock log prints `kbd_max77816_control : not support device`
  (`test-047…/last_kmsg.txt:303`). The call at `interrupt_v3.c:282` cannot be the missing
  step.
* **`0x2008`/`0x2003` as MCU commands.** They are Linux `request_threaded_irq()` flags
  (section 2) and appear nowhere on the wire; the port's DT uses the equivalent
  `IRQ_TYPE_LEVEL_LOW` (`kernel/dts/sm8550-samsung-gts9wifi.dts:1916`).
* **An LED/caps write.** There is none: Caps Lock is transported as the third byte of the
  fetch request (`stm32_caps_led_value`, `stm32_pogo_keyboard_v3.c:250-263`), which the
  port already sends.

## 9. Could not determine

* **Which of the three omitted actions is the gate** — CHECK_CRC (candidate 1a), the
  touchpad-endpoint version read (1b), or the 200 ms settle itself. Nothing in the vendor
  drop states that any of them is a precondition for event reporting; only a run that adds
  them one at a time can separate them.
* **The MCU-side meaning of a "fetch with nothing pending."** Every vendor fetch is
  triggered by ATTN; what the application answers to an unsolicited `03 00 01` (candidate
  2) is unknown, and a negative answer may mean "no packet" or "protocol violation".
* **Whether the third byte of the fetch is an endpoint id or the Caps-Lock LED state.**
  The vendor passes `stm32_caps_led_value` (1/2) there but passes real endpoint ids in the
  register frames; the SM-X800 port documents it as the LED state. No header names it.
* **Why the reply to the model announcement carries `02` in the same byte position that
  event replies use for the endpoint id.** `keyboard_v3_common.c:20-27` plus the stock
  log's `input_name: Book Cover Keyboard Slim (EF-DX710)` prove the vendor reads it as the
  keyboard model, but the firmware's own framing rule is not documented.
* **The application's internal gate.** The shipping V37 image is available locally
  (`.work/firmware/keyboard_stm/…/stm32_gts9family.bin`, 52,012 bytes) but this environment
  has no ARM disassembler (`objdump` has no arm target, no capstone), so it was not
  examined; the unit itself runs a different (V34-era) build, so the blob would only be
  circumstantial in any case.
* **Non-I2C explanations that this document does not exclude** — GENI transfer-path
  differences, the SWCLK/BOOT0 rail ordering and the `pogo_supply` pinctrl `output-high`
  (`kernel/dts/sm8550-samsung-gts9wifi.dts:1996`) are covered by
  `docs/GENI_TRANSFER_DIFF.md` and `docs/POGO_OPEN_IMPLEMENTATIONS.md`; this document only
  settles what Samsung's driver writes, and it writes nothing the port is missing *except*
  the four frames of candidate 1.
