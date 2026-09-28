# Test253 attempt03: host recovery passed; physical cycles pending

The same-version/default LIBADBUSB Windows ADB server was reopened once with
`scripts/gts9-adb-host-rescan.sh`. It rediscovered native gts9wifi-0001; a real
USB shell verified the unchanged boot461c1408e42643afae5b48162771d077, PID834
and exact custom daemon SHA. No device/gadget/service/controller restart or
new reboot occurred. First native shell completed within a24.079s conservative
upper bound including host orchestration delay; this is not a performance
measurement. Host backend and37.0.1 version are unchanged. A50-poll continuous
NCM SSH session completed exit0 with the same boot/PID/UDC. The actual source
connection was169.254.141.163 ->169.254.42.1:22.

Native USB1MiB random payload push/pull passed exact size, SHA256 and byte
comparison. Device temporary payload was removed; both Windows test files
were moved back inside this repository's ignored .work archive, and the empty
D:\android\gts9-active\test253-adb-transfer directory was removed. The
owner's D:\android\platform-tools tools remain untouched. Host acceptance
shows exact kernel config/notes/DCC/profile and protected NCM/SSH files,
no failed unit, Code43 or CPU/kernel fault, and both SSH paths available.

The three registered physical disconnect/reconnect cycles remain unexecuted:
cycle01 capture is waiting for the owner's15s unplug/replug action. No cycle
is counted clean and no final series acceptance is claimed. ADB currently
works, but automatic cable-reconnect verification and full final acceptance
are pending. The raw connected `adb reconnect` incident from attempt02 stays
stopped; host-server rescan is a verified workaround for that observed host
state, not proof that every37.0.1 backend failure is repaired. No backend
switch, new daemon variant or charging/kernel configuration change was made.
Test252 stays stopped; Stage2/3 and further charging tests have not started.
