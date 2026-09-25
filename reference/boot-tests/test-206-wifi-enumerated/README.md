# test-206: THE ENDPOINT ENUMERATED — the PIPE-mux fix was the root cause

Boot `e122b3d9`, kernel `7.2.0-rc3-gts9wifi-dirty`, after flashing
`out/boot-bundle-wifi-pipe-mux` (`boot.img` `0cafa99a…`, `vendor_boot` and
`init_boot` unchanged). Raw capture in `EVIDENCE.txt`.

## LEVEL 1 reached

```
pci_dev 0000:01:00.0  vendor=0x17cb device=0x1103  class=0x028000
endpoint_0100 = PRESENT
link_status = 0x3013   dllla(bit13) = 1        <- link UP
current_link_speed = 8.0 GT/s   width = 1
revision = 0x01   subsystem = 17cb:0108
modalias = pci:v000017CBd00001103sv000017CBsd00000108bc02sc80i00
BAR 0 = 0x60400000-0x605fffff (64-bit), assigned
```

`17cb:1103` had **never** appeared in this project's history before this boot.

## The root cause, confirmed by the measurement that predicted it

`0009-phy-qcom-qmp-pcie-select-phy-source-on-pipe-mux.patch` was adopted because
`gcc_pcie_0_pipe_clk_src` read **19200000** (parked on the 19.2 MHz XO) while
`pcie0_pipe_clk` claimed 125 MHz — i.e. the MAC-PHY PIPE interface was dead and the
LTSSM could not perform receiver detection. After the fix:

```
gcc_pcie_0_pipe_clk_src = 18446744073709551615     (ULONG_MAX sentinel = PHY source)
link_status = 0x3013, dllla = 1
```

The prediction held: switch the mux, and the endpoint appears.

## LEVEL 2 and the path to LEVEL 3

`ath11k_pci` **bound and identified the hardware**:

```
ath11k_pci 0000:01:00.0: MSI vectors: 32
ath11k_pci 0000:01:00.0: wcn6855 hw2.1          <- hardware revision, measured
mhi mhi0: Requested to power ON
mhi mhi0: Power on setup success                 <- MHI works
mhi mhi0: Direct firmware load for ath11k/WCN6855/hw2.1/amss.bin failed with error -2
ath11k_pci 0000:01:00.0: failed to power up mhi: -110
```

**This settles the round's "do not guess `hw2.0`/`hw2.1`/`board-2.bin`" rule.** The
driver measured `hw2.1` and requested exactly one path. That output, not a
convention, is the authority, and it is now recorded as such.

The only remaining failure is `error -2` (`ENOENT`) — the firmware file is absent.
Nothing else in the chain is broken: PCIe enumerates, BAR is assigned, MSI works,
MHI powers on, and the driver identifies the part.

## What is needed, exactly

From the driver's own request and confirmed against
`drivers/net/wireless/ath/ath11k/core.c:492` (`.dir = "WCN6855/hw2.1"`):

```
/lib/firmware/ath11k/WCN6855/hw2.1/amss.bin
```

and, for the board data, `ATH11K_BOARD_API2_FILE` (`board-2.bin`) in the same
directory. `/lib/firmware` is a symlink to `/usr/lib/firmware` on this rootfs.

Per the round's rules these must come from a legitimate source with provenance
recorded — upstream `linux-firmware` if it carries a matching `hw2.1` revision, or
Samsung's own stock firmware. **No guessed BDF, no X910 board file, no internet
`board-2.bin` treated as X710 calibration, and no ath11k patch to bypass board
matching.**

## Current state

| level | state |
|---|---|
| `PCI_ONLY` | **REACHED** |
| `DRIVER_BOUND` | **REACHED** (`ath11k_pci` bound, hw2.1 identified) |
| `FIRMWARE_LOADED` | pending — `amss.bin` absent, `-ENOENT` |
| `WLAN_INTERFACE` | not reached |
| `SCAN_WORKS` … `NETWORK_STABLE` | not reached |

## Isolation

No stall record added, removed or reclassified; no rate computed; no Wi-Fi reboot
counted in any A/B series. The flash and reboot here are Wi-Fi bring-up steps only.
