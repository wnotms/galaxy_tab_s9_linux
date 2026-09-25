# test-203: the cold cycle, and the chip is silent on TWO buses

Full `systemctl poweroff`, confirmed by the console reaching
`Reached target poweroff.target` at 15:56:12 and then going quiet. The tablet then
restarted (boot `a214feda`). Captures: `cold-1-immediate.txt`, `cold-2-settled.txt`,
taken by `scripts/wifi-cold-boot-capture.sh`, which polls for the tablet and
snapshots the instant it answers rather than being run by hand later.

## Result: the cold cycle changes nothing

| | warm reboot (test-202) | this cold cycle |
|---|---|---|
| modules autoloaded | yes | **yes** |
| `1c00000.pcie` | `qcom-pcie` | **`qcom-pcie`** |
| `1c06000.phy` | `qcom-qmp-pcie-phy` | **`qcom-qmp-pcie-phy`** |
| `devices_deferred` | only `aux_bridge` | **only `aux_bridge`** |
| PCI devices | 1 | **1** — `0000:00:00.0` `17cb:0113` |
| `link_status` / `DLLLA` | `0x0142` / 0 | **`0x0142` / 0** |
| `0000:01:00.0` | absent | **absent** |
| `gpio80` `WLAN_EN` | out high | **out high** |
| `gpio94` `PERST` | out high | **out high** |
| PMU input rails | all enabled | **all enabled** |
| `vreg_pmu` internal rails | 0 registered | **0 registered** |

So the cold-handoff hypothesis — that the PMU needs the PDC/AOP votes a cold start
lacks — is **not supported**: cold behaves exactly like warm. This is worth having
tested, because it was the cheapest explanation and it is now excluded.

## And the decisive new evidence: a second, independent witness

The pstore console for the boot that preceded this one contains something that has
nothing to do with PCIe:

```
[    7.873591][  T183] Bluetooth: hci0: command 0xfc00 tx timeout
[    7.880222][  T90] Bluetooth: hci0: Reading QCA version information failed (-110)
[    9.985070][  T183] Bluetooth: hci0: command 0xfc00 tx timeout
[    9.991602][  T90] Bluetooth: hci0: Reading QCA version information failed (-110)
[   12.095694] ... (4 attempts, then it gives up)
```

`hci_qca` asks the WCN chip for its version over **UART14** — a completely different
bus from PCIe0 — and the chip answers **nothing**: four attempts, each timing out
with `-110` (`ETIMEDOUT`).

This matters because it removes the last PCIe-specific explanations. It is not the
link training, not the controller, not the PHY, not the iATU, and not the pinctrl:
**the WCN6855 is silent on both of its host interfaces.** That is one fault, not
two, and it sits below both of them.

Counted on the current and previous boots: 4 failures each. Two boots earlier: 0 —
that boot did not have `hci_qca` loaded, since the modules were not installed yet,
so it is not a counter-example.

Note against the round's own rule: this is recorded as an **observation about the
shared chip**, not as "Bluetooth caused it" and not as "Wi-Fi caused it". BT is
running and shares the PMU; the version-read failure is being used as evidence that
the chip is unpowered or held, which is a statement about the chip, not about
either driver. The round still forbids developing BT alongside WLAN.

## What that leaves

Both interfaces being silent, while `WLAN_EN` is high and `PERST` is released,
fits exactly one of the three candidates from test-202:

1. **the chip has no power** — its `vddpcie0p9`/`vddpcie1p8` and RF rails are
   declared on `wifi@0` and referenced from the `regulators { }` child of
   `wcn6855-pmu`, but **no mainline driver registers those internal LDOs**
   (`vreg_pmu` count in `/sys/class/regulator` is **0**). A chip with no core power
   cannot drive a PCIe link *or* answer a UART;
2. the chip is held in reset — `PERST` is driven high by the host, so this would
   have to be an internal or second reset line;
3. the chip has no clock — the `XO_CLK` pulse is issued by the driver's
   `post_enable` hook, and the PMU's optional `clk` is unset, matching upstream's
   working boards.

**Hypothesis 1 was the obvious reading and it is wrong — checked and withdrawn.**
The `regulators { }` child of a WCN PMU node holds the chip's *own* output LDOs, not
rails the host must switch on: upstream's accepted `sm8550-samsung-gts9wifi.dts`
declares the same 37 `vreg_pmu` references as this tree, and no mainline board
registers them as regulators either — `pwrseq-qcom-wcn` only does
`regulator_bulk_enable()` over the **inputs** (`vddio`, `vddaon`, `vddpmu*`,
`vddrfa*`, `vddpcie*`), which are the six PMIC rails verified *enabled* above.
A `vreg_pmu` count of 0 is therefore normal upstream behaviour, not a defect, and
the "missing internal LDO driver" explanation does not survive contact with a
working board.

That leaves the fault genuinely unexplained by anything in the software path, and
the honest position is the one the evidence supports: **the host applies power
enable, releases PERST, pulses XO and initialises the PHY, iATU and pinmux
correctly, and the chip answers on neither of its two host interfaces.**

## Caveat on the poweroff itself

The tablet was confirmed off (no ssh, no adb, console silent) and came back when
USB VBUS was present. The pmsg region still named an older boot (`639dc6d0`), and
`ramoops` lives in RAM that a true rail collapse would clear — so this should be
treated as *the closest to a cold start achieved so far*, not as a
guaranteed-cold power cycle with the battery disconnected. A genuinely cold start
(battery physically disconnected, or held off long enough for the rails to bleed)
remains a distinct, harder test. It is recorded rather than smoothed over, and the
cold/warm comparison above is only claimed for *this* meaning of cold.

## Explicitly not concluded

* Not "Wi-Fi works" and not "Bluetooth works": neither interface has ever come up,
  and `17cb:1103` has **never** appeared in any log in this project's history.
* Not an ath11k problem — `ath11k` has still never been loaded, so there is no
  authoritative `hw` revision or board id, and none is guessed.
* Not a DTS bug: the WLAN sections are identical to upstream mainline's own
  `sm8550-samsung-gts9wifi.dts` apart from comments.
* Nothing about the CPU wedge. No stall record added, removed or reclassified, no
  rate computed, no Wi-Fi reboot counted in any A/B series.
