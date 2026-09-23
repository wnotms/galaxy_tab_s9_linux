# Bring-up history moved out of the board DTS

`kernel/dts/sm8550-samsung-gts9wifi.dts` describes the hardware. This file keeps the
experiment record that used to live in its comments, so the board description can state
facts and reasons while the measurements stay findable.

Nothing here is new evidence: every entry summarises a test that is already archived under
`reference/boot-tests/`. Follow the link for the raw logs, the flashed artifact hashes and
the owner's observation.

The rule applied when the comments were rewritten: the DTS keeps hardware facts,
electrical relationships, why a property is required, why a node is disabled and the
official Samsung correspondence. Numbered experiments, owner observations, disproved
hypotheses and accounts of what was tried belong here.

## Display and DSI

| Source | Recorded fact |
| --- | --- |
| [test 015](../reference/boot-tests/test-015-20260921T132049Z/README.md) | The ABL splash lives in a command-mode panel that never refreshes, so binding that region through `/chosen` put the console on a surface nobody could see. `/chosen` is therefore deliberately empty and the console comes from the DRM panel pipeline. |
| [test 033](../reference/boot-tests/test-033-20260921T154352Z/README.md) | With mdss/mdpu/mdsi/dsi-phy and the ANA38407 panel driver ported, `msm_dpu` (ae01000) and `msm_dsi` (ae94000) both bound while `ae90000.displayport-controller` stayed in the deferred list: `/sys/class/drm/` held only `version`, `/proc/fb` was empty and no console was created. This is why `&mdss_dp0` stays disabled. |
| — | Disproved hypothesis: `qcom,defer-hpd-until-first-resume` is not a mainline property. It comes from the SM-X910 port's msm-dp patch and explains nothing here. |
| [test 040](../reference/boot-tests/test-040-20260921T174149Z/README.md) | The panel first displayed with the official X710 revision-D sequence - the DDIC's own power-on and refresh-mode programming, not DSC and not the DPU. |
| [test 041](../reference/boot-tests/test-041-20260922T001026Z/README.md), [test 042](../reference/boot-tests/test-042-20260922T001407Z/README.md) | Both first-enable experiments failed: quiescing the PHY lanes and cycling the inherited host/PHY link left the first panel ID at `00 00 00`, and only the framebuffer blank cycle recovered `80 00 04`. See `DISPLAY_OFFLINE_AUDIT.md` for why the premature CTL kickoff patch is also retired. |
| owner observation | The panel's cold-boot recovery needs a suspend/resume cycle, which is why the volume keys carry `wakeup-source`. |

## Pogo keyboard (STM32)

| Source | Recorded fact |
| --- | --- |
| [test 058](../reference/boot-tests/test-058-20260922T074000Z/README.md) | `pogo_supply output-low`: the rail came up with BOOT0 low, 60 s of read-only polling got no answer from the application, and the bootloader then took the `0xFF` sync first try (version `0x12`, IC `00340034`). Power-on ordering is therefore not the cause. Since this test gpio10 is held low until the driver enables the rail. |
| [test 081](../reference/boot-tests/test-081-20260922T105000Z/README.md) | Adding the keyboard's `pogo_swclk`/`pogo_nrst` states to the rail regulator's pinctrl made the keyboard driver's own pinctrl apply fail with `-EINVAL` and its probe never completed: one pinctrl group cannot be applied by two devices. This is why `pogo_supply` claims only the rail pin. |
| [test 082](../reference/boot-tests/test-082-20260922T110000Z/README.md) | With nothing touched at all - no rail, no pin writes, no IRQ arming - the application was already running and pulsed announce low about every 600 ms. The MCU is not powered by gpio10 and runs before any driver probes. |
| [test 083](../reference/boot-tests/test-083-20260922T111000Z/README.md) | With the pin configured `output-low`, pin 10 read `io 0x0` thirty seconds in while `regulator_is_enabled(pogo-vdd)` was true: the pinconf level won over the regulator's own write, so the level must not be pinned low. |
| [test 066](../reference/boot-tests/test-066-20260922T083400Z/README.md) | `irq_get_irqchip_state(..., IRQCHIP_STATE_LINE_LEVEL, ...)` is not implemented by this platform's irqchip (`level -1`), so the announce line is claimed as a GPIO descriptor, matching Samsung's `stm32,irq_gpio` + `gpio_to_irq`. |
| [test 072](../reference/boot-tests/test-072-20260922T092000Z/README.md) | Stock reads `int:1` and `con:1/1` in every status line, while this board's free-floating connector leaves the lines toggling; the vendor state machine then alternates `keyboard_start`/`keyboard_stop` and never reaches the application read. This is why gpio75/gpio62 carry `bias-pull-up`. |
| [test 059](../reference/boot-tests/test-059-20260922T074500Z/README.md) | `&i2c15` moved 100 kHz -> 400 kHz to match stock (`qcom,clk-freq-out` absent, vendor log "Bus frequency is set to 400000Hz"). Disproved: 60 s of read-only polling at 400 kHz found nothing, because the application was never alive - the app-entry reset did not exist yet. |
| [test 097](../reference/boot-tests/test-097-20260922T135809Z/README.md) | 400 kHz re-applied with the app-entry reset present: the handshake succeeded, but key presses still produced one interrupt and one packet. The bus rate is excluded as the cause of the silence. |

## Storage

| Source | Recorded fact |
| --- | --- |
| [test 013](../reference/boot-tests/test-013-20260921T131039Z/README.md) | Mainline UFS did not enumerate on this board, and a UDC existed in `/sys/class/udc` while the host saw no device - which is why `dr_mode = "peripheral"` is forced. |
| [test 020](../reference/boot-tests/test-020-20260921T140306Z/README.md) | Storage came up with the `CONFIG_QCOM_PDC` fix: microSD (`mmc1`) and UFS (`sda`..`sdf`) both enumerate. The SM-X910 UFS TX pull-down patch is not needed on this board. |

## USB

| Source | Recorded fact |
| --- | --- |
| [test 021](../reference/boot-tests/test-021-20260921T141444Z/README.md) | The Samsung eUSB2 init patch is wrong for this board: with it the kernel never reached userspace and no gadget appeared on the host, where test 020 without it produced a host-visible device. |
| [test 029](../reference/boot-tests/test-029-20260921T151542Z/README.md) | The gadget's CDC-ACM function was the failing part, not the PHY; the Windows COM path is the ACM endpoint `/dev/ttyGS0`. See `USB_SERIAL_CONSOLE.md`. |
| — | Charging policy: the board allows 3 A at 9 V on the switching charger, the fast path is the SM5440 2:1 pump on a PPS contract, and `op-sink-microwatt` stays at the stock 15 W because tcpm applies it only to programmable operating points. |

## Pinctrl and buses

| Source | Recorded fact |
| --- | --- |
| — | At 1 MHz Fast-Mode Plus in FIFO/PIO mode the QUPv3 hub SE accepts `M_CMD` but never drives the bus (bus idle, both lines high, zero interrupts): the QUP core clock available to PIO is not enough for FM+. This is why `i2c_hub_6` runs at 400 kHz. |
| — | With mainline's 2 mA drive strength the GENI controller never completed the first transfer and returned `-110` after about a second, surfacing as "Timeout waiting for OTP boot" while the rail and the shared reset were verifiably correct. The measurement was taken while SE6 was still at 1 MHz; the 8 mA setting is kept as Samsung's own value. See `GENI_TRANSFER_DIFF.md`. |
| — | Enabling the SE3 hub controller in default FIFO/PIO mode resets the SE and makes the complete SSC registry disappear, which is why the touchscreen bus runs through GPI DMA. |
| — | Listing `hub_i2c4` in the ADSP's `pinctrl-0` alongside the SM5440's SE3 GPI-DMA use makes pinctrl reject the probe with `pin GPIO_22 already requested by 98c000.i2c`. |

## Regulators

| Source | Recorded fact |
| --- | --- |
| — | On this board, omitting the two sensor rails correlates with the sensors PD watchdog during SSC bring-up; mainline `qcom_q6v5_pas` only manages cx/px, so the rails are marked always-on. |
| — | The experimental S4G parent for PM8550VS-G LDO3 created a fixed dependency cycle with the provider, which is why `vdd-l3-supply` must not be added. |
| — | Stock enables `panel_ldo_en` 11 ms before the DSI on commands; this port keeps it always-on until the hand-off is characterised. |

## Other

| Source | Recorded fact |
| --- | --- |
| — | The pmOS port dropped the QCA6490 AOP PDC votes after finding the xo-clk strobe alone starts the chip. That holds only when the boot chain hands the chip over already powered: after a cold handoff the PMU never completes power-up, PCIe never trains and the BT ROM never answers its version read. |
| — | A suspend test (`echo freeze`) left the tablet asleep with no way back, before `&pon_pwrkey` was enabled. |
| — | LPASS interconnect bring-up: `of_icc_get` for the upstream path never resolves on this tree, so the ADSP stayed in `-EPROBE_DEFER`; deleting `interconnects` lets PAS auth/boot proceed because `qcom_q6v5_init()` accepts a NULL path. Restore a real path once the LPASS icc graph is fixed. |
| — | The `v0.5 video` ended after the two preceding LPASS NOC providers probed and before `lpass_ag_noc` could return, which is why that provider is disabled. |
| — | Camera rotation: declaring `<90>` made libcamera report the wrong rotation and GNOME Camera's viewfinder rotate 90 degrees; the front viewfinder measured 0 upright, 180 upside down, 270 anticlockwise, so the value is applied clockwise as-is and stock's `sensor-position-roll` does not map onto it. |
| — | Front camera address: a full `0x08..0x77` sweep on the front bus with the sensor powered and MCLK4 running returned only `0x21` (model `0x1337`, vendor `0x2000`); `0x20` NAKs, and it is the module EEPROM in the stock tree. |

## Related documents

- `DISPLAY_OFFLINE_AUDIT.md` - the retired display patches and why they were retired.
- `DISPLAY_X710_OFFICIAL_V1.md` - the working revision-D display candidate.
- `GENI_TRANSFER_DIFF.md` - mainline vs stock GENI transfer behaviour.
- `MAINLINE_VS_STOCK_POGO.md` - the pogo protocol comparison.
- `POGO_STARTUP_REPAIR.md`, `POGO_EVENT_STARTUP.md`, `POGO_APP_PHASE_WRITES.md` - the pogo
  startup investigation in full.
- `USB_SERIAL_CONSOLE.md` - the verified console mapping.
