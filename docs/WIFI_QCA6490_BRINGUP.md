# QCA6490 / WCN6855 Wi-Fi bring-up on the X710

State: **PCI_ONLY not yet reached — the PCIe host does not finish probing.** See
§6. Nothing has been flashed for Wi-Fi; no ath11k or DTS change has been made.

This document is the record of what the hardware is, what the tree already
supports, what the running system actually reports, and what is missing. It is
deliberately ordered so that "compiles", "boots", "enumerates" and "verified on
hardware" stay separate claims.

## 1. Hardware identity

| item | value | how it is known |
|---|---|---|
| device | Samsung Galaxy Tab S9 Wi-Fi, SM-X710, `gts9wifi` | board name in the DTB |
| SoC | Qualcomm SM8550 (`kalama`) | `compatible` |
| WLAN/BT combo | **QCA6490 / WCN6855-class** | stock X710 downstream device tree |
| **not** | WCN7850 / Kiwi v2 / ath12k — that is the **X910** and must not be copied | `AGENT.md`, `reference/stock/MANIFEST.md` |
| PCI identity | **`17cb:1103`** (vendor Qualcomm, device WCN6855) | `pci17cb,1103` in the DTS; upstream `pci-pwrctrl-pwrseq.c` labels it *"ATH11K in WCN6855 package"* |
| driver | `ath11k_pci` → `ath11k` → MHI → `cfg80211`/`mac80211` | upstream |
| bus | PCIe0 `1c00000.pcie`, PHY `1c06000.phy` | upstream `sm8550.dtsi` |
| control GPIOs | 80 `WLAN_EN`, 81 `BT_EN`, 82 `SWCTRL`, 94 `PERST`, 96 `WAKE`, 204 `XO` | stock X710 downstream tree, carried in the board DTS |
| PMU | `qcom,wcn6855-pmu` with `qcom,wlan-pdc-init` AOP votes | stock X710 `cnss` evidence |

## 2. Existing support in this tree (verified, not assumed)

All of the following were checked against the **resolved** config
`out/kernel-gts9wifi/config` and the pinned source, not against the fragment:

| layer | symbol | state |
|---|---|---|
| PCI core | `CONFIG_PCI` | `=y` |
| PCIe controller | `CONFIG_PCIE_QCOM` | `=y` |
| PCIe PHY | `CONFIG_PHY_QCOM_QMP_PCIE` | `=y` |
| PCI power control | `CONFIG_PCI_PWRCTRL` / `HAVE_PWRCTRL` | `=y` |
| PCI pwrctrl via pwrseq | `CONFIG_PCI_PWRCTRL_PWRSEQ` | **`=m`** |
| WCN power sequencing | `CONFIG_POWER_SEQUENCING_QCOM_WCN` | **`=m`** |
| WLAN core | `CONFIG_WLAN`, `CONFIG_WLAN_VENDOR_ATH` | `=y` |
| cfg80211 / mac80211 | `CONFIG_CFG80211`, `CONFIG_MAC80211` | `=m` |
| ath11k | `CONFIG_ATH_COMMON`, `CONFIG_ATH11K`, `CONFIG_ATH11K_PCI` | `=m` |
| MHI | `CONFIG_MHI_BUS` | `=y` (built in — no `mhi.ko` is expected or needed) |
| QRTR | `CONFIG_QRTR`, `CONFIG_QRTR_MHI` | `=y`, `=m` |

Device tree, confirmed in the **flashed** DTB (`sm8550-samsung-gts9wifi.dtb`,
`b3e068e7…`), not merely in the source: `wcn6855-pmu` present at root with
`compatible = "qcom,wcn6855-pmu"`, nine `vreg_pmu_*` rails, and
`1c00000.pcie` `okay` with `phys`, `power-domains`, `interconnects`,
`operating-points-v2` and `num-lanes` all resolved.

**No Kconfig change was needed.** Every symbol above was already correct; the
problem was that the modules were never built or installed (see §7). Per the
round's instruction, no meaningless Kconfig edit was made.

### The `wifi@0` node is the correct upstream idiom, not a bug

`&pcieport0 { wifi@0 { compatible = "pci17cb,1103"; ... -supply = ... } }` is
byte-for-byte the same pattern as upstream `qcs615-ride.dts` and
`qcs8300-ride.dts`. It is how upstream binds a **power-sequencing wrapper** to the
endpoint, and `ath11k_pci`'s Kconfig `select PCI_PWRCTRL_PWRSEQ if HAVE_PWRCTRL`
shows it is a required part of the ath11k PCI stack rather than an optional
flourish. `validate_device()` additionally requires `vddaon-supply`, which this
node declares.

## 3. Runtime evidence (test-200, boot `037998b6`)

From `scripts/wifi-preflight.sh`, transcript in
`reference/boot-tests/test-200-wifi-preflight/preflight.txt`:

```
pci devices on the bus : 0
17cb:1103 present      : NO
17cb:1103 bound driver : n/a
cfg80211/mac80211/ath11k loaded : 0
ieee80211 phy devices  : 0
/lib/modules/$(uname -r) : NONE
qcom-pcie deferred ('cannot initialize host') : YES
STATE: A  no PCI devices at all
```

* **PCI enumeration: none.** `/sys/bus/pci` exists and `CONFIG_PCI=y`, so the bus
  is present and empty. No config space has ever been read.
* **driver bind: none** — for the same reason.
* **firmware request: none.** ath11k was never reached, so nothing has been asked
  for. There is therefore no authoritative `hw revision` or `board id` yet, and
  this document does **not** guess `hw2.0`/`hw2.1`/`board-2.bin`.
* `/sys/kernel/debug/devices_deferred`:
  ```
  1c00000.pcie   qcom-pcie: cannot initialize host
  ```
* PHY: `1c06000.phy` **bound** to `qcom-qmp-pcie-phy`. GDSCs `pcie_0_gdsc` and
  `pcie_0_phy_gdsc` present.
* The WCN PMU platform device exists (`/sys/bus/platform/devices/wcn6855-pmu`) but
  is **unbound**, because its driver is also a module.

## 4. Changes made

* **`scripts/wifi-preflight.sh`** — new, read-only. It cannot modify hardware
  state: no modprobe, no bind/unbind, no GPIO or regulator writes, no firmware
  writes. Committed as `wifi: add read-only QCA6490 bring-up probe`.
* **Nothing else.** No DTS change, no ath11k change, no Kconfig change, and no
  flash. The board DTS, the `qcom,wlan-pdc-init` AOP votes and the PCIe node are
  correct as they stand and were left untouched, as the round required.

## 5. Firmware provenance

**None yet, and that is the honest state.** No firmware has been staged, selected
or downloaded. The path, the hardware revision and the board id must come from
what `ath11k` actually requests at runtime once the PCIe host probes; deciding
them now would be guessing, which the round forbids.

When it is time, the rules are already fixed: prefer upstream `linux-firmware` if
it carries a matching WCN6855 revision, otherwise extract Samsung's own
firmware/BDF from the legally-owned stock partitions, and record source, version,
filename and SHA-256 for every file. Never a guessed BDF, never an X910 board
file, never an internet `board-2.bin` as X710 calibration, and never an ath11k
patch to bypass board matching.

## 6. Current state

| level | state |
|---|---|
| `PCI_ONLY` — `17cb:1103` visible in `lspci` | **NOT REACHED** |
| `DRIVER_BOUND` — `ath11k_pci` bound | not reached |
| `FIRMWARE_LOADED` — MHI/QMI/firmware up | not reached |
| `WLAN_INTERFACE` — `wlan0` in `ip link` | not reached |
| `SCAN_WORKS` | not reached |
| `ASSOCIATION_WORKS` | not reached |
| `NETWORK_STABLE` | not reached |

What *was* reached is not on that scale and must not be confused with it: the PCIe
**host** now probes successfully and a root complex enumerates. That is a
prerequisite for LEVEL 1, not LEVEL 1.

## 7. Cold/warm boot result

**Warm reboot measured; cold boot not yet measured.** The two are never merged.

| | warm reboot, modules installed |
|---|---|
| modules autoloaded at boot | **yes** (`pci-pwrctrl-pwrseq`, `pwrseq-qcom-wcn`) |
| `wifi@0` bound during boot, no manual modprobe | **yes** |
| `devices_deferred` | only `aux_bridge` |
| PCI devices | 1 — `0000:00:00.0` `17cb:0113` (root complex) |
| `17cb:1103` | **absent** |
| Link Status `DLLLA` (bit 13) | **0 — link down**, unchanged by `rescan` |

Reading config space of `01:00.0` fails outright (`No devices selected`). So the
warm path reaches "host ready, link down", and a cold power-on has **not** been
tested. Per the round's rule, the warm result is not evidence about cold.

## 8. Remaining problems

### 8.1 The endpoint does not come up, and the fault is on its side of a link the host finished setting up

Everything the host owns has been verified working, live:

| item | measured |
|---|---|
| PCIe controller `1c00000.pcie` | probed successfully, bound, no longer deferred |
| PHY `1c06000.phy` | bound to `qcom-qmp-pcie-phy` |
| GDSCs | `pcie_0_gdsc`, `pcie_0_phy_gdsc` present |
| pinmux | `gpio94` out high (PERST released), `gpio95` func1 (`pcie0_clk_req_n`), `gpio96` in high (WAKE) |
| root port | `17cb:0113`, class `0x060400`, windows + BAR0 assigned, PME/AER IRQ 205 |

And the endpoint power sequence ran:

| item | measured |
|---|---|
| `wifi@0` driver | `pci-pwrctrl-pwrseq` |
| `wcn6855-pmu` driver | `pwrseq-qcom_wcn` |
| `WLAN_EN` `gpio80` | **out high** |
| `PERST` `gpio94` | **out high** (active-low, so out of reset) |
| `XO_CLK` `gpio204` | out low, i.e. deasserted *after* enable — matches the driver's `post_enable` hook |
| PMU input rails | `vreg_s2g_1p012`, `vreg_s5g_0p966`, `vreg_s4e_0p952`, `vreg_s4g_1p352`, `vreg_s6g_1p904` all **enabled** |
| pwrseq wiring | consumer `platform:1c00000.pcie:pcie@0:wifi@0`, supplier `platform:17a00000.rsc:regulators-0` |

So power, reset, clock and pinmux are all applied and the link is still down. The
remaining fault is in the endpoint/PMU interaction, not in the host controller.

### 8.2 The board DTS matches upstream mainline exactly — so this is not a DTS bug

`wcn6855_pmu`, `&pcie0`, `&pcieport0`/`wifi@0`, `&pcie0_phy`, `pcie0_default_state`
and `pmk8550_sleep_clk` were diffed against
`.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550-samsung-gts9wifi.dts` — the
tree **already carries an upstream gts9wifi DTS** — and they are identical apart
from comments. `wifi@0` is byte-identical. There is therefore no DTS change to make
on this evidence, and making one would be guessing.

### 8.3 Two properties in the DTS are inert on mainline

* **`qcom,wlan-pdc-init` and `qcom,qmp`** — a search of the entire pinned tree finds
  them **only in the DTS**; no driver reads either. They are kept, because the
  comment explains they are what a cold handoff needs and upstream's own comment
  says the same, but on mainline those AOP votes must come from the boot chain or
  not at all. Upstream's comment records the exact symptom seen here: *"the PMU
  never completes power-up without these votes: PCIe trains only after the bus scan,
  so ath11k never sees the endpoint"*.
* **`swctrl-gpios` (gpio82)** — consumed by no WLAN driver. Mainline's `hci_qca.c`
  reads a `swctrl` property, so this pin belongs to **Bluetooth**, not WLAN.

### 8.4 Bluetooth shares the PMU and is running

`hci0` exists and `hci_qca` powers the shared chip through the **same**
`pwrseq-qcom-wcn` device, via `devm_pwrseq_get(..., "bluetooth")` and
`pwrseq_power_on()`. Both targets share the `vregs` + `clk` + `xo-clk-assert`
dependencies and differ only in the final enable GPIO. This is a real confound for
attribution and is exactly why the round forbids bringing up BT at the same time;
it has not been disabled, and doing so is a candidate experiment, not a change made
here.

### 8.5 The stale-boot artifact is gone

test-200/201 ran on a boot that had probed PCIe eight times *before* the modules
existed. The reboot in §7 clears that: the current state is what a normal boot
produces.

### 8.6 Explicitly out of scope and untouched

* **Bluetooth** — not developed this round.
* **suspend/resume** — recorded only, no PM change.
* **The CPU wedge** — no stall record added, removed or reclassified; no rate
  computed; no Wi-Fi reboot counted in any A/B series. Nothing in these results
  claims anything about it.

## 9. Exact next physical test

The next test is chosen to discriminate between two hypotheses that the current
evidence cannot separate, and it needs no code change and no build:

1. **Cold power-on versus warm reboot.** The DTS comment (and upstream's) says a
   cold handoff is where the PMU fails to complete power-up when the PDC/AOP votes
   are absent — and mainline implements no such votes (§8.3). Warm boot is now
   measured and fails; a **full poweroff then power-on** is the untested half. Do
   not merge the two results.
2. **Whether the endpoint needs the PMU's *internal* LDOs.** The nine
   `vreg_pmu_*` rails are declared in the `regulators { }` child of `wcn6855-pmu`
   and referenced by `wifi@0` and the BT node — but **no mainline driver registers
   them**, so they appear as zero entries in `/sys/class/regulator`. If the
   endpoint's `vddpcie0p9`/`vddpcie1p8` really come from those internal LDOs, they
   are not being enabled. This is the strongest remaining structural hypothesis.

Order: power off fully, power on, and immediately run
`scripts/wifi-preflight.sh --save reference/boot-tests/test-<N>-wifi-cold/`. Read
the same table as §8.1. Then, if the link is still down, test hypothesis 2 by
checking whether the internal rails can be modelled as `regulator-fixed` from
always-on parents — that is a DTS change and needs its own authorization, and it
must be justified by evidence rather than tried as a guess.

If `17cb:1103` ever appears, move immediately to `modprobe ath11k_pci` and capture
the firmware paths **it** requests; that output, not this document, decides the
`hw` revision and board file.

