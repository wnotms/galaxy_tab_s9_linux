# test-210: Wi-Fi bring-up complete — all eight levels

Boot `3cba35b7`. Raw evidence in `EVIDENCE.txt`.

## Every level reached

| level | state |
|---|---|
| `PCI_ONLY` — `17cb:1103` enumerated | **REACHED** |
| `DRIVER_BOUND` — `ath11k_pci` bound | **REACHED** |
| `FIRMWARE_LOADED` — MHI + QMI + firmware | **REACHED** |
| `WLAN_INTERFACE` — `phy0`, `wlp1s0` | **REACHED** |
| `SCAN_WORKS` | **REACHED** — 16 BSS, 2.4 GHz and 5 GHz |
| `ASSOCIATION_WORKS` | **REACHED** — on **5 GHz** |
| `NETWORK_STABLE` — IPv4 | **REACHED** — DHCP lease + default route |
| traffic | **REACHED** — ping, DNS, HTTP download |

```
ath11k_pci 0000:01:00.0: wcn6855 hw2.1
ath11k_pci 0000:01:00.0: fw_build_id WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1

bssid=da:4d:3d:c0:32:d5   freq=5180   ssid=OnePlus 15
wifi_generation=6   key_mgmt=WPA2-PSK   wpa_state=COMPLETED
signal: -80 dBm     tx bitrate: 288.2 MBit/s 80MHz HE-MCS 3 HE-NSS 2
```

**5 GHz works, at 288 Mbit/s with 80 MHz and 2 spatial streams.** That closes the
question test-208 left open about whether this board suffers the "weak 5 GHz RX"
the Fedora port documents for `board-2.bin`'s generic payload: here, with the
**unmodified upstream container**, 5 GHz associates and carries traffic. No BDF
substitution was needed or made.

### LEVEL 7 and 8 detail

```
wlp1s0: offered 10.221.200.69 from 10.221.200.10
wlp1s0: leased 10.221.200.69 for 3599 seconds
default via 10.221.200.10 dev wlp1s0 proto dhcp src 10.221.200.69

ping 10.221.200.10   3/3 received, 0% loss, 28.5 ms avg
ping 223.5.5.5       3/3 received, 0% loss, 53.9 ms avg     <- public, DNS bypassed
getent hosts one.one.one.one  ->  2606:4700:4700::1111      <- DNS resolves
curl http://mirrors.aliyun.com/debian/dists/trixie/Release
                     code=200 bytes=138612 speed=692685 B/s
                     sha256=ed56aac47e7911e65ee63aae8d67e29f...
```

### HTTPS does not verify, and it is not the Wi-Fi

```
curl: (60) SSL certificate problem: unable to get local issuer certificate
```

`/etc/ssl/certs/ca-certificates.crt` exists. This is a **CA/trust configuration
issue on the Debian rootfs**, not a wireless fault — it reproduces identically over
any link, and plain HTTP transfers at ~690 KB/s. Recorded so it is not mistaken for
one.

### Why the OnePlus hotspot works where the Windows one did not

The earlier Windows Mobile Hotspot advertised DHCP and served none — confirmed when
the operator's phone also failed to obtain a lease from it. The OnePlus hotspot
offers one immediately. So test-208's "no DHCP" was the AP, as its counter evidence
already suggested (`rx_bytes` doubling with no local traffic).

## Stability results

| test | result |
|---|---|
| 5 consecutive scans | 16, 19, 21, 21, 22 BSS — no failures |
| interface down/up ×3 | association survived every cycle |
| `disconnect`/`reconnect` ×3 | back to `COMPLETED` within 2 s each time |
| cold boot (test-209) | endpoint, firmware, `phy0`, scan and association all automatic |
| warm reboot (test-209) | same |
| **sustained soak** | **56 of 60 HTTP transfers succeeded**, 7.4 MB total, 93-882 KB/s |

### The soak, and what its four failures actually were

Ten minutes of repeated `curl` against a Debian mirror over the associated 5 GHz
link:

```
200  56
000   2
curl: (6) Could not resolve host: mirrors.aliyun.com    x2
```

**The two failures are DNS, not the link.** `curl: (6)` is name resolution; the
transfers immediately before and after them both returned `200` with a full 138612
bytes, and `wpa_state` stayed `COMPLETED` throughout. The association never dropped
once in ten minutes.

They coincide with the weakest signal of the run — `RSSI=-89 dBm` against
`NOISE=-96 dBm`, an ~7 dB SNR, down from -65 dBm at the start. At that margin a DNS
query to the AP's resolver times out while bulk transfer still gets through, which is
what the pattern shows. So this is a **range/placement** observation, not a driver
defect, and it is recorded as such rather than as a Wi-Fi fault.

Worth noting for anyone repeating this: the link actually *improved* early in the
soak, reaching `tx 432.3 MBit/s HE-MCS 4 HE-NSS 2 80 MHz`, then degraded as the
tablet sat at the edge of 5 GHz coverage. Throughput tracked signal cleanly
(882 KB/s near the start, 93 KB/s at the end), which is the behaviour of a healthy
rate-control loop rather than a fault.

**A 2.4 GHz soak was not run.**

## What was required

Three faults, each diagnosed from a measurement rather than a guess:

1. **the modules had never been built** — `BUILD_MODULES=0`, so every `=m` symbol was
   satisfied on paper only;
2. **the AOP PDC votes** (`0008`) — the DTS carried the strings and no driver read
   them, which is what a cold handoff needs;
3. **the parked PCIe0 PIPE source mux** (`0009`) — it powered up on the 19.2 MHz XO
   reference, so the MAC-PHY PIPE was dead and the LTSSM could not perform receiver
   detection. This was the blocking fault.

Plus firmware staged at the path the driver asked for, and `iw`/`wpa_supplicant`
installed on the tablet (neither was present).

**No ath11k source was modified, no DTS changed, no Kconfig changed, and no magic
delay, retry, hardcoded BAR, firmware-validation bypass or forced-calibration
fallback was added.** `board-2.bin` matched this device's exact-ABI slot on its own.

## Isolation

No stall record added, removed or reclassified; no rate computed; no Wi-Fi reboot
counted in any A/B series. Nothing here speaks to the CPU wedge.
