# Test253 current status: bounded cable recovery verified

Owner-adopted attempt04 completed three fresh physical computer USB unplug/
replug cycles with the installed optional Debian34.0.5-12 userspace repair,
same boot461c1408e42643afae5b48162771d077 and PID834. No new software variant,
kernel/config/DTB/module/rootfs-settings change, device/host-server restart,
controller reset, flash or reboot was made during this final series. Read
[attempt04 RESULTS](attempt-04/RESULTS.md), [machine summary](attempt-04/summary.json)
and full final-acceptance/ plus the per-cycle raw journals and seals.

Combined native-shell/NCM recovery upper bounds were14.100/15.346/15.060s,
each followed by155.487/155.466/151.345s real ADB+NCM/Wi-Fi checks. All final
identity/181+181 files/DCC/units/kernel/Code43/transport gates passed. NCM first
8s timeouts in all three cycles and one initial native not-found were preserved
and recovered inside the registered60s window. Two tightly contextual bounded
pre-enable DISABLE W messages completed ENABLE/worker; the third cycle had none.
This is bounded cable recovery with observed transients, not transient-free
operation, a failure-rate estimate, long-term CPU/USB reliability or all USB
failure modes. The same-boot1MiB byte/hash transfer prerequisite remains in
attempt03/transfer/, not relabelled as a new attempt04 transfer.

The optional daemon SHA is053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5
at /usr/local/libexec/gts9-adbd-reconnect; gts9-adbd-run selects it, falling back
to the preserved packaged daemon if absent on a future normal boot. Guard/
ep0 holder/no_disconnect/gadget/NCM/SSH keys/settings remain preserved.
ADB tools stay D:\android\platform-tools\adb.exe37.0.1-15733141/LIBADBUSB.

Earlier stops remain unchanged: initial UPower217/USER, attempt02 raw connected
Windows `adb reconnect` missing transport, and attempt03 incomplete physical
recovery evidence. Root RESULTS/SHA256 and older attempts describe those
historical phases, not the current result. Raw connected `adb reconnect`
remains unaccepted; scripts/gts9-adb-host-rescan.sh separately verified one
computer-side server reopen without disrupting NCM or restarting the device.
The cause of every host-backend/Code43 failure is not established.

Current kernel is still the authorized Test252 Stage1 battery candidate, not
promoted Test249 production. Test252's original stopped attempt remains
stopped; Stage2 TCPM/Stage3 SM5440 and further charging tests have not started.
The independent UPower namespace prerequisite issue is unresolved. No automatic
next hardware test or rollback follows this bounded ADB acceptance.
