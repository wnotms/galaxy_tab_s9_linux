# Survey of `gts9wifi-fedora-linux` against this tree

Read-only comparison of the Fedora port for this same SM-X710
(`~/gts9wifi-fedora-linux`, commit `ab123e7`) against our mainline tree, done to
find whether any *other* known problem has a known fix there. Every claim below was
checked in our tree, not assumed.

## Adopted

| their patch | why it matters | our state |
|---|---|---|
| `unpark-pcie0-pipe-mux.patch` | GCC PIPE source mux powers up on the XO reference and nothing switches it, so the MAC-PHY PIPE is dead and **the LTSSM never performs receiver detection** | **adopted as `0009`**; verified live before the change: `gcc_pcie_0_pipe_clk_src = 19200000` (parked on 19.2 MHz XO) while `pcie0_pipe_clk` reports 125 MHz |
| `wcn7850-pwrseq-cold-reset-aop.patch` | sends the `qcom,wlan-pdc-init` AOP votes and cold-resets `WLAN_EN` | **adopted as `0008`**; our DTS already had the strings and no driver read them |

## Already present here, no action

| their patch | our state |
|---|---|
| `keep-sec-log-previous-index-current.patch` | **already implemented** — `kernel/drivers/samsung-gts9wifi-sec-log.c` line 175ff carries the same reasoning and the same `WRITE_ONCE(previous_index, index)`. This matters because `last_kmsg` is one of the stall evidence channels. |
| `ignore-console-null.patch` | **already present** as `0003-printk-allow-ignoring-samsung-console-null.patch` |
| `configure-nxp-ptn3222-from-dt.patch` / `match-samsung-sm8550-eusb2-phy-init.patch` | **already present** as `nxp-ptn3222-apply-dt-register-overrides.patch`; the log confirms `ptn3222 8-004f: applied 5 register overrides` |
| `add-gts9wifi-dtb.patch`, `add-samsung-sec-log-console.patch`, `expose-separate-gpu-kms-resources.patch`, `msm-dp-*` | superseded — our tree carries the equivalent work as `0001`/`0002`/`0004`/`0006`/`0007` and the board DTS |

## Checked and deliberately not adopted

| their patch | our state, and why not |
|---|---|
| `quiet-adsp-handover-already-happened.patch` | the spam it suppresses does **not** occur here: `grep -c "Handover signaled, but it already happened"` on a real stall record (test-199's wedged boot) is **0**. No evidence, so no patch. |
| `build-wcn-pcie-providers-in.patch` (makes the pwrseq/pwrctrl providers `=y`) | ours are `=m` and that is **proven sufficient**: `wifi@0` binds `pci-pwrctrl-pwrseq` and `wcn6855-pmu` binds `pwrseq-qcom_wcn` during boot with no manual `modprobe`. Building them in would be a real change for no measured benefit, and the round forbids unnecessary churn. Worth revisiting only if a future boot shows a race between udev and the PCIe probe. |

## Not examined

`qcomtee-*`, `tcpm-*`, `set-mi2s-codec-dai-format`, `msm-dp-*`: outside this round's
scope (tee, USB-C role, audio, display), and none of them touch the WLAN or stall
paths. Listed here so the survey is complete rather than selective.

## The honest summary

Exactly two patches were taken. Both were adopted because the failure they describe
**matched a measurement already in hand** — the parked mux at 19.2 MHz, and the
inert PDC strings — not because they came from a tree that works. Neither has been
verified on our hardware yet, and the outcome of that verification is recorded
separately. Everything else was either already here or had no supporting evidence
in our logs.
