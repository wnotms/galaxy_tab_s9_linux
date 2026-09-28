# First physical cycle: source review and proposal

Immutable Debian baseline `userspace/adbd/source-baseline/usb.cpp` StartMonitor
initializes `enabled=false` for each connection. The installed patch remembers
actual BIND and retains ep0, but deliberately does not carry enabled across
connections. FUNCTIONFS_DISABLE logs a warning when enabled is false; both
warning and ordinary paths then set enabled=false and running=false, end the
monitor and recreate the transport. The warning has no separate fatal branch.
This observation does not prove why the event arrived at that connection.

Attempt03 cycle01 journal, PID834, boot461c...:
- SUSPEND1490.700347, while physical USB supply became offline.
- Original transport teardown1510.374902.
- New monitor6845/DISABLE and W1510.417270; monitor ends.
- Next monitor6846, ENABLE1510.565311, worker6847 at1510.565463.
- Native host table device transport2 reappears; actual later shell works.

This is consistent with an old DISABLE reaching a newly created pre-enable
monitor during internal transport handoff. ENABLE follows the warning by
0.148041s; daemon PID/hash and kernel/SSH settings never changed. Full post-stop
identity/transport/kernel gates pass. This supports a tightly bounded
recoverable-teardown classification, not certainty about event queuing, and
does not establish attempt03's missing60s real-shell/150s window.

The proposal permits only this exact W plus matching monitor/disable/enable/
worker context and mandatory real USB/NCM recovery. Other warnings/errors still
stop. Default pure review rejects even this warning until explicitly opted in;
the runner refuses owner_adopted=false. Old verdicts/seals are retained.

A separate host observer defect required UDC unconfigured during physical
unplug. In391 valid Wi-Fi samples UDC stayed configured; ONLINE=0 spanned
source1491.10..1509.67 and host ADB tables were absent. The new host state
tracker uses supply+host evidence, conservative command-time brackets, unchanged
boot/PID/hash/binding and an elapsed observation clock. It never changes device
state. Host tests include this actual raw journal replay and the failed UDC case.
