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

The driver's own output is the authority; nothing below is taken from a convention.

```
lspci -nn:  01:00.0 Network controller [0280]: Qualcomm QCNFA765 [17cb:1103] (rev 01)
            modalias pci:v000017CBd00001103sv000017CBsd00000108bc02sc80i00

ath11k_pci 0000:01:00.0: MSI vectors: 32
ath11k_pci 0000:01:00.0: wcn6855 hw2.1                       <- hardware revision
mhi mhi0: Power on setup success
mhi mhi0: Wait for device to enter SBL or Mission mode
ath11k_pci 0000:01:00.0: chip_id 0x12 chip_family 0xb board_id 0xff soc_id 0x400c1211
ath11k_pci 0000:01:00.0: fw_version 0x11021302 fw_build_timestamp 2026-02-04 08:10
ath11k_pci 0000:01:00.0: fw_build_id WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1
ath11k_pci 0000:01:00.0 wlp1s0: renamed from wlan0
```

| question | answer |
|---|---|
| PCI enumeration | **`0000:01:00.0` = `17cb:1103`**, class `0x028000`, revision `0x01`, subsystem `17cb:0108` |
| link | **up**: `link_status=0x3013`, `DLLLA(bit13)=1`, 8.0 GT/s x1, BAR0 assigned |
| root complex | `0000:00:00.0` = `17cb:0113` |
| driver bind | **`ath11k_pci`**; also `1c00000.pcie`→`qcom-pcie`, `1c06000.phy`→`qcom-qmp-pcie-phy`, `wcn6855-pmu`→`pwrseq-qcom_wcn`, `wifi@0`→`pci-pwrctrl-pwrseq` |
| **hardware revision** | **`hw2.1`**, reported by the driver |
| **firmware path** | `ath11k/WCN6855/hw2.1/amss.bin` + `m3.bin`, requested by the driver; matches `core.c` `.fw.dir` for `"wcn6855 hw2.1"` |
| **board id** | `board_id 0xff` from the chip; `board-2.bin` matched the device's exact-ABI slot automatically |
| interface | `phy0`, `wlp1s0`, MAC `00:03:7f:12:ce:0c`, rfkill clear |
| scan | **17 BSSes**, 2.4 GHz (2412/2437/2462) and 5 GHz (5300) |
| association | WPA2-PSK, `wpa_state=COMPLETED`, 802.11ax HE-MCS 3 HE-NSS 2 |

## 4. Changes made

| change | why |
|---|---|
| `0009-phy-qcom-qmp-pcie-select-phy-source-on-pipe-mux.patch` | **the root cause.** The GCC PIPE mux powered up on the XO reference and nothing switched it, so the MAC-PHY PIPE was dead and the LTSSM never performed receiver detection |
| `0008-power-sequencing-qcom-wcn-send-aop-wlan-pdc-votes.patch` | sends the `qcom,wlan-pdc-init` AOP votes through the QMP mailbox and cold-resets `WLAN_EN`; the DTS already had the strings and no driver read them |
| `scripts/wifi-preflight.sh` | read-only probe; classifies the state and reports control-pin ownership |
| `scripts/stage-wifi-modules.sh` | installs built modules into the running tablet, refusing unless release **and** vermagic match |
| `scripts/stage-wifi-firmware.sh` | fetches/stages the firmware to the path the **driver** asked for, hash-verifies every file, writes a manifest, never modifies its sources, installs with post-copy verification |
| `scripts/lib/bdftool.py` | parses/reports `board-2.bin`; ported from the Fedora tree with provenance |
| `scripts/wifi-cold-boot-capture.sh`, `scripts/screenshot-tablet.sh` | cold-boot snapshot; screen capture over the console link |
| `build-kernel.sh`: `GTS9_DIAGNOSTIC_PATCHES`, image-replace guard | a diagnostic patch was being silently reverted by `prepare-kernel.sh`, and a later build overwrote the artifact named as flashed |
| `docs/WIFI_QCA6490_BRINGUP.md` | this document |

**No ath11k source was modified, no Kconfig changed, no DTS changed, and no magic
delay, retry, hardcoded BAR, firmware-validation bypass or forced calibration
fallback was added.** `board-2.bin` matched this device's exact-ABI slot on its own.

## 5. Firmware provenance

Staged by `scripts/stage-wifi-firmware.sh` into
`out/wifi-firmware/ath11k/WCN6855/hw2.1/` (ignored by Git — these are proprietary
blobs) and installed to the tablet at `/usr/lib/firmware/ath11k/WCN6855/hw2.1/`.
The path is the one the **driver asked for**, taken from dmesg, not a convention.

| file | size | sha256 |
|---|---|---|
| `amss.bin` | 5079040 | `8cb5e63877c7cfdc5002a7d28bc5d7f7d20368183e6f93b12c977bfd0351c7b7` |
| `m3.bin` | 266684 | `d20460e104b85a7be9cdb5199c4d8b94a9787912e3f920acd845694d4d71f730` |
| `board-2.bin` | 7479440 | `3a92de58509ee13d417241a6b17be446fa3b0fa938c4cbd8492b1be25ae0f4a7` |

* `amss.bin`, `m3.bin` — from the CodeLinaro mirror of Qualcomm's
  `ath11k-firmware` tree,
  `WCN6855/hw2.0@nfa765/1.1/WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1`.
  The **IOE** family is chosen on evidence, not preference: the
  `gts9wifi-fedora-linux` port for this same tablet records that linux-firmware's
  WCN6855 amss "boots but the IOE build is the reliable family on this unit", that
  Samsung's own non-LITE `amss20` "crashes ath11k with `MHI_CB_EE_RDDM`", and that
  "the firmware family matters, not just the file name". Both hashes match that
  port's pinned values exactly. The chip now reports that same build id:
  `fw_build_id WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1`.
* `board-2.bin` — upstream `linux-firmware` at `main`. `bdftool.py` confirms this
  device's exact-ABI slot
  (`bus=pci,vendor=17cb,device=1103,subsystem-vendor=17cb,subsystem-device=0108,qmi-chip-id=18,qmi-board-id=255`)
  is present, so no substitution was needed and none was made.

**Upstream has no `ath11k/WCN6855/hw2.1/` at all** — `hw2.0` is the only revision
linux-firmware ships (`reference/boot-tests/test-207-wifi-firmware-search/`). The
directory name differs between Qualcomm's tree (`hw2.0@nfa765`) and the path the
kernel loads (`hw2.1`), which is why the staging tool writes to the driver's path.

**No Samsung stock partition was read and no blob was extracted from the device.**
The blobs were not committed to Git.

## 6. Current state

**Wi-Fi bring-up is complete: every level reached.** Boot `3cba35b7`, evidence in
`reference/boot-tests/test-210-wifi-network-works/`.

| level | state |
|---|---|
| `PCI_ONLY` — `17cb:1103` enumerated | **REACHED** (test-206) |
| `DRIVER_BOUND` — `ath11k_pci` bound | **REACHED** |
| `FIRMWARE_LOADED` — MHI + QMI + firmware | **REACHED** |
| `WLAN_INTERFACE` — `phy0`, `wlp1s0` | **REACHED** |
| `SCAN_WORKS` — 16 BSS, both bands | **REACHED** |
| `ASSOCIATION_WORKS` — on **5 GHz** | **REACHED** |
| `NETWORK_STABLE` — DHCP lease + default route | **REACHED** |
| traffic — ping, DNS, HTTP download | **REACHED** |

```
ath11k_pci 0000:01:00.0: wcn6855 hw2.1
fw_build_id WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1

bssid=da:4d:3d:c0:32:d5  freq=5180  ssid=OnePlus 15
key_mgmt=WPA2-PSK  wpa_state=COMPLETED  signal -80 dBm
tx bitrate: 288.2 MBit/s 80MHz HE-MCS 3 HE-NSS 2

DHCP: 10.221.200.69/24 via 10.221.200.10
ping 223.5.5.5        0% loss, 53.9 ms
getent hosts one.one.one.one  ->  resolves
HTTP 200, 138612 bytes at 692 KB/s
```

**5 GHz carries real traffic at 288 Mbit/s with 80 MHz and 2 spatial streams**, with
the **unmodified upstream `board-2.bin`** — no BDF substitution. That answers the
open question from test-208 about the documented weak-5-GHz payload: it is not a
problem on this unit as configured.

**HTTPS fails certificate verification** (`unable to get local issuer certificate`)
while HTTP transfers at ~690 KB/s. That is a CA/trust issue on the Debian rootfs, not
wireless, and is recorded so it is not mistaken for one.

Three faults had to be fixed to get here, each diagnosed from a measurement rather
than a guess: the **missing modules** (`BUILD_MODULES=0`, so every `=m` symbol was
satisfied on paper only), the **AOP PDC votes** (`0008`), and above all the **parked
PCIe0 PIPE source mux** (`0009`).

## 7. Cold/warm boot result

**Measured before Wi-Fi worked, and not yet re-measured after.** Both a warm reboot
(test-202) and a full `systemctl poweroff` then power-on (test-203) failed
identically at the time: same one PCI device, `link_status` with `DLLLA=0`,
`17cb:1103` absent, the same `Device not found`. That is what motivated sending the
AOP PDC votes, since the DTS records they are what a cold handoff needs.

Those runs predate the PIPE-mux fix, so they no longer describe the current
configuration. **The cold-boot path with Wi-Fi working is untested** and is the first
item in §10. Warm boot after `modprobe` is what produced every result in §3 and §6.

Scope of what "cold" meant, stated because it was never a true rail collapse: the
tablet was confirmed off (no ssh, no adb, console silent), but it restarted when VBUS
was present and the `ramoops` region was still populated, which a genuine power cycle
would clear.

## 8. Superseded: "the fault is below both host interfaces"

This section previously argued that because the BT version read over UART also
failed, the fault sat below both host interfaces. That reasoning was **withdrawn**:
`BT_EN` was low at the time, so the chip was not enabled on that path and its
silence there was expected — the two observations were consistent but not
independent.

The actual fault was the parked PIPE mux (§6), which is PCIe-specific. Recorded here
because the earlier claim is in the git history and should not be read as standing.

## 9. Remaining problems

### 9.1 HTTPS certificate verification

`curl: (60) SSL certificate problem: unable to get local issuer certificate`, while
`/etc/ssl/certs/ca-certificates.crt` exists and plain HTTP works at ~690 KB/s. A
rootfs CA/trust issue, not a wireless one; it reproduces over any link.

### 9.2 The boot console block, and the shutdown delay

Two separate console-path defects were found while bringing Wi-Fi up, both recorded
in full in `docs/BOOT_CONSOLE_BLOCK.md`: a userspace `write()` to `/dev/console`
(which resolves to `ttyGS1`/COM19) blocks when no host process is draining the port,
which can make the boot look hung until the port is opened; and
`gts9-acm-getty.service` held shutdown for 90 s on an unreaped login shell.

The second is fixed (`TimeoutStopSec=3`). For the first, one contributing writer was
removed (`gts9-prev-boot-evidence.service` no longer uses `journal+console`), but the
underlying policy question — keep `console=ttyGS1` for the kernel log from 5.6 s, or
drop it so `gts9-kmsg-console` mirrors `/dev/kmsg` from userspace where it cannot
wedge PID 1 — is a real trade-off and is left as a decision, not made unilaterally.

### 9.3 The 5 GHz question is closed, the long-transfer one is not

5 GHz associates and transfers at 288 Mbit/s (§6), so the documented BDF weakness
does not apply here. A 10-30 minute sustained-transfer soak has **not** been run, so
`NETWORK_STABLE` is claimed on the strength of a working lease, bidirectional traffic
and a clean download rather than on a soak.

### 9.4 Things deliberately not touched

* **Bluetooth** — out of scope, per the brief. `BT_EN` was observed low while
  `hci_qca` retried, which is the first thing to look at when BT is tackled.
* **suspend/resume** — recorded only; no PM change made.
* **The CPU wedge** — no stall record added, removed or reclassified, no rate
  computed, and no Wi-Fi reboot counted in any A/B series.

## 9a. How the fix was found

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

Wi-Fi itself needs nothing further to be *working*; what follows is hardening, in
priority order.

1. **A sustained transfer soak** — 10-30 minutes over the associated 5 GHz link, to
   turn `NETWORK_STABLE` from "working" into "measured". `iperf3` if a peer is
   available, otherwise a long HTTP fetch with byte accounting.
2. **Decide the `console=ttyGS1` policy** (§9.2). This is the one open design
   question the bring-up surfaced, and it affects every future boot measurement in
   this repo, not just Wi-Fi.
3. **A cold boot with the current configuration**, to confirm `0008` and `0009`
   together hold from a full power cycle now that firmware and interface autoload is
   proven (test-209 did this before the network levels were reached).
4. **Then Bluetooth**, in its own round, as the brief requires — with `BT_EN` first.

None of it requires an ath11k change, and none should be made unless a measurement
demands it.
