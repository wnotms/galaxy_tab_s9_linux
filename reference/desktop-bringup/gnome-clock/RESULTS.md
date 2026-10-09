# Debian desktop time repaired on accepted Test370 boot

Owner clock issue confirmed: dateSep30 versus trusted host/UTC clockOct9, while
Asia/Shanghai timezone was already correct. No network time client installed.
Preserve all original Test370 source timestamps; kernel/input acceptance had
already completed before this independent wall-clock correction.

Boot-bound bootstrap from trusted host epoch, then standard Debian
systemd-timesyncd257.13-1~deb13u1 installed/enabled. APT: one new package, zero
upgrades/removals; existing systemd/libsystemd-shared exact version preserved.
The daemon contacted95.111.202.5:123 (0.debian.pool.ntp.org) and journal records
initial clock synchronization. Final timedatectl show reports NTP=yes and
NTPSynchronized=yes, Shanghai timezone; device epoch lies within the host
command's time interval. Standard persistent clock-state file exists.

An initial timedatectl timesync-status formatting query timed out after8s;
its original error/command is preserved. Independent basic properties, full
timesyncd journal, enabled/active status and clock-state verification succeeded.
Same boot0cdf, GNOME/palm/SSH/adbd active, no failed units. USB is unplugged by
owner; physical USB rescue/reconnect remains a separate scope. No reboot, RTC
register operation, kernel/DT/modules/PD/charger/sensor change. Hardware RTC
still reports an old value; no offline/reboot RTC correctness claim.

Future GNOME package list includes standard timesyncd. No custom time daemon
added. Host/build/full tests executed:false for this standard package/data/docs
change; runtime evidence, not a zero-test regression pass, proves current clock.
USB lifecycle and actual sensor discovery/rotation/fullport remain pending.
