# test-209: Wi-Fi works on BOTH cold and warm boot — and a boot-time regression found

Boot `ee79757e` (cold power-on) and `7d2e31d3` (warm reboot). Raw evidence in
`COLD-BOOT.txt` and `PRE-STATE.txt`.

## Both boot paths reach full Wi-Fi, with no manual step

| | cold power-on (`ee79757e`) | warm reboot (`7d2e31d3`) |
|---|---|---|
| `17cb:1103` enumerated | **yes** | **yes** |
| modules autoloaded | **yes** — `pwrseq_qcom_wcn`, `pci_pwrctrl_pwrseq`, `ath11k_pci`, `ath11k`, `mac80211`, `cfg80211`, `qrtr_mhi` | **yes** |
| firmware | `wcn6855 hw2.1`, `WLAN.HSP.1.1-04866.5-…-IOE-1` | same |
| `phy0` / `wlp1s0` | **yes** | **yes** |
| scan | **16 BSS, 2.4 GHz and 5 GHz** | yes |
| association | `wpa_state=COMPLETED`, WPA2-PSK, 802.11ax, -18 dBm | yes |

**This is the result patch `0008` (AOP PDC votes) existed for.** The board DTS and
the Fedora port both record that after a cold handoff the WCN PMU cannot complete
its power-up without those votes, and that mainline had no driver to send them.
A genuine power-off → power-on now reaches a working `wlp1s0` on its own.

So for the first time the brief's cold/warm requirement is satisfied **with Wi-Fi
working**, rather than reporting two matching failures.

## Regression found: userspace boot takes 101 s instead of 8 s

The operator reported the tablet appearing to hang on the boot log after a reboot,
and asked whether it is expected. **It is not.** `systemd-analyze`:

```
boot  0 (this one):  Startup finished in 1.818s (kernel) + 1min 42.386s (userspace)
boot -1 (7d2e31d3):  Startup finished in 1.821s (kernel) + 8.013s (userspace) = 9.835s
```

`systemd-analyze blame` on the slow boot:

```
1min 37.388s wpa_supplicant.service
1min 30.677s systemd-backlight@backlight:ae94000.dsi.0.service
1min 16.776s gts9-usb-acm.service
1min  1.685s gts9-prev-boot-evidence.service
     46.605s gts9-panel-recover.service
```

### The `wpa_supplicant.service` entry is mine, and it is fixed

Installing the `wpasupplicant` package for the association test **enabled**
`wpa_supplicant.service` and its D-Bus activation symlink, so it ran on every boot
and blocked `network.target` for 91 s:

```
ExecStart=/usr/sbin/wpa_supplicant -u -s -O "DIR=/run/wpa_supplicant GROUP=netdev"
```

`systemctl disable wpa_supplicant.service` removes both symlinks
(`multi-user.target.wants/` and `dbus-fi.w1.wpa_supplicant1.service`). Association
is done from a hand-written config in this project precisely so that no manager
sits in the boot path; installing the package quietly undid that.

### The remaining entries are the USB-console back-pressure already documented

`gts9-usb-acm`, `gts9-prev-boot-evidence`, `systemd-backlight` and
`gts9-panel-recover` all *report* long durations, and **nothing at all happens in
the journal between 5.5 s and 96.2 s** — a single quiet gap, not four independent
stalls. That matches `docs/USB_SERIAL_CONSOLE.md`:

> A large write to `/dev/ttyGS1` blocks the shell if nothing is draining the port.
> Writing 128 KiB to it while reading COM17 wedged the shell until COM19 was opened
> and drained.

The mechanism is the same one: `ttyGS1` carries `printk`, the gadget has a bounded
number of OUT requests, and when no host reader is draining COM19 the writers
block. The honest reading is that **the boot did not take 101 s of work — it waited
on a console nobody was reading**, and it completed the moment COM19 was opened,
which is exactly what the operator observed ("打开COM19后恢复").

This is consistent with the healthy 8 s figure on boot `-1`, where COM19 was being
read during the reboot by the test tooling.

### What this means for reading boot times here

A boot measured without a host reader on COM19 is not a boot-time measurement.
Any future timing claim must state whether COM19 was held open, and this repo's own
`docs/USB_SERIAL_CONSOLE.md` already warns about it — it was previously analysed for
*shutdown* (`docs/SLOW_SHUTDOWN_ANALYSIS.md`), where the same uptime-scaling wait
was found.

## Isolation

No stall record added, removed or reclassified; no rate computed; no Wi-Fi reboot
counted in any A/B series. No ath11k source, DTS or Kconfig change.
