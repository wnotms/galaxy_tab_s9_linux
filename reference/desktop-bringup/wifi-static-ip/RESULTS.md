# Wi-Fi fixed-address preparation — no device mutation

Owner confirms Debian desktop normal, address10.49.219.42 and manageable private
router/hotspot. Enrolled Windows TCP SSH still failed banner exchange before the
NetworkManager read-only program ran (exit255). Independent native Windows TCP
probe timed out5s, direct WSL TCP22 also timed out. ADB list empty while unplugged.
No new boot ID, battery, MAC, gateway, DHCP options or health snapshot obtained;
do not infer CPU stall from this transport evidence. Prior accepted370 snapshot
records wlp1s0 DHCP10.49.219.42/24, not a fresh qualification.

Preferred route: router DHCP address reservation for the tablet's actual Wi-Fi
MAC and10.49.219.42; keep NetworkManager DHCP so gateway/DNS stay automatic.
Router model, current MAC, reservation availability and pool must be obtained
from owner/router before applying. No router credentials requested, no router
write, device Wi-Fi modification, USB/NCM change, service restart or reboot.
Static IP alone cannot fix the currently unreachable TCP22 at unchanged address.
Test371 physical preflight/helper activation remains unstarted, registration
and historical STOP results unchanged. Do not manufacture a CLEAN result.

Host tests/build: executed:false (read-only transport evidence/docs only).

## Owner update and recovery

Phone hotspot, owner defers static IP. New actual address10.49.219.156 SSH
succeeds, machine/config/notes match accepted370. Owner confirms manual reboot
explains d1977159-8330-4c90-b5be-e7cf8c67ea0f (no host reboot issued).
MAC00:03:7F:12:F4:14, actual gateway/DNS10.49.219.11, DHCP/24 retained.
73%/30.8C/Good/discharging, required services active, no failed unit.
Complete kernel journal passed unchanged Test370 startup classifier, no new
HFI/CPU fault/suspect. Test371 initial enrollment updated before any formal
preflight or device mutation; earlier registration retained. No static setting.
