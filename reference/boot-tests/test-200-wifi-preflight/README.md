# test-200: Wi-Fi preflight — the fork question, answered

Read-only probe at 2026-09-25T15:00Z, boot `037998b6`, no hardware state
changed. Transcript in `preflight.txt`, produced by `scripts/wifi-preflight.sh`.

## The question the round turns on

> Is the QCA6490 (`17cb:1103`) enumerated on PCIe by the running Debian?

**No. `STATE A` — there are no PCI devices at all.**

```
pci devices on the bus : 0
17cb:1103 present      : NO
/lib/modules/$(uname -r) : NONE
qcom-pcie deferred ('cannot initialize host') : YES
```

`/sys/bus/pci` exists and `CONFIG_PCI=y`, so the bus is there; nothing ever
enumerated on it. A `compatible = "pci17cb,1103"` string in the DTS is a binding
declaration, not enumeration — and this is exactly the distinction the probe
exists to keep honest.

## The root cause, found and confirmed in source

This is **not** an ath11k problem, and not a link-training problem. The PCIe host
never finishes probing because of a **missing module**, and the chain is complete
at every step:

1. `&pcieport0 { wifi@0 { compatible = "pci17cb,1103"; ... -supply = ... } }` is the
   correct upstream idiom — byte-for-byte the same pattern as upstream
   `qcs615-ride.dts` and `qcs8300-ride.dts`, so the DTS is not at fault.
2. `pci_pwrctrl_create_devices()` walks the controller's children and calls
   `pci_pwrctrl_is_required()`, which returns **true** for any child whose
   compatible starts with `"pci"` and that declares a `-supply`. Ours does.
3. So the kernel creates a platform device for it. Confirmed on the device:
   `/sys/bus/platform/devices/1c00000.pcie:pcie@0:wifi@0` with
   `modalias: of:NwifiT(null)Cpci17cb,1103`.
4. The driver that matches that modalias is `drivers/pci/pwrctrl/pci-pwrctrl-pwrseq.c`,
   whose OF table contains **`pci17cb,1103`** at line 117.
5. That driver is `CONFIG_PCI_PWRCTRL_PWRSEQ=m` — **a module**.
6. **`/lib/modules/$(uname -r)` does not exist on the tablet: zero modules are
   installed.** So the pwrctrl device never binds.
7. `pci_pwrctrl_power_on_device()` then hits, verbatim:
   ```c
   } else {
           /* FIXME: Use blocking wait instead of probe deferral */
           dev_dbg(&pdev->dev, "driver is not bound\n");
           ret = -EPROBE_DEFER;
   }
   ```
8. `qcom_pcie_host_init()` propagates it, `dw_pcie_host_init()` fails, and
   `dev_err_probe()` prints **nothing** for `-EPROBE_DEFER` — which is why dmesg
   shows the controller probing five times and then just stopping after
   `host bridge ... ranges:` with no error at all.
9. `/sys/kernel/debug/devices_deferred` names it plainly:
   ```
   1c00000.pcie    qcom-pcie: cannot initialize host
   ```

So the endpoint is never powered, PERST is never released, the link never trains,
and no config space is ever read.

## What is already correct, and must not be "fixed"

Everything else in the chain is present and bound, so this needs **no DTS change
and no ath11k change**:

| layer | state |
|---|---|
| PCIe controller `1c00000.pcie` | node `okay`, DTB complete (`phys`, `power-domains`, `interconnects`, `operating-points-v2`, `num-lanes`) |
| PCIe QMP PHY `1c06000.phy` | **bound** to `qcom-qmp-pcie-phy` |
| GDSCs `pcie_0_gdsc`, `pcie_0_phy_gdsc` | present in pm_genpd |
| `wcn6855-pmu` node | present at root, `compatible = "qcom,wcn6855-pmu"` — a **supported** id in `pwrseq-qcom-wcn.c` |
| `CONFIG_PWRSEQ` machinery | `POWER_SEQUENCING=y`, `POWER_SEQUENCING_QCOM_WCN=m`, `PCI_PWRCTRL=y`, `PCI_PWRCTRL_PWRSEQ=m` |
| ath11k | `ATH11K=m`, `ATH11K_PCI=m`, `MAC80211=m`, `CFG80211=m` all set |

The `qcom,wlan-pdc-init` AOP votes are untouched and must stay untouched.

## The one real defect: the modules were never installed

`out/kernel-gts9wifi/` — the build matching the flashed `Image.gz`
(`df00c53c…`) — contains **no `modules-root` at all**. The only module tree in the
tree is `out/kernel-poweroff-trace/modules-root/`, which belongs to a *different*
kernel build (`2cfe9793…`) from 09-23, while the flashed kernel was built 09-25.
And the tablet has `/lib/modules/` **empty**.

So at least these modules exist as config symbols but not as installable files:
`ath.ko`, `ath11k.ko`, `ath11k_pci.ko`, `cfg80211.ko`, `mac80211.ko`,
`pwrseq-qcom-wcn.ko`, `pci-pwrctrl-pwrseq.ko`, `qrtr-mhi.ko`.

That single fact explains every level-1 failure, and it is why the next step is a
**build with modules**, not a driver patch.

## Why this is not the CPU wedge

The `1c00000.pcie` re-probe at 0.33 / 0.88 / 1.43 / 1.47 / 5.37 / 15.59 s is a
deferred-probe retry loop, and the 15.59 s attempt lands right after the
`sync_state() pending due to 1c00000.pcie` burst. **Neither is evidence about the
wedge**: the wedge onset measured from the RCU timer is 7.13–7.74 s, and this
round does not add, remove or reclassify a single stall record. Per the round's
isolation rule, no stall rate is computed here and no Wi-Fi reboot is counted in
any A/B series.
