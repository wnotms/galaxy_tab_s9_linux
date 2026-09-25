# test-207: upstream firmware search — the `hw2.1` directory does not exist upstream

Following the round's instruction to prefer upstream `linux-firmware` and to take
the driver's own output as authority. Read-only: nothing downloaded, nothing staged,
nothing flashed.

## What the device actually asked for

`lspci -nn` on boot `e122b3d9`, after the PIPE-mux fix:

```
00:00.0 PCI bridge [0604]: Qualcomm SM8550/SM8650 PCIe Root Complex [17cb:0113]
01:00.0 Network controller [0280]: Qualcomm QCNFA765 Wireless Network Adapter [17cb:1103] (rev 01)
```

and the driver, from the clean reload:

```
ath11k_pci 0000:01:00.0: MSI vectors: 32
ath11k_pci 0000:01:00.0: wcn6855 hw2.1
mhi mhi0: Power on setup success
mhi mhi0: Direct firmware load for ath11k/WCN6855/hw2.1/amss.bin failed with error -2
ath11k_pci 0000:01:00.0: failed to power up mhi: -110
```

So the requested path is **`ath11k/WCN6855/hw2.1/amss.bin`** and the hardware is
**`hw2.1`** — both reported by the driver, neither assumed. This matches
`drivers/net/wireless/ath/ath11k/core.c:490` (`.name = "wcn6855 hw2.1"`,
`.fw.dir = "WCN6855/hw2.1"`), and `pci.c:1056` selects HW21 from the SoC version
registers, so the selection is correct.

## What upstream `linux-firmware` ships

From the kernel.org / googlesource mirror of
`linux-firmware` at `refs/heads/main`:

```
ath11k/WCN6855/
    hw2.0/                      <- the ONLY revision upstream provides
        Notice.txt  amss.bin  board-2.bin  m3.bin  regdb.bin
        nfa765/                 <- a variant dir: Notice.txt amss.bin m3.bin
```

**There is no `ath11k/WCN6855/hw2.1/` upstream.** Confirmed by listing the directory
and by the absence of any other `WCN6855` tree (`ath11k/` contains `IPQ5018`,
`IPQ6018`, `IPQ8074`, `QCA2066`, `QCA6390`, `QCA6698AQ`, `QCN9074`, `WCN6750`,
`WCN6855` — `WCN6855` with `hw2.0` only).

## An interesting and potentially useful fact

`ath11k/QCA6698AQ/hw2.1/` **does** exist, and its `amss.bin` is **byte-identical**
(same git blob `a73b4b2f…`) to `ath11k/WCN6855/hw2.0/nfa765/amss.bin`. `m3.bin` is
likewise identical (`7b66e6b0…`). The variant directory is named **`nfa765`** — which
is exactly the module name `lspci` reports for our device ("QCNFA765"), and the name
`ath11k` itself uses in its usecase table for `ATH11K_HW_WCN6855_HW21` boards:

```c
{ ATH11K_HW_WCN6855_HW21, "qcom,lemans-evk",     "nfa765"},
{ ATH11K_HW_WCN6855_HW21, "qcom,monaco-evk",     "nfa765"},
{ ATH11K_HW_WCN6855_HW21, "qcom,hamoa-iot-evk",  "nfa765"},
```

So upstream knows `hw2.1` + `nfa765` as a valid combination for other SM8550-family
boards. **That is evidence, not a licence to copy**: the usecase table is keyed on
`of_machine_is_compatible()`, which does not match this device, and using the
QCA6698AQ `board-2.bin` as X710 calibration would be exactly the "unmatched
calibration" the round forbids. `board-2.bin` is per-board RF calibration data; a
different board's file is not interchangeable.

## What this means, and what it does not

* The missing `hw2.1` directory is a **genuine upstream packaging gap**, not a
  mistake in this port: our kernel's supported-hardware table includes
  `wcn6855 hw2.1`, and the firmware repository simply has no directory for it.
* It does **not** follow that any available blob may be renamed into place. Staging
  `QCA6698AQ`'s or `hw2.0`'s files under `WCN6855/hw2.1/` would be guessing a
  calibration file for this board, which the round prohibits and which would be
  dishonest to record as verified.
* The driver request is the authority, and it is unambiguous: the file it wants does
  not exist upstream.

## Next step, per the round's own priority order

The instruction is explicit: prefer upstream, and **only if the standard
firmware/BDF cannot match the X710, then analyse the Samsung stock partitions for
WLAN firmware**. That condition is now met and demonstrated — the standard firmware
has no `hw2.1` directory at all.

So the next step is to look at the device's own legally-owned stock firmware for a
WCN6855 `hw2.1` `amss.bin` and `board-2.bin`, with source partition, filename and
SHA-256 recorded for each, and staged through
`scripts/stage-wifi-firmware.sh` so the provenance is auditable and the blobs are
never committed to Git. **No extraction has been performed yet**, and no blob has
been placed anywhere.

## Isolation

No stall record added, removed or reclassified; no rate computed; no Wi-Fi reboot
counted in any A/B series. Nothing was downloaded to the device or the repo.
