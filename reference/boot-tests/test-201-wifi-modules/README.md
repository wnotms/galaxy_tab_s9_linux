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

---

## Follow-up: the link is DOWN, and the GPIO states say power was applied

Reading the PCIe capability's Link Status register on the root port settles it:

```
link status = 0x0142
  bit13 Data Link Layer Link Active (DLLLA) = 0   <- the link is DOWN
```

and reading config space of `01:00.0` fails outright (`No devices selected`), which
is what "nothing on bus 01" looks like from userspace. The `2.5 GT/s x1` reported by
sysfs is therefore only the *negotiated-so-far* / floor value of a link that has not
reached the data-link-active state — `max_link_speed` is `8.0 GT/s`, so this is not a
speed-capability limit.

### The power sequence did run

From `/sys/kernel/debug/gpio` (TLMM is `gpiochip3`, 211 lines, `f100000.pinctrl`):

| line | state | meaning |
|---|---|---|
| `gpio80` | **out high** | `WLAN_EN` asserted — the pwrseq `wlan-enable` unit ran |
| `gpio94` | **out high** | `PERST` deasserted (declared `GPIO_ACTIVE_LOW`), so the endpoint is out of reset |
| `gpio81` | out low | `BT_EN` low — correct, Bluetooth is out of scope this round |
| `gpio82` | in high | `SWCTRL` |
| `gpio204` | out low | `XO_CLK`, deasserted *after* the enable, which matches the driver's `post_enable` hook (`pwrseq_qcom_wcn6855_xo_clk_deassert`) |

So the sequencing chain completed and the driver-side ordering is right:
`qcom_pcie_host_init()` asserts PERST, powers the PHY, calls
`pci_pwrctrl_power_on_devices()`, then deasserts PERST. The endpoint still does not
answer.

### A DTS claim that mainline does not implement

`qcom,wlan-pdc-init` and `qcom,qmp` are present in the board DTS, and the comment
above them explains they are the AOP PDC votes a **cold handoff** needs. They are
worth keeping. But a search of the entire pinned tree finds them **only in that
DTS** — no mainline driver reads either property. They are inert: nothing in
`pwrseq-qcom-wcn.c`, `pci-pwrctrl-pwrseq.c` or `pcie-qcom.c` consumes them, so on
mainline those votes must already have been applied by the boot chain or not at
all. That is a real difference from downstream `cnss2`, and it matters for the
cold-boot case below.

### Where that leaves the fault

The fault is now isolated to the endpoint side of a link that the host has finished
setting up, with power and reset applied. In order of likelihood:

1. **The endpoint needs more than `WLAN_EN`.** The `wcn6855-pmu` regulators are
   modelled but the endpoint's own rails (`vddpcie0p9`, `vddpcie1p8`, and the RF
   rails) are only declared on `wifi@0`; whether the pwrseq provider actually
   enabled them is not yet evidenced. Note the driver has logged
   `supply vdda not found, using dummy regulator` since the first probe.
2. **Cold handoff.** This boot was a warm one and the board DTS records that after a
   full poweroff the PMU may not complete power-up without correct PDC/AOP votes.
   Since mainline does not implement those votes, a cold boot is now a *specific and
   testable* hypothesis rather than a general worry — and it is the first thing the
   next test should separate.
3. **A missing board-specific step** that downstream `cnss2` performs, which no
   mainline driver currently does.

### Next physical test, revised

The stale-boot ordering also has to be cleared first: `1c00000.pcie` probed eight
times on this boot **before** the modules existed, and only the last attempt
succeeded. A clean reboot with the modules already installed is the honest baseline,
and it is needed before any of the three hypotheses above can be compared.

1. Reboot (warm), then run `scripts/wifi-preflight.sh` with the modules present from
   boot. Confirm the pwrctrl binds during the boot probe, without a manual
   `modprobe`.
2. Read the link status again — `DLLLA` must go to 1 for `17cb:1103` to appear.
3. If it is still down, compare a **cold** power-on against the warm reboot, per the
   brief's rule that the two are never merged into one claim.
