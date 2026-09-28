# Test253 attempt03: host recovery passed; physical capture stopped

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

The owner performed physical cycle01, but its sampler missed the cable state
transition because UDC remained configured while USB supply was offline. Native
ADB subsequently recovered with the unchanged boot/PID/hash. The registered
60s native-shell deadline and150s elapsed observation were not collected;
cycle01 is not accepted and attempt03 stops. No cycle02/03 or final series
acceptance occurred. Preserve cycle01/review.json, full raw journals and the
complete post-stop identity/transport check. The new pre-enable DISABLE warning
requires source review before further classification. No software/device change,
extra host server restart or reboot occurred in this physical cycle.

Attempt02's raw connected `adb reconnect` incident remains stopped. Host-server
rescan is a verified workaround for the observed missing transport, not proof
that every37.0.1 backend failure is repaired. Test252 remains stopped; Stage2/3
and further charging tests have not started.
