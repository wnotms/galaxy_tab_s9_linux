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
problem was that the modules were never built or installed (see §4). Per the
round's instruction, no meaningless Kconfig edit was made.

### The `wifi@0` node is the correct upstream idiom, not a bug

`&pcieport0 { wifi@0 { compatible = "pci17cb,1103"; ... -supply = ... } }` is
byte-for-byte the same pattern as upstream `qcs615-ride.dts` and
`qcs8300-ride.dts`. It is how upstream binds a **power-sequencing wrapper** to the
endpoint, and `ath11k_pci`'s Kconfig `select PCI_PWRCTRL_PWRSEQ if HAVE_PWRCTRL`
shows it is a required part of the ath11k PCI stack rather than an optional
flourish. `validate_device()` additionally requires `vddaon-supply`, which this
node declares.

## 3. Runtime evidence

Read-only probes, all archived: `reference/boot-tests/test-200-wifi-preflight/`
(transcript), `test-201-wifi-modules/`, `test-202-wifi-warm-reboot/`,
`test-203-wifi-cold-boot/`.

| question | answer |
|---|---|
| PCI enumeration | **one device: `0000:00:00.0` `17cb:0113`** — the SM8550 root complex, class `0x060400`, driver `pcieport` |
| `17cb:1103` (the WCN6855 endpoint) | **absent.** Has never appeared in any log in this project's history |
| link | `link_status=0x0142`, `DLLLA (bit13) = 0` — **down**; LTSSM stuck in `DETECT_QUIET`/`DETECT_ACT` |
| driver bind | `1c00000.pcie`→`qcom-pcie`, `1c06000.phy`→`qcom-qmp-pcie-phy`, `wcn6855-pmu`→`pwrseq-qcom_wcn`, `wifi@0`→`pci-pwrctrl-pwrseq` |
| `devices_deferred` | only `aux_bridge` — PCIe is no longer deferred |
| firmware request | **none** — `ath11k` has never been loaded |
| hw revision / board id | **unknown, and not guessed.** They are decided by what `ath11k` asks for once an endpoint exists |
| second witness | `hci0: Reading QCA version information failed (-110)` ×4 over UART14 — the chip is silent there too |

The driver's own words for the failure, now that it gets far enough to speak:

```
qcom-pcie 1c00000.pcie: Device not found
```

which `pcie-designware.c:788` emits only when the LTSSM is in
`DETECT_QUIET`/`DETECT_ACT` — no link partner was ever seen. This is not a
signal-integrity or training failure; the neighbouring branch would have printed
`Device found, but not active`.

## 4. Changes made

| change | why |
|---|---|
| `scripts/wifi-preflight.sh` | read-only probe; classifies the result into the plan's named states |
| `scripts/stage-wifi-modules.sh` | installs built modules into the running tablet, refusing unless release **and** vermagic match |
| `scripts/wifi-cold-boot-capture.sh` | snapshots the instant the tablet answers after a power-on, so a cold result is not a late reading |
| `scripts/screenshot-tablet.sh` | screen capture over the console link (no X11/Wayland on this port) |
| `build-kernel.sh`: `GTS9_DIAGNOSTIC_PATCHES`, image-replace guard | see below |
| `docs/WIFI_QCA6490_BRINGUP.md` | this document |

**No DTS change, no ath11k change, no Kconfig change, and nothing flashed for
Wi-Fi.** The board DTS, the `qcom,wlan-pdc-init` block and the PCIe nodes are
identical to upstream mainline's own `sm8550-samsung-gts9wifi.dts` apart from
comments, so there is nothing to correct on this evidence.

Two build-path defects were found and fixed while doing this, both recorded because
they are the kind that surface much later:

* **the modules had never been built.** The build whose `Image.gz` is flashed had no
  `modules-root` at all (`BUILD_MODULES=0`), so `CONFIG_ATH11K=m` and
  `CONFIG_PCI_PWRCTRL_PWRSEQ=m` were satisfied on paper only. Rebuilt: 167 modules,
  vermagic matching the flashed kernel, and `modules.alias` carries
  `alias of:N*T*Cpci17cb,1103 pci_pwrctrl_pwrseq`.
* **`build-kernel.sh` silently reverted a diagnostic patch.** It calls
  `prepare-kernel.sh`, which by design restores the pinned source and reapplies
  only the default queue — dropping `0021-gts9-rpmh-timeout-state-dump.patch`,
  which had been applied by hand. The result was a valid-looking `Image.gz` with no
  `gts9_rpmh_debug` switch, overwriting the artifact named as flashed. Now
  `GTS9_DIAGNOSTIC_PATCHES=<name>` applies it explicitly, and the build keeps an
  `Image.gz.flashed-*` copy rather than silently replacing a flashed image. The
  regenerated kernel is **byte-identical** to the one in the flashed boot image.

## 5. Firmware provenance

**None staged, none selected, none downloaded — and that is the correct state.**
`ath11k` has never been loaded because there is no PCI endpoint for it to bind to,
so it has never requested a firmware path. The `hw` revision and board id must come
from what it actually asks for at runtime; choosing them now would be guessing,
which the round forbids.

`scripts/stage-wifi-firmware.sh` does not exist yet on purpose: writing a tool whose
whole job is to place files at a path decided by the driver, before the driver has
said what that path is, would bake in exactly the assumption this round is meant to
avoid. It gets written when there is a real request to satisfy.

The rules are already fixed for when there is one: prefer upstream `linux-firmware`
if it carries a matching WCN6855 revision, otherwise extract Samsung's own
firmware/BDF from the legally-owned stock partitions, and record source, version,
filename and SHA-256 for each file. Never a guessed BDF, never an X910 board file,
never an internet `board-2.bin` as X710 calibration, and never an ath11k patch to
bypass board matching or force an unmatched calibration fallback.

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

**Both measured, and they are identical.** test-202 covers a warm reboot; test-203
covers a full `systemctl poweroff` followed by power-on. Neither reaches the
endpoint, and every field matches: modules autoload, controller and PHY bound,
`devices_deferred` down to `aux_bridge`, one PCI device (`17cb:0113`),
`link_status=0x0142` / `DLLLA=0`, `0000:01:00.0` absent, `WLAN_EN` high, `PERST`
released, all six PMU inputs enabled. The cold-handoff hypothesis — that the PMU
needs the PDC/AOP votes a cold start lacks — is **not supported**.

Scope, stated rather than assumed: the tablet was confirmed off (no ssh, no adb,
console silent) and restarted when VBUS was present, but the pmsg region still
named an older boot and `ramoops` lives in RAM that a true rail collapse would
clear. So this is the closest to a cold start achieved so far, not a
guaranteed-cold power cycle with the battery disconnected.

## 8. The fault is below both host interfaces

The strongest evidence in this round is not about PCIe at all. The pstore console
of the preceding boot shows `hci_qca` reading the chip's version over **UART14** —
a different bus — and getting no answer four times:

```
Bluetooth: hci0: command 0xfc00 tx timeout
Bluetooth: hci0: Reading QCA version information failed (-110)
```

So PCIe0 reports LTSSM `DETECT_QUIET` (no link partner) while the BT ROM also fails
to answer. **The WCN6855 is silent on both of its host interfaces.** That is one
fault, below both, and it rules out the link-training, controller, PHY, iATU and
pinctrl explanations individually — they cannot each be the cause of a UART
timeout.

Recorded as an observation about the shared chip, not as "Bluetooth caused it" or
"Wi-Fi caused it". BT shares the PMU and is running; the version-read failure is
evidence that the chip is unpowered or held, which is a statement about the chip.

## 9. Remaining problems

### 9.1 The endpoint does not come up, and the fault is on its side of a link the host finished setting up

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

### 9.2 The board DTS matches upstream mainline exactly — so this is not a DTS bug

`wcn6855_pmu`, `&pcie0`, `&pcieport0`/`wifi@0`, `&pcie0_phy`, `pcie0_default_state`
and `pmk8550_sleep_clk` were diffed against
`.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550-samsung-gts9wifi.dts` — the
tree **already carries an upstream gts9wifi DTS** — and they are identical apart
from comments. `wifi@0` is byte-identical. There is therefore no DTS change to make
on this evidence, and making one would be guessing.

### 9.3 Two properties in the DTS are inert on mainline

* **`qcom,wlan-pdc-init` and `qcom,qmp`** — a search of the entire pinned tree finds
  them **only in the DTS**; no driver reads either. They are kept, because the
  comment explains they are what a cold handoff needs and upstream's own comment
  says the same, but on mainline those AOP votes must come from the boot chain or
  not at all. Upstream's comment records the exact symptom seen here: *"the PMU
  never completes power-up without these votes: PCIe trains only after the bus scan,
  so ath11k never sees the endpoint"*.
* **`swctrl-gpios` (gpio82)** — consumed by no WLAN driver. Mainline's `hci_qca.c`
  reads a `swctrl` property, so this pin belongs to **Bluetooth**, not WLAN.

### 9.4 Bluetooth shares the PMU and is running

`hci0` exists and `hci_qca` powers the shared chip through the **same**
`pwrseq-qcom-wcn` device, via `devm_pwrseq_get(..., "bluetooth")` and
`pwrseq_power_on()`. Both targets share the `vregs` + `clk` + `xo-clk-assert`
dependencies and differ only in the final enable GPIO. This is a real confound for
attribution and is exactly why the round forbids bringing up BT at the same time;
it has not been disabled, and doing so is a candidate experiment, not a change made
here.

### 9.5 The stale-boot artifact is gone

test-200/201 ran on a boot that had probed PCIe eight times *before* the modules
existed. The reboot in §7 clears that: the current state is what a normal boot
produces.

### 9.6 Explicitly out of scope and untouched

* **Bluetooth** — not developed this round.
* **suspend/resume** — recorded only, no PM change.
* **The CPU wedge** — no stall record added, removed or reclassified; no rate
  computed; no Wi-Fi reboot counted in any A/B series. Nothing in these results
  claims anything about it.

## 9a. The missing step, identified in a Fedora port for this same board

Read-only analysis of `~/gts9wifi-fedora-linux` (a Fedora port for the **same
SM-X710**, seen at commit `ab123e7`) found
`kernel/patches/wcn7850-pwrseq-cold-reset-aop.patch`, whose comment describes this
board's failure:

> Samsung's cnss2 programs the AOP WLAN PDC resources through the QMP mailbox before
> the first WCN power-on. … without them **the WCN PMU never completes its power
> handshake and the PCIe receivers stay undetected.**

That is exactly what we measured — `Device not found`, LTSSM `DETECT_QUIET`. The
patch sets `cold_reset_wlan = true` for `wcn6855` (changing `wlan_gpio` from
`GPIOD_ASIS` to `GPIOD_OUT_LOW` with a settle delay) and adds
`pwrseq_qcom_wcn_program_wlan_pdc()`, which sends the `qcom,wlan-pdc-init` strings
through the AOP QMP mailbox.

Everything it needs is already here and working: the `qcom_aoss.h` API with
`qmp_send`, `CONFIG_QCOM_AOSS_QMP=y`, `c300000.power-management` **bound to
`qcom_aoss_qmp`**, and both `qcom,qmp` and the 11 `qcom,wlan-pdc-init` strings in
our DTS. Our WLAN DTS section is otherwise identical to that tree's, and the patch
**applies cleanly** to our pinned source. It is a downstream port patch, not
upstream — recorded as such — and it is **not yet verified on our hardware**.

This supersedes the "measure the rails" advice that used to sit in §10:
the missing step is observable in software after all.

## 10. Exact next physical test

The next test is chosen to discriminate between two hypotheses that the current
evidence cannot separate, and it needs no code change and no build:

Both hypotheses that this section used to list have been **tested and excluded**:
the cold-handoff/PDC one by test-203 (§7), and the "PMU internal LDOs are not being
enabled" one by inspection — those rails are the chip's own outputs, upstream's
accepted board file declares the same 37 references, and no mainline board
registers them, so a `vreg_pmu` count of 0 is normal upstream behaviour rather than
a defect.

What remains is a hardware-side question, and the next test is a measurement rather
than a code change: **measure the chip's rails directly.** Both host interfaces
being silent with `WLAN_EN` high and `PERST` released is consistent with the chip
having no power, being held in reset by something other than `PERST`, or having no
reference clock — and software cannot distinguish those three from the host side.

Concretely, on the next physical session:

1. probe the WCN6855's supply rails at the test points (or read them through the
   PMIC if the board exposes them) with the host asserting `WLAN_EN`, and confirm
   whether they are actually up;
2. check `XO` (gpio204) and the sleep-clock pin (`pmk8550` gpio3) at the chip, since
   the driver only *claims* to pulse them;
3. check whether any reset line other than `PERST` holds the chip.

Until a rail is measured, no DTS, ath11k or pwrseq change is justified — and in
particular **do not** add magic delays or retries to manufacture a `wlan0`.

If `17cb:1103` ever appears, move immediately to `modprobe ath11k_pci` and capture
the firmware paths **it** requests; that output, not this document, decides the
`hw` revision and board file.

