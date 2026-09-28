# Physical cycle01: stopped on incomplete evidence

The owner performed one unplug/replug without reboot or charger. Raw Wi-Fi
polls show USB ONLINE=0 and native host device-table disappearance, while UDC
stayed configured. The sampler wrongly required both UDC unconfigured and
ONLINE=0, so it never entered recovery collection. Its host process was stopped;
raw poll/log files are preserved. No registered <=60s native shell or150s
responsive observation was collected. This is not a passed cycle.

Native ADB subsequently executed a real shell on the same boot/PID834 with the
exact installed daemon hash. Full post-stop config/notes/five partitions/181
candidate plus181 original modules, protected NCM/SSH settings, DCC and both
SSH channels pass, without failed unit, Code43 or kernel/CPU signature. This
later check cannot establish the missing recovery deadline.

The full adbd journal records SUSPEND1490.700347, an internal transport teardown,
DISABLE1510.417270 with `received FUNCTIONFS_DISABLE while not enabled?`, then
ENABLE1510.565311 and worker1510.565463 without a daemon restart. This new warning
requires source review before future classification; it is not silently exempted.
Attempt03 stops here: one physical cycle performed, zero accepted, no cycle02.
