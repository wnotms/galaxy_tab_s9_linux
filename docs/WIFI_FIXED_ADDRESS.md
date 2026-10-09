# Wi-Fi fixed address for device testing

Use the owner-managed router's DHCP address reservation for the tablet's active
Wi-Fi MAC, with the desired address10.49.219.42. This maintains automatic gateway
and DNS and scopes the address to that network. Use the router's connected-client
entry for gts9/the tablet and its currently shown MAC; confirm the address is not
reserved for another device. Router menu names vary (DHCP address reservation /
static lease / fixed client address). Do not use the Windows PC or USB NCM MAC.

Read the tablet's Wi-Fi MAC in its terminal:

```sh
cat /sys/class/net/wlp1s0/address
```

wlp1s0 was the actual Test370 Wi-Fi interface. If a future kernel changes its name,
inspect `nmcli device status` first. A per-network randomized MAC must be stable
for a reservation; inspect the existing connection before changing MAC policy.
Do not force a global hardware-MAC change without checking the active profile.

Keep Debian's Wi-Fi IPv4 method automatic after reserving it in the router.
Do not reconnect during an armed physical charging/USB test. Verify the next
normal reconnection receives the reserved address and SSH reaches the same
machine; no reboot is needed just to save a router reservation.

If the router cannot reserve DHCP, a NetworkManager manual-address alternative
needs the real prefix, gateway, DNS and an approved address outside its dynamic
allocation or explicitly excluded by the router. Back up the exact connection
profile and use bounded NetworkManager checkpoint/rollback before activation.
Do not guess10.49.219.1, overwrite all Wi-Fi profiles, or fix a10.x address for
unrelated SSIDs. USB/NCM stays independent at169.254.42.1/16.

Reference: [router DHCP reservation example](https://www.tp-link.com/in/support/faq/182/)
and [NetworkManager IPv4 methods](https://www.networkmanager.dev/docs/api/latest/settings-ipv4.html).
Current preparation: `reference/desktop-bringup/wifi-static-ip/RESULTS.md`.
