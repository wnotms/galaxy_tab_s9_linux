# test-204: a real chip power cycle, and a wrong register of my own

Two things this round: an experiment that forced the chip through an actual
power-off/power-on, and a correction to instrumentation I had already recorded.

## 1. The measurement I had wrong

test-202/203 read the PCIe Link Status register at a **hardcoded offset `0x72`**.
That is wrong. The PCI Express capability is not at a fixed address — the list has
to be walked from `0x34`:

```
cap@0x40 id=0x01 next=0x50     (Power Management)
cap@0x50 id=0x05 next=0x70     (MSI)
cap@0x70 id=0x10 next=0x00     (PCI Express)   <- Link Status is at 0x70+0x12 = 0x82
```

So the value I quoted (`0x0142` at `0x72`) was a different register entirely. The
**conclusion survives** — read correctly, `link_status = 0x1011` and
`DLLLA (bit13) = 0`, so the link really is down — but the cited evidence was wrong,
and a confident-looking number from the wrong register is worse than no number.
Both scripts now walk the capability list, and `wifi-preflight.sh` emits
`pcie_cap_offset` alongside the value so the offset is auditable. The bit labels are
also corrected: bit 11 is Link Training, bit 12 is Slot Clock Configuration, bit 13
is Data Link Layer Link Active.

Corrected reading on the wired-up host:

```
pcie_cap_offset=0x70
link_status=0x1011
  negotiated speed = 1 (2.5 GT/s Gen1, the floor)
  negotiated width = 1
  link_training_bit11 = 0     (training completed, i.e. it did run and settle)
  dllla_bit13 = 0             -> no data link
link_cap=0x007b6c23  max_speed=3  (8.0 GT/s capable)
endpoint_present=NO
```

## 2. The power-cycle experiment, and why it is informative

Upstream's own comment in `pwrseq-qcom-wcn.c` is the key:

> FIXME: This should actually be `GPIOD_OUT_LOW`, but doing so would cause the WLAN
> power to be toggled, resulting in PCIe link down.

So the driver acquires `wlan_gpio` with **`GPIOD_ASIS`** and then *preserves its
current value*. It never drives `WLAN_EN` low→high at probe. The chip is powered by
whatever the **boot chain** left, and on a mainline boot nothing in the kernel ever
turns it on from cold.

That makes a real power cycle the interesting experiment, and the pwrctrl
unbind/bind pair does exactly that, because the driver's `power_off`/`power_on`
callbacks are wired to the pwrseq target:

| step | `gpio80` (`WLAN_EN`) |
|---|---|
| before | `out high` |
| after `unbind wifi@0` | **`out low`** — the chip was genuinely de-powered |
| after `bind wifi@0` | `out low` — **unchanged** |

**The rebind did not re-power the chip.** That is not a bug in the driver: `probe`
only registers the pwrctrl and calls `devm_pci_pwrctrl_device_set_ready()`; the
`power_on` call lives in `qcom_pcie_host_init()`, which runs once when the PCIe host
is initialised, not on a pwrctrl rebind. So the sequence left the chip off, and a
`rescan` could not bring the link up because nothing had powered it.

**This is a candidate explanation for the whole symptom, and it is testable**: if
the boot chain hands the chip over unpowered, then `WLAN_EN` being *observed* high
means only that the driver preserved a line the bootloader drove — the chip's own
power state is not established by that alone.

The chip was returned to its correct state by rebooting (which re-runs
`qcom_pcie_host_init` → `power_on` → `WLAN_EN` high), verified after the reboot:
`gpio80: out high`, `pci_count=1`, and the same `Device not found`.

## 3. The sleep clock

`clk_summary` shows `sleep-clk` with **`prepare_count = 0`** but gate `Y` — the
clock is registered and ungated, and no driver has prepared it. Checked against the
binding rather than assumed: `Documentation/devicetree/bindings/regulator/qcom,qca6390-pmu.yaml`
lists `clocks` as **optional** and requires only the ten supplies for
`qcom,wcn6855-pmu`, and **no** upstream WCN PMU node — `sm8450-hdk`,
`glymur-crd`, `sm8550-qrd` — declares `clocks` at all. So `devm_clk_get_optional()`
returning NULL is normal upstream behaviour, and the reference clock arrives via the
`pmk8550_sleep_clk` pinctrl state instead. Not a defect, and no DTS change is
justified on it.

## 4. What is established now

| | state |
|---|---|
| host controller, PHY, iATU, pinctrl, GDSCs | **verified working** |
| `wifi@0` → `pci-pwrctrl-pwrseq`, `wcn6855-pmu` → `pwrseq-qcom_wcn` | **bound** |
| all six PMU input rails | **enabled** |
| `WLAN_EN` high, `PERST` released | **confirmed, and confirmed to be *preserved*, not driven** |
| link | **down**, `DLLLA=0`, LTSSM `DETECT_QUIET` |
| endpoint `17cb:1103` | **absent** |
| second witness | BT version read over UART14 fails `-110` ×4 — chip silent on both buses |

## 5. Next test, sharpened by §2

The question is no longer "is the DTS right" or "is the driver right" — both were
checked against upstream and match. It is: **what actually powers this chip on a
mainline boot?**

Concretely, in priority order:

1. **Measure the chip's supply rails** with `WLAN_EN` asserted. §2 shows the kernel
   never drives that line from low; if the boot chain leaves the rails down, the pin
   being high is irrelevant.
2. **Drive `WLAN_EN` low, wait, then high, and re-run the PCIe host init.** The
   pwrctrl unbind/bind pair proves the low half works; the missing half is getting
   `qcom_pcie_host_init` to run again afterwards, which needs the controller
   rebound (denied while in use — `Permission denied`) or a reboot with the line
   first forced low. If a genuine low→high transition makes the link train, the
   fault is the boot chain's handover, not this kernel's logic.
3. Only then consider whether the kernel should drive the line itself — and note
   upstream explicitly does **not**, for a documented reason.

No DTS, ath11k or pwrseq change is justified yet, and no magic delay, retry or
forced-calibration fallback will be added to manufacture a `wlan0`.

## 6. Isolation

No stall record was added, removed or reclassified; no rate was computed; no Wi-Fi
reboot was counted in any A/B series. The one reboot in this test was to restore the
chip's power state after the experiment, and it is not a stall observation.
