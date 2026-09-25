# test-208: Wi-Fi is up — scan and association both work

Boot `e122b3d9`, the kernel with the PIPE-mux fix (`0009`). Raw evidence in
`EVIDENCE.txt`.

## The levels reached

| level | state |
|---|---|
| `PCI_ONLY` — `17cb:1103` enumerated | **REACHED** (test-206) |
| `DRIVER_BOUND` — `ath11k_pci` bound | **REACHED** |
| `FIRMWARE_LOADED` — MHI + QMI + firmware | **REACHED** — the chip identifies itself |
| `WLAN_INTERFACE` — `wlp1s0` / `phy0` | **REACHED** |
| `SCAN_WORKS` | **REACHED** — 17 BSSes, 2.4 GHz and 5 GHz |
| `ASSOCIATION_WORKS` | **REACHED** — WPA2-PSK, `wpa_state=COMPLETED` |
| `NETWORK_STABLE` — IPv4 + traffic | **partly**: associated and exchanging frames, but the AP served no DHCP lease |

## LEVEL 3: the firmware the driver asked for, loaded

```
ath11k_pci 0000:01:00.0: wcn6855 hw2.1
mhi mhi0: Power on setup success
mhi mhi0: Wait for device to enter SBL or Mission mode
ath11k_pci 0000:01:00.0: chip_id 0x12 chip_family 0xb board_id 0xff soc_id 0x400c1211
ath11k_pci 0000:01:00.0: fw_version 0x11021302 fw_build_timestamp 2026-02-04 08:10
ath11k_pci 0000:01:00.0: fw_build_id WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1
ath11k_pci 0000:01:00.0 wlp1s0: renamed from wlan0
```

Note the path was **not guessed**: the driver asked for
`ath11k/WCN6855/hw2.1/amss.bin`, so that is where the files went, and the
**`hw2.1`** revision came from the driver's own probe.

## LEVEL 4: interface and rfkill

`/sys/class/ieee80211/phy0`, `wlp1s0` (MAC `00:03:7f:12:ce:0c`), driver
`ath11k_pci`, rfkill soft- and hard-unblocked.

## LEVEL 5: scan

**17 BSSes**, on both bands — 2.4 GHz (2412/2437/2462) and **5 GHz (5300)**. So both
radios work, which is the direct answer to the earlier open question about the
"generic payload's weak 5 GHz RX": 5 GHz is receiving here.

## LEVEL 6: association

Associated to the host's own hotspot, WPA2-PSK, using a hand-written
`wpa_supplicant` config — deliberately **not** the distro's systemd unit, so the
association is attributable to this driver and not to a manager:

```
ssid=DESKTOP-S24EEHN 9670
bssid=fa:cf:52:cd:be:9b
freq=2437
wpa_state=COMPLETED
key_mgmt=WPA2-PSK
pairwise_cipher=CCMP
wifi_generation=6
```

and the link is carrying frames in both directions:

```
Connected to fa:cf:52:cd:be:9b
    SSID: DESKTOP-S24EEHN 9670
    RX: 9709 bytes (57 packets)
    TX: 1299 bytes (12 packets)
    signal: -15 dBm
    tx bitrate: 68.8 MBit/s HE-MCS 3 HE-NSS 2
```

That is **802.11ax (HE)** with 2 spatial streams — the chip is running at Wi-Fi 6,
not falling back to legacy rates.

## LEVEL 7: not yet — and the evidence points at the AP, not the driver

`dhcpcd` sends DISCOVER and no OFFER comes back, so the interface falls back to
IPv4LL (`169.254.175.120`). Probed for the usual Windows-hotspot gateways
(`192.168.137.1`, `192.168.0.1`, `10.0.0.1`) with a static address in each subnet:
none answers, and the neighbour entry stays `INCOMPLETE`.

**But the link itself is demonstrably bidirectional.** Sampling the interface
counters 12 seconds apart with no traffic generated locally:

```
rx_bytes  6140 -> 13220     <- the AP is transmitting to us
tx_bytes  7012 ->  7322
```

RX roughly doubled from beacons and AP traffic alone, and `iw link` shows
76837 bytes / 401 packets received against 7607 / 62 sent, at -17 dBm. So layer 2
works in both directions and the receive path is healthy; what is missing is an
L3 address, which is the AP's DHCP server declining to serve this client — a
Windows Mobile Hotspot condition, not an ath11k fault.

Stated plainly rather than as "network works": **there is no IPv4 lease, so DNS and
HTTP were not tested.** The tablet also has no route off its `usb0` link-local
network, so those tests would not have been possible regardless of the lease.

Also relevant: the tablet has **no route to the internet** (only the `usb0`
link-local network), so DNS and HTTP could not be tested even with a lease.

## What was needed, for the record

* the PIPE-mux fix (`0009`) to make the endpoint enumerate at all;
* the AOP PDC votes (`0008`) for the chip's power handshake;
* firmware staged at the path the driver asked for, from the CodeLinaro mirror of
  Qualcomm's ath11k-firmware tree — the **IOE** family, which the
  `gts9wifi-fedora-linux` port for this same tablet records as the reliable one and
  which matches the `fw_build_id` the chip now reports;
* `iw` and `wpa_supplicant` installed on the tablet from Debian arm64 packages,
  because neither was present.

**No ath11k source was modified, no DTS changed, no Kconfig touched, and no magic
delay, retry, hardcoded BAR or firmware-validation bypass was added.** `board-2.bin`
matched the device's exact-ABI slot on its own.

## Isolation

No stall record added, removed or reclassified; no rate computed; no Wi-Fi reboot
counted in any A/B series. Nothing here says anything about the CPU wedge.
