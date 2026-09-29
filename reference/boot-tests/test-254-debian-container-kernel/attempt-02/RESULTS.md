# Test254 attempt02: deployed; container acceptance stopped on registry access

Registration369ebe3a pushed before writes. Exact candidate boot+181 modules
deployed in TWRP; four other partitions, DTB, cmdline and all protected Test253
USB/ADB/SSH files unchanged. Exact Test252+Test249 rollback module sets retained.
Temporary misc BCB requested TWRP and was cleared. Original source/config/charge
policy unchanged; no Stage2/3. See DEPLOYMENT.md and complete readback captures.

Uniquely attributed boot6c3dde80334e495589169a1e576c8024, Wi-Fi10.191.121.241,
config c80d3c66… and notes7bbb0dc3… match the sealed candidate. Real151.6s
ADB/NCM/Wi-Fi responsiveness passed. Full pre/post-stop journals have zero
CPU/panic/RCU/CSD/soft-lockup fault signatures, no suspects or failed units.
Battery Good, post-stop29.1°C/SOC72%; no universal safety/reliability claim.

UPower starts with unchanged shipped PrivateUsers=yes and enumerates the SM5714
battery and USB supply. No namespace setup/217 error. Two separate GLib/GUdev
assertions remain visible; their cause is not established and no hardware/udev
workaround was applied. User ms successfully unshare -Ur id; mqueue mounted;
cgroup2 cpu/cpuset/io/memory/pids available. An auxiliary combined command exited1
because a Debian-only unprivileged_userns_clone sysctl is absent upstream;
required unshare independently returned0, with full raw stderr preserved.

Debian Docker26.1.5, containerd/runc, iptables-nft, uidmap and ipvsadm installed
from existing repositories with no recommendations;11 new packages, no upgrades.
Docker CLI is a separate necessary package. Daemon active, systemd cgroup v2,
overlay2 and builtin seccomp; default nft-translated iptables route. apt retained
a backports timeout/cache warning; no repository/proxy/config change.

First hello-world pull failed at registry-1.docker.io awaiting HTTPS headers.
Series stopped at that first failure: no container workload or physical cable
cycle was performed. Diagnostic IPv4 curl also could not connect; host endpoint
returns expected HTTP401. DNS outputs differ, but precise DNS/network cause
is not proven. This is not evidence of a kernel or CPU failure. Post-stop full
identity/181+181+181 modules/protected files/transports/kernel health still pass.

The stopped result is preserved. A separately registered same-boot continuation
can use official host-downloaded ARM64 images with source manifest/config/layer
digests, tar transfer and load, preserving all device configuration. It must
never relabel device registry pulling as passed, retry/rewrite this attempt or
claim rootless runtime/delegation, cold/power-path or long-term acceptance.
