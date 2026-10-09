# SSC wireless admission recovery (read-only)

Same d197 boot; both clients on exact OnePlus13s BSSID e6:fe:3e:c9:6c:65,
computer10.49.219.63/tablet10.49.219.156. sshd listens on0.0.0.0:22 and[::]:22.
Initial Windows neighbor table had all-zero unresolved tablet MAC and TCP timed
out. Device-side one ping and bounded7s ARP observation preserved; later native
Windows TCP22 succeeded and neighbor resolved to actual00:03:7f:12:f4:14.
Observed ARP reply from actual computerMAC f8:cf:52:cd:be:9b; underlying loss cause
unproven. No staticIP, WiFi profile, SSH restart, route/firewall change or reboot.
TCP reachability alone is not authenticated Test372 admission; require fresh
registered preflight before mutation. Initial host import mistake was corrected
before a device command; raw actual command/evidence retained. Build/tests
executed:false, registration797dff95 qualification reused.
