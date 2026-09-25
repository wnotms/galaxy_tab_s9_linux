# test-201: staging the modules unblocks PCIe — root complex enumerates

2026-09-25T15:09Z, boot `037998b6` (the same boot as test-200; nothing was
rebooted). Evidence in `RESULT.txt` and `dmesg.txt`.

## What was done

`scripts/stage-wifi-modules.sh --apply` installed the 167 modules from
`out/kernel-gts9wifi/modules-root/` into the tablet's
`/lib/modules/7.2.0-rc3-gts9wifi-dirty/` and ran `depmod -a`. No flash, no reboot.

Then the two modules the diagnosis named:

```
modprobe pwrseq-qcom-wcn      # the PMU sequencer (provider)
modprobe pci-pwrctrl-pwrseq   # the wrapper that matches pci17cb,1103 (consumer)
```

## Result: the diagnosis was right and the blocker is gone

| | before (test-200) | after |
|---|---|---|
| `wcn6855-pmu` driver | **unbound** | `pwrseq-qcom_wcn` |
| `1c00000.pcie:pcie@0:wifi@0` driver | **unbound** | `pci-pwrctrl-pwrseq` |
| `devices_deferred` | `1c00000.pcie  qcom-pcie: cannot initialize host` | **gone** (only `aux_bridge` remains) |
| PCI devices | **0** | **1** |
| PCIe host probe | fails, retried 5×, no error logged | **succeeds** |

The power chain is wired end to end, confirmed from sysfs:

```
pwrseq consumer = platform:1c00000.pcie:pcie@0:wifi@0
pwrseq supplier = platform:17a00000.rsc:regulators-0      (the WCN PMU)
```

So the `-EPROBE_DEFER` in `pci_pwrctrl_power_on_device()` was exactly the cause, and
a **missing module** was exactly the reason. No DTS change, no ath11k change, no
Kconfig change.

## But LEVEL 1 is only partly reached — this is a root complex, not the endpoint

```
0000:00:00.0  17cb:0113  class 0x060400  driver=pcieport
  link: 2.5 GT/s x1, secondary bus 01, subordinate 255
  windows: io 0x1000-0x1fff, mem 0x60300000-0x604fffff,
           pref 0x60500000-0x606fffff, BAR0 0x60700000-0x60700fff
  PME IRQ 205, AER enabled
```

`17cb:0113` is the **SM8550 PCIe Root Complex** (its own device id), not the
WCN6855. It is the right *kind* of progress — before this, `lspci` was empty — but
it is the host bridge, and **no device appeared on bus 01**. A manual
`echo 1 > /sys/bus/pci/rescan` added nothing.

## What that means

The link between the root complex and the endpoint did not come up far enough for
the endpoint's config space to be read. The prime suspect is now the **endpoint
power-on**: the pwrctrl wrapper bound, but there is no evidence yet that the WCN
PMU was actually told to raise `WLAN_EN` and release `PERST` — and the driver has
been logging `supply vdda not found, using dummy regulator` and
`vddpe-3v3 not found` since the very first probe.

Also worth noting for the next attempt: `x1` at `2.5 GT/s` is the *floor* of PCIe
Gen1. A WCN6855 link that has trained but not negotiated upward, with no config
space readable, is consistent with the device being held in reset or never
powered rather than with a signal-integrity problem.

## Explicitly not concluded

* **Not** "Wi-Fi works" — there is no endpoint, no driver bind, no firmware, no
  interface.
* **Not** a DTS problem, and **not** an ath11k problem: ath11k has not been
  reached even once, so it has asked for no firmware and this round still has no
  authoritative `hw revision` or board id.
* **Not** related to the CPU wedge. Nothing was added to or removed from the stall
  record, no rate was computed, and this reboot did not happen — the same
  `037998b6` boot was used throughout, so no Wi-Fi reboot entered any A/B series.

## Files

| file | what it is |
|---|---|
| `RESULT.txt` | the state table before and after, and the full PCI result |
| `dmesg.txt` | the kernel log for the enumeration, captured after loading the modules |
