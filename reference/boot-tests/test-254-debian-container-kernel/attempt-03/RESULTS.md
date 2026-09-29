# Test254 attempt03: stopped on ineffective CLI I/O limit

Registration084d4142 pushed before image loading or container workloads. Same
boot6c3dde80334e495589169a1e576c8024, kernel/config/notes/181 modules and protected
Test253 userspace unchanged. No flash/rebuild/reboot/daemon restart in this attempt.

Four official ARM64 image archives independently bind Docker Hub index/platform/
config digests and every layer diff_id. Host save SHA matches transfer SHA;
loaded Docker26 image IDs/architecture match the verified configs. Source JSON,
archive hashes, load outputs and actual IDs are preserved. Device direct Docker
Hub pull remains failed/unaccepted; no proxy/DNS/daemon mirror workaround.

Rootful hello-world, trixie uname, container mqueue,256MiB/oneCPU/pids64 run pass.
Actual cpu.max=`100000 100000`, memory.max=268435456, pids.max=64, cpuset.cpus=0
and effective0. Docker26.1.5 uses systemd cgroup2, overlay2 and builtin seccomp.
Complete kernel journals and same-boot battery/failed-unit checks accompany each
command, with no new fault/signature. No sustained CPU/I/O stress.

**First non-clean: io.max empty.** The resource test requested1MiB/s read/write
limits on the microSD without exposing any block device to the container.
Docker HostConfig.BlkioDeviceReadBps/WriteBps were empty and io.max had no rule.
Stop immediately; no DNS/outbound/NAT/publishing, virtual-network/IPVS or physical
cable acceptance followed. The single sleep-only test container was stopped and
removed; no test container or namespace remains.

Read-only incident analysis proves CONFIG_BLK_DEV_THROTTLING=y, BLK_CGROUP=y
and the io controller/file exist. An isolated fake Unix HTTP endpoint captured
the installed CLI's create request: despite explicit --device-read-bps and
--device-write-bps, both API arrays were already empty. The fake endpoint never
contacted the real daemon or created a real container. This localizes a missing
CLI/API input before the kernel, but does not establish the client's internal
cause or prove kernel throttling failure. Do not change kernel/service/drivers
to conceal the failed test. Full raw request and helper remain in io-incident/.

[Upstream CLI26 resource assembly](https://github.com/docker/cli/blob/v26.1.5/cli/command/container/opts.go)
and [Moby26 resource validation](https://github.com/moby/moby/blob/v26.1.5/daemon/daemon_unix.go)
are only auxiliary code references, not substitutes for this installed Debian
binary's captured request. Runtime/client fixes are a separate task outside
the config-only candidate; registered first-non-clean result remains stopped.

Final full identity: five partition hashes, exact config/notes,181 current+181
Test252+181 Test249 files, DCC absence and all protected ADB/USB/SSH hashes pass.
All139 protected repository sources unchanged. Same boot at1430.74s; full1171-row
kernel journal has zero CPU/panic/RCU/CSD/soft-lockup counts/suspects. ADB, source-
bound NCM SSH and Wi-Fi work, no Code43/failed unit. Battery Good,71%,29.0°C,
4.062V, ordinary SDP input500mA. No charge policy/DTB/SM5714/SM5440/TCPM/PD/PPS/
DWC3/FunctionFS/adbd/CPU OPP or diagnostic change, no Stage2/3.

UPower remains active with PrivateUsers=yes, battery enumerated and no namespace
error; two prior GUdev assertions remain separate/unresolved. Ordinary user
unshare succeeds and uidmap/subuid/subgid exist. User cgroup delegation is
recorded (subtree cpu/memory/pids); rootless daemon and its full resource/network
behavior are not accepted. No linger/delegation/service workaround.

This is bounded **partial acceptance**, not full Docker/I/O/network/reconnect,
rootless runtime, cold/power-path or long-term/hardware-safety proof. New candidate
remains installed with verified Test252 rollback available; no unsafe kernel
condition requiring rollback was detected. Do not automatically resume skipped
physical stages. Analyze the CLI input issue in a separately scoped task.

Final local `all --fail-on-skip` executes1148 retained tests in91.475s,
zero failures/errors/skips; raw structured report and command are in
attempt03/host-validation/ (relative to the Test254 root). Pre-deployment wrapper
also executed1148 in98.092s unittest time. No CI launched or main update.
