# test-205: the missing piece, found in the Fedora port for this same board

Read-only analysis of `~/gts9wifi-fedora-linux` (commit `ab123e7`), a Fedora port for
**the same SM-X710**. Nothing was flashed or changed.

## The finding

That tree carries `kernel/patches/wcn7850-pwrseq-cold-reset-aop.patch`, and its own
comment describes this board's failure exactly:

> Samsung's cnss2 programs the AOP WLAN PDC resources through the QMP mailbox before
> the first WCN power-on. … without them **the WCN PMU never completes its power
> handshake and the PCIe receivers stay undetected.**

"PCIe receivers stay undetected" is precisely what we measured:
`qcom-pcie 1c00000.pcie: Device not found`, LTSSM `DETECT_QUIET`, no link partner.

The patch does two things, both for `wcn6855`:

1. **`cold_reset_wlan = true`** on `pwrseq_wcn6855_of_data`, which changes
   `wlan_gpio` from `GPIOD_ASIS` to **`GPIOD_OUT_LOW`**, then settles
   `usleep_range(5000, 10000)` so the sequence starts from a known state. This is the
   upstream FIXME being resolved for this part: upstream deliberately keeps
   `GPIOD_ASIS` because it assumes the boot chain already powered the chip, and that
   assumption does not hold here.
2. **`pwrseq_qcom_wcn_program_wlan_pdc()`** — walks `qcom,wlan-pdc-init` and sends
   each string through the AOP QMP mailbox, guarded by
   `of_property_present(dev->of_node, "qcom,qmp")` so boards without it are skipped
   silently.

## Why this lands exactly on our evidence

Everything the patch needs is already present in our tree and on the tablet:

| requirement | state |
|---|---|
| `include/linux/soc/qcom/qcom_aoss.h` | **present**, with `qmp_send` / `qmp_get` / `qmp_put` |
| `CONFIG_QCOM_AOSS_QMP` | **`=y`** |
| AOSS device `c300000.power-management` | **bound to `qcom_aoss_qmp`** |
| `qcom,qmp = <&aoss_qmp>` in our DTS | **present** |
| `qcom,wlan-pdc-init = …` (11 votes) in our DTS | **present** |

And the two DTS facts I established earlier line up with it:

* the properties are **inert on mainline** — a whole-tree search finds `qcom,qmp` and
  `qcom,wlan-pdc-init` only in the DTS, because **no upstream driver reads them**.
  This patch is that missing reader;
* they came from the stock X710 `cnss` `qcom,pdc_init_table`, which is the
  provenance the Fedora tree independently cites.

Our board DTS is otherwise **identical** in the WLAN section, including the same
`wcn6855_pmu` compatible, the same four GPIOs, the same `pinctrl-0` and the same
11 PDC strings. So this is the same board, the same silicon, the same symptom, and a
known-good change — not a guess.

## What this changes about our conclusion

It **supersedes** the "measure the rails" recommendation from test-204. That advice
assumed the fault was physical and unobservable from software. It is observable: the
missing step is a mailbox write the kernel never performs, and the fix is small,
generic and already written for this exact part.

It also **retroactively explains** the cold/warm result. The comment above says the
xo-clk strobe alone starts the chip "only when the boot chain hands the chip over
already powered", and that "after a full poweroff (cold handoff) the PMU never
completes power-up without these votes". Our cold and warm runs both failed, which is
consistent: once the chip is in the unsequenced state, neither path recovers it,
because neither sends the votes.

## Provenance and honesty about it

* Source: `~/gts9wifi-fedora-linux`, file
  `kernel/patches/wcn7850-pwrseq-cold-reset-aop.patch`, 112 lines, seen at commit
  `ab123e7`. It is a **downstream port patch**, not upstream mainline.
* Its filename says `wcn7850` but its `of_data` hunks set `cold_reset_wlan = true`
  for **`wcn6855`** as well, which is our part. The WLAN PDC helper is
  chip-agnostic.
* **Not yet verified on our device.** It is evidence about what this board needs,
  not proof that it fixes our symptom — that requires building it and running the
  same measurement.
* The brief's rule against copying X910 blobs does not bite here: this is not a
  blob, BDF, voltage or GPIO from another device. It is driver logic for the *same*
  `wcn6855`/`17cb:1103` part on the *same* SM-X710, and the DTS it operates on is
  byte-comparable to ours.

## Next test

Bring the patch into our tree as a **reviewable, self-contained change** and verify
by measurement, not by inspection:

1. apply it as a proper patch under our patch queue with the Fedora provenance
   recorded, keeping it separate from any stall work;
2. build with `USE_CCACHE=1`, confirm the module still matches the flashed kernel's
   vermagic, and stage it with `scripts/stage-wifi-modules.sh`;
3. `modprobe -r pwrseq-qcom-wcn; modprobe pwrseq-qcom-wcn` (or reboot) so `probe`
   re-runs and sends the PDC votes, then **immediately** read the link status at the
   correct offset and `devices_deferred`;
4. success is `DLLLA (bit13) = 1` and `0000:01:00.0` with vendor:device `17cb:1103`.
   Only then does `ath11k` become reachable, and only then does its actual firmware
   request — not a guess — decide the `hw` revision and board file.

If the link still does not train with the votes sent, that is a real result too, and
it would move the question to the rails as test-204 said.
