# test-202: warm reboot — the host is fully up and the endpoint is not there

Warm reboot with the modules already installed, so nothing was `modprobe`d by hand
and the stale-boot ordering of test-201 is gone. Raw capture: `WARM-REBOOT.txt`.

## The host side is now completely healthy

| item | measured |
|---|---|
| modules | **167 installed, autoloaded at boot** — `pci-pwrctrl-pwrseq`, `pwrseq-qcom-wcn` |
| `wifi@0` driver | `pci-pwrctrl-pwrseq`, bound **during boot** |
| `wcn6855-pmu` driver | `pwrseq-qcom_wcn` |
| `1c00000.pcie` | bound to `qcom-pcie` |
| `1c06000.phy` | bound to `qcom-qmp-pcie-phy` |
| `devices_deferred` | only `aux_bridge` — PCIe is **not** deferred any more |
| iATU | `unroll T, 8 ob, 8 ib, align 4K, limit 1024G` — configured |
| PCI host bridge | `PCI host bridge to bus 0000:00` |
| root port | `0000:00:00.0` `17cb:0113` class `0x060400`, PME + AER IRQ 205 |

## And the driver now says exactly what is wrong

This is the first boot where the PCIe driver got far enough to report a reason,
because before test-201 it never finished probing at all:

```
[    5.535313] qcom-pcie 1c00000.pcie: Device not found
```

That string comes from `drivers/pci/controller/dwc/pcie-designware.c:788`, and the
branch it sits in is precise:

```c
if (retries >= PCIE_LINK_WAIT_MAX_RETRIES) {
        /*
         * If the link is in Detect.Quiet or Detect.Active state, it
         * indicates that no device is detected.
         */
        ltssm = dw_pcie_get_ltssm(pci);
        if (ltssm == DW_PCIE_LTSSM_DETECT_QUIET ||
            ltssm == DW_PCIE_LTSSM_DETECT_ACT) {
                dev_info(pci->dev, "Device not found\n");
```

So the LTSSM is stuck in **Detect.Quiet / Detect.Active**. This is not a
signal-integrity failure and not a training failure: the controller never saw a
link partner *at all*. The neighbouring branch would have said `Device found, but
not active` if the endpoint had reached Poll.Active/Compliance. It did not.

`link_status = 0x0142`, `DLLLA (bit13) = 0`, `endpoint 0000:01:00.0 = NO`, and a
manual `rescan` changes nothing.

## What "no link partner" means, and the three remaining causes

LTSSM Detect means the WCN6855 is presenting nothing on the differential pair.
That leaves exactly three possibilities, and all three are on the endpoint side:

1. **The endpoint is not powered.** Its rail sequence is asserted (see below), but
   the `wifi@0` node's supplies may resolve to nothing, because **no mainline
   driver registers the `wcn6855-pmu` internal LDOs**: nine `vreg_pmu_*` rails are
   declared in the `regulators { }` child and referenced by `wifi@0`, yet
   `/sys/class/regulator` shows **zero** `vreg_pmu` entries. If `vddpcie0p9` /
   `vddpcie1p8` really come from those internal LDOs, nothing is enabling them.
2. **The endpoint is held in reset.** `PERST` is `gpio94`, declared
   `GPIO_ACTIVE_LOW`, measured **out high** (= released). So the pin is driven
   correctly by the host — but if the chip has no power it cannot sample it either.
3. **The endpoint has no reference clock.** `XO_CLK` (`gpio204`) was pulsed
   `1` then `0` by the driver's `post_enable` hook, which is the documented
   sequence; the PMU's own `clk` is optional and unset here, exactly as in
   upstream's working boards. So this is the least likely of the three, but it is
   not excluded.

## The power sequence did run — all of it

Measured live, not inferred:

| item | state |
|---|---|
| `WLAN_EN` `gpio80` | **out high** |
| `PERST` `gpio94` | **out high** (released) |
| `SWCTRL` `gpio82` | out high — note: this is a **Bluetooth** signal in mainline |
| `XO_CLK` `gpio204` | out low, after the 1→0 `post_enable` pulse |
| PMU inputs | `vreg_l15b_1p8`, `vreg_s2g_1p012`, `vreg_s5g_0p966`, `vreg_s4e_0p952`, `vreg_s4g_1p352`, `vreg_s6g_1p904` — **all enabled** |
| PMU internal rails | **0 registered** (`vreg_pmu_*` count = 0) |

So the host has applied power-enable, released reset, pulsed the clock, and
configured the PHY, the iATU and the pinmux — and the endpoint still shows nothing.
The one measured anomaly is the last row: the internal rails do not exist as
regulators at all.

## Cold/warm: warm measured, cold not

**Warm reboot: fails, as recorded above. Cold power-on: NOT TESTED.** They are not
merged. The DTS (and upstream's own gts9wifi DTS) records that after a cold handoff
the PMU may not complete power-up without the PDC/AOP votes, and that those votes
are **inert on mainline** — `qcom,wlan-pdc-init` and `qcom,qmp` appear only in the
DTS and no driver reads either. That makes a cold boot a specific, cheap, testable
hypothesis rather than a general worry.

## Bluetooth is running and shares the PMU

`hci0` exists, and `hci_qca` powers the same chip through the same
`pwrseq-qcom-wcn` device: it calls `devm_pwrseq_get(..., "bluetooth")` and then
`pwrseq_power_on()`, and both the `bluetooth` and `wlan` targets share the `vregs`,
`clk` and `xo-clk-assert` dependencies, differing only in the final enable GPIO.
This is a genuine confound for attribution and is why the round forbids bringing
BT up at the same time. It has **not** been disabled — doing so is a candidate
experiment, not a change made here.

## Explicitly not concluded

* Not "Wi-Fi works": no endpoint, no `ath11k_pci` bind, no firmware request, no
  interface. `ath11k` has still never been loaded, so there is no authoritative
  `hw` revision or board id and this round does not guess one.
* Not a DTS bug: `wcn6855_pmu`, `&pcie0`, `&pcieport0`/`wifi@0`, `&pcie0_phy`,
  `pcie0_default_state` and `pmk8550_sleep_clk` are identical to upstream mainline's
  own `sm8550-samsung-gts9wifi.dts`, apart from comments. `wifi@0` is byte-identical.
* Not an ath11k problem: it has not been reached.
* Nothing about the CPU wedge. No stall record was added, removed or reclassified,
  no rate was computed, and no Wi-Fi reboot was counted in any A/B series.
