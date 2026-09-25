# The X710's earliest abnormal event: SMMU context faults on the MDSS stream

Every boot of this port produces a handful of `arm-smmu` context faults in the
first half-second, before anything else abnormal happens. By the investigation's
own rule — establish `first abnormal event → first stalled subsystem →
downstream failures` — they have to be accounted for rather than skipped. This
document identifies whose traffic they are, and corrects a round-15 claim about
them.

**They are the display subsystem's. They are not the ADSP's, and they are not
new.**

## What the kernel says

Captured live on the current kernel:

```
[    0.337225] platform ae00000.display-subsystem: Adding to iommu group 11
[    0.337252] platform a600000.usb: Adding to iommu group 12
[    0.338395] arm-smmu 15000000.iommu: Unhandled context fault: fsr=0x402, iova=0xb87b1200, fsynr=0x630021, cbfrsynra=0x1c00, cb=9
[    0.351006] arm-smmu 15000000.iommu: FSR    = 00000402 [Format=2 TF], SID=0x1c00
[    0.359330] arm-smmu 15000000.iommu: FSYNR0 = 00630021 [S1CBNDX=99 PNU PLVL=1]
```

The stream is named in the fault record itself: **`SID=0x1c00`**.

## Whose SID is 0x1c00

`arch/arm64/boot/dts/qcom/sm8550.dtsi` at the pinned revision
(`v7.2-rc3`, `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`) contains exactly one
reference to that stream ID:

```
4061:		mdss: display-subsystem@ae00000 {
4062:			compatible = "qcom,sm8550-mdss";
...
4085:			iommus = <&apps_smmu 0x1c00 0x2>;
```

So the faults belong to **`ae00000.display-subsystem`** — the MDSS/DPU container.
They are display traffic, not ADSP traffic. The two occurrences in the capture are
also consistent with that: the first fault is **1.14 ms** after the MDSS is added
to its IOMMU group, i.e. at the moment the domain is installed for that master.

## Why the fault is reported at all

Two fields disagree in a way that is diagnostic:

| field | value | reading |
|---|---|---|
| `cb` | 9 | the context bank that *raised* the report |
| `FSYNR0 S1CBNDX` | 99 (`0x63`) | the context bank the *faulting transaction* was tagged with |

`S1CBNDX=99` is not context bank 9. A transaction arriving with a CB index that
does not match the bank reporting it is the signature of traffic reaching the
SMMU while the relevant context bank is not yet programmed — the display pipeline
left running by the bootloader, still fetching after the Domain-attribute setup
changed underneath it. That is a startup artefact of attaching the master, not a
driver taking a wrong address, and it is why the faults stop on their own.

## It is pre-existing, and its count varies per boot

The device's own evidence archive keeps the previous boot's kernel journal. All
eight retained archives predate the round-15 `CONFIG_HWSPINLOCK_QCOM` change, and
six of the eight contain these faults:

| archive (`…-<id8>`) | `Unhandled context fault` lines | SID |
|---|---|---|
| `1084b57a` | 0 | – |
| `36f5abea` | 2 | `0x1c00` |
| `7f8878b7` | 2 | `0x1c00` |
| `9e3bde71` | 10 | `0x1c00` |
| `b0cd2e21` | 2 | `0x1c00` |
| `61f93d8e` | 5 | `0x1c00` |
| `7f02df57` | 1 | `0x1c00` |
| `cd04c0ef` | 0 | – |

Two things follow. The **only** SID that appears anywhere in those archives is
`0x1c00`, so on this port every early SMMU context fault is display; and the count
is not deterministic (0–10), so it depends on how much MDSS traffic is still in
flight when the domain is installed — not on anything a driver does wrong.

## Correction: this is not an ADSP symptom

`reference/boot-tests/test-187-*/on-device/HWSPINLOCK-FIX-RESULT.md` records the
ten faults seen on the first post-`HWSPINLOCK_QCOM` boot and attributes them to
the ADSP:

> These faults are the ADSP's memory traffic being translated by a context bank
> that `request_firmware` failure left unprogrammed — a *consequence of missing
> firmware*, not of the hwspinlock change.

The temporal correlation was real — `remoteproc0: request_firmware failed: -2`
does appear next to the faults in that log — but the attribution is wrong. The
fault record names its own stream, and `SID=0x1c00` is the MDSS. The missing ADSP
firmware is a real gap, and it has nothing to do with these messages.

What survives from that paragraph is the *conclusion*: the faults are not caused
by the hwspinlock change. They are simply older than it.

## Relationship to the stall

Kept on the list, but not elevated:

* they are the **earliest** abnormal event of the boot, which is why they are
  documented at all;
* they are **display**, and the display is already a known source of early noise
  on this port — `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration`
  (`docs/DISPCC_RCG_WARNING.md`) is the same subsystem within 40 ms of them, and
  is likewise non-fatal and pre-existing;
* they occur on boots that stall and boots that do not. That direction cannot be
  tested for the two archived failures, whose evidence directories have since
  been rotated out, so **no claim is made** about the failing boots' fault counts;
* they leave no downstream trace: the system reaches multiuser normally, and no
  device is deferred or unbound because of them.

Nothing here proposes a change. Suppressing the report would hide the bootloader
hand-off problem rather than fix it, and the correct fix — if one is ever wanted —
is to quiesce the MDSS before the domain is installed, which is display work and
out of scope.

## Reproducing the check

```
grep -n "0x1c00" arch/arm64/boot/dts/qcom/sm8550.dtsi        # -> mdss@ae00000
dmesg | grep -c "Unhandled context fault"                    # -> 0..10, varies
dmesg | grep -ao "SID=0x[0-9a-f]*" | sort -u                 # -> SID=0x1c00
```

The per-boot count and its single SID are recorded by
`reference/boot-tests/test-188-*/shutdown-series.sh` as `CTXFAULTS` and `CTXSID`,
so the claim above is re-measured on every round instead of being asserted once.
