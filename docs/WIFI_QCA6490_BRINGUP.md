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

**`PCI_ONLY` is not yet reached.** The scale below is the only one that counts as
progress; "module loaded" is not on it.

| level | state |
|---|---|
| `PCI_ONLY` — `17cb:1103` visible in `lspci` | **NOT REACHED** |
| `DRIVER_BOUND` — `ath11k_pci` bound | not reached |
| `FIRMWARE_LOADED` — MHI/QMI/firmware up | not reached |
| `WLAN_INTERFACE` — `wlan0` in `ip link` | not reached |
| `SCAN_WORKS` | not reached |
| `ASSOCIATION_WORKS` | not reached |
| `NETWORK_STABLE` | not reached |

## 7. Remaining problems

### 7.1 No kernel modules are installed on the tablet — the blocking defect

This is the single cause of the `STATE A` result, and it is a build/packaging
defect rather than a driver or device-tree problem.

* `/lib/modules/$(uname -r)` does not exist on the tablet. **Zero** `.ko` files.
* `out/kernel-gts9wifi/` — the build whose `Image.gz` (`df00c53c…`) is the flashed
  one — had **no `modules-root` at all**: the last build ran with
  `BUILD_MODULES=0`.
* The only module tree in the repository belonged to
  `out/kernel-poweroff-trace/`, a *different* kernel (`2cfe9793…`) built two days
  earlier. It could not have been used even if someone had tried.
* So `CONFIG_ATH11K=m`, `CONFIG_PCI_PWRCTRL_PWRSEQ=m` and
  `CONFIG_POWER_SEQUENCING_QCOM_WCN=m` were satisfied **on paper only**: the
  symbols resolve, the `.ko` files did not exist anywhere.

Rebuilt with `USE_CCACHE=1 ARCH=arm64 LLVM=1 BUILD_MODULES=1 ./scripts/build-kernel.sh`.
167 modules now exist under `out/kernel-gts9wifi/modules-root/`, including
`ath11k_pci.ko`, `pci-pwrctrl-pwrseq.ko`, `pwrseq-qcom-wcn.ko`, `cfg80211.ko`,
`mac80211.ko`, `ath.ko` and `qrtr-mhi.ko`. Their vermagic is
`7.2.0-rc3-gts9wifi-dirty SMP preempt mod_unload modversions aarch64`, matching
the flashed kernel exactly, and `modules.alias` contains

```
alias of:N*T*Cpci17cb,1103 pci_pwrctrl_pwrseq
```

which is precisely the modalias the tablet reports for the unbound device
(`of:NwifiT(null)Cpci17cb,1103`).

**No new kernel image is needed.** The DTB is byte-identical to the flashed one
(`b3e068e7…`). The freshly built `Image.gz` differs only by the build timestamp,
and must **not** be flashed: staging the modules into the existing kernel is the
whole fix.

### 7.2 The exact deferral, for the record

Because it is easy to mistake for a link-training failure, the chain is:

1. `pci_pwrctrl_is_required()` accepts any child whose compatible starts with
   `"pci"` and which declares a `-supply`, so `wifi@0` becomes a platform device.
2. The driver for it is `pci-pwrctrl-pwrseq`, matched on `pci17cb,1103`.
3. `pci_pwrctrl_power_on_device()`:
   ```c
   } else {
           /* FIXME: Use blocking wait instead of probe deferral */
           ret = -EPROBE_DEFER;
   }
   ```
4. `qcom_pcie_host_init()` propagates, `dw_pcie_host_init()` fails, and
   `dev_err_probe()` prints nothing for `-EPROBE_DEFER`.

Hence dmesg shows the controller starting five times and stopping after
`host bridge ... ranges:` with no error, and the device lands in
`devices_deferred` instead. It is a **missing module**, not a broken link.

### 7.3 What must still be verified after the modules load

Cold-boot versus warm-boot bring-up. The board DTS records that after a cold
handoff the QCA6490 PMU may not complete power-up without correct PDC/AOP votes,
and those votes are present but have never been exercised on this port. A warm
boot succeeding will not be reported as "cold boot fixed"; both will be measured
separately.

### 7.4 Explicitly out of scope this round

* **Bluetooth.** `uart14` / `qcom,wcn6855-bt` shares the PMU with WLAN, so
  bringing up `hci_qca` at the same time would make a PMU or shared-rail fault
  impossible to attribute. Wi-Fi first, BT in its own round.
* **suspend/resume.** Recorded only; no PM change is being made for it.
* **The CPU wedge.** Untouched. No stall record was added, removed or
  reclassified, no stall rate is computed here, and no Wi-Fi reboot is counted in
  any A/B series. If a wedge appears during Wi-Fi work it is filed as
  `wifi-bringup incidental wedge` with its evidence preserved, and the co-occurrence
  of a PCIe probe or a firmware load is **not** treated as causation — the baseline
  wedges on its own, so only a single-variable A/B could speak to it, and this
  round does not run one.

## 8. Exact next physical test

**Stage the modules into the running Debian and re-probe. No flash, no reboot
required to start.**

1. Install `out/kernel-gts9wifi/modules-root/lib/modules/7.2.0-rc3-gts9wifi-dirty/`
   to `/lib/modules/7.2.0-rc3-gts9wifi-dirty/` on the tablet, then `depmod -a`.
2. `modprobe pci-pwrctrl-pwrseq` (the specific missing link), then
   `modprobe pwrseq-qcom-wcn`, then re-read
   `/sys/bus/pci/devices/` and `lspci -nn`.
3. If `17cb:1103` appears: `modprobe ath11k_pci`, then capture `dmesg -T` and the
   firmware paths it actually requests — that output, not this document, is what
   decides `hw` revision and board file.
4. If it does not appear, read `devices_deferred` and the PHY/GDSC state before
   touching anything else, and treat it as a power-sequencing problem (§5 of the
   round plan), not an ath11k problem.

The expected outcome is that the pwrctrl device binds, PCIe finishes probing, and
the endpoint enumerates — reaching `PCI_ONLY`. Whether the endpoint then needs
`vddpe-3v3`/`vdda` supplies that this board does not declare is the first thing to
watch: the driver currently logs `supply vdda not found, using dummy regulator`
and `vddpe-3v3 not found`, and a dummy regulator is adequate for enumeration but
would not be for a real power-on.
