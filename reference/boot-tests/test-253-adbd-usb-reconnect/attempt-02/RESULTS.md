# Test253 attempt02: stopped at connected host reconnect

The adopted UPower prerequisite classification and full unchanged Test252
candidate preflight passed. Installation preserved packaged adbd, backup of
original service bytes, guard/holder/gadget/NCM/SSH identities. Device loader
and --version passed. Continuous NCM SSH survived staging with the old PID838.
One normal reboot was uniquely attributed from fcb9a367fa8e43dfafb108db722ff2f1
to461c1408e42643afae5b48162771d077; target/new journals are kept separately.
All five partitions,181 candidate/181 original files, exact config/notes and
DCC/profile remain matched. New daemon PID834 runs the manifest binary hash.
Native USB shell, NCM and Wi-Fi SSH passed the boot gates. A152.945s elapsed
window kept native shell/Wi-Fi responsive with no CPU/kernel fault. Wi-Fi DHCP
changed195 ->29; old-address failure and discovered address are preserved.

`adb -s gts9wifi-0001 reconnect` at14:01:56.215UTC returned0 but removed the
Windows server's USB transport. Nineteen subsequent native-shell probes could
not find the serial; the later post-stop device list remained empty. Recovery
within the registered≤60s bound was not established. The series stopped;
no1MiB transfer or physical cable cycle was issued. A50-s NCM SSH session
survived this operation, same boot/PID834/UDC throughout. Both SSH channels,
configured UDC and Windows ADB/NCM PnP interfaces remain healthy, no Code43.
Device worker/monitor still wait normally with no new FunctionFS lifecycle
message or daemon error. Host37.0.1 uses LIBADBUSB; its log records resetting
transport/read-failed at22:01:56CST. This localizes the observed missing
transport to host state, but does not prove the backend's underlying cause.
Read-only post-stop identity/full kernel logs show no CPU fault and no drift.

This is stopped, not passed and not resumed. Initial Test253 and Test252
stopped outcomes remain intact. The fixed daemon is installed but reconnect
acceptance is incomplete. No kernel/charging configuration or additional
reboot/reset/service restart was performed. Next independent host recovery
may reopen only the Windows ADB server with identical version/backend, under
a separate registration; it must not silently amend this failed outcome.
