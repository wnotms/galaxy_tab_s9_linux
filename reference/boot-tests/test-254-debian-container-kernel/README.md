# Test254 plan: Debian userspace/container kernel feature enablement

Status: **offline candidate preparation only; deployment not authorized or
performed**. Linux remains7.2-rc3 at
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`. The installed device remains the
Test252 Stage1 candidate with the separately accepted Test253 userspace daemon.
This record does not promote Test252 or alter any historical stopped result.

## Purpose and boundary

Enable the missing kernel prerequisites for shipped UPower `PrivateUsers=yes`
and ordinary rootful/rootless OCI containers, including overlay2, cgroup v2,
seccomp, mqueue, common virtual networks, NAT/port publishing and minimal IPVS.
Only the mainline config fragment and necessary host gates/tests/docs change.
Do not change kernel source patches, DTS, battery charge policy,4.44V/current/
thermal settings, SM5440/TCPM/PD/PPS, CPU OPP/cpufreq/cpuidle, DCC repair,
GPU/display/radio, DWC3/PHY/gadget/FunctionFS, adbd or rootfs USB/NCM/SSH.
No systemd sandbox workaround. No Stage2/3 or special charging experiment.

The baseline config is the Test252 manifest-pinned config
`410e4fe28f6fcc25950aba0029f8cda310b39ddbf1653f3eaa7b334e62f3b722`, also
byte-identical to Test253 attempt04 final embedded config. Hardware/device
commands in this document are a future plan, not executed results.

## Build and offline review

Use the normal build script in independent directories, preserving all Test252
and rollback outputs:

```sh
JOBS=8 USE_CCACHE=1 BUILD_MODULES=1 \
  KERNEL_WORKTREE="$PWD/.work/build/linux-src-container" \
  KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-container" \
  KERNEL_OUT_DIR="$PWD/out/kernel-container-candidate" \
  ./scripts/build-kernel.sh
```

The resolved gate runs after olddefconfig and before compilation. Retain the
entire config diff, exact reviewed delta, embedded config, image/DTB/release
hashes, notes, paired module manifest, protected-source hashes and local tests.
Verify the DTB matches Test252 byte for byte. Keep the original181-file Test252
module directory; a newly built kernel must use its own matched modules even
when the release string is unchanged. Do not run the old Test252 gate against
this intentionally different candidate or weaken that historical gate.

## Future deployment prerequisite

After separate explicit authorization, register the physical attempt and push
it before any write. First perform fresh read-only preflight: exact Test252
boot/config/notes/five partition identities, all181 paired modules and rollback
files, DCC absence, battery telemetry, Test253 daemon/service/helper hashes and
ADB/NCM/Wi-Fi SSH. Preserve the Test253 accepted daemon and units.

Package and verify a candidate boot using the unchanged existing ramdisk and
cmdline. The candidate kernel/modules are prepared offline; boot partition
packaging and device acceptance are not asserted here. Deploy only the verified
boot and matched module set after authorization, never generated vbmeta or
other partitions. Preserve init_boot/vendor_boot/dtbo/vbmeta. Stop on any
identity mismatch; do not repair the installed baseline automatically.
Rollback, if separately needed during that future attempt, pairs the retained
Test252 boot with its exact original181 files and preserves Test253 userspace.
No rollback is needed now because this task writes nothing to the device.

## Future acceptance order

**A. Identity and rescue first.** Save boot ID, uptime, uname, cmdline, boot and
other partition hashes, embedded config, kernel notes and full matched module
manifest. Require DCC=n, no /dev/hvc0 or hvc0 getty, BATTERY_SM5714=y,
QCOM_SPMI_ADC5_GEN3=y, normal battery/USB supplies, exact Test253 daemon/helper
identity and working ADB/NCM/Wi-Fi SSH. Observe a responsive boot for at least
150s. Keep complete kernel journal JSON and text; attribute by boot ID.

**B. UPower.** Preserve the shipped unit and `PrivateUsers=yes`:

```sh
systemctl status upower.service --no-pager
journalctl -u upower.service -b --no-pager
systemctl show upower.service -p PrivateUsers -p ActiveState -p Result
upower -e
```

Require active service, battery enumeration, no new217/USER or `Failed to set
up user namespacing`. A config prerequisite is not a claim of device success.

**C–E. User namespace, mqueue, cgroup v2.** Run the user-namespace command as an
ordinary login user and capture exit status; root-only success is insufficient
for rootless prerequisites:

```sh
unshare -Ur id
grep mqueue /proc/filesystems
stat -fc %T /sys/fs/cgroup
cat /sys/fs/cgroup/cgroup.controllers
```

Require successful unshare, mqueue, cgroup2fs and cpu/cpuset/io/memory/pids.
Read namespace limits, mount options and controller delegation if a gate
fails; do not change sysctls or sandbox policy to manufacture a pass.

**F. Rootful Docker.** Record package/runtime versions and image digests before
testing. Image pulls and daemon installation/configuration require the future
attempt's authorized scope; none are performed in this offline task.

```sh
docker info
docker run --rm hello-world
docker run --rm debian:trixie-slim uname -a
docker run --rm debian:trixie-slim sh -c 'mount | grep mqueue'
docker run --rm --memory=256m --cpus=1 --pids-limit=64 \
  debian:trixie-slim sh -c 'echo container-ok'
```

Require cgroup version2, overlay2 and seccomp. Modern Docker fresh installs may
default to the containerd image store; record the actual storage mode, and do
not interpret its default as a missing kernel overlay capability. If classic
overlay2 acceptance needs a daemon/storage switch, propose it separately rather
than silently changing existing Docker data/config. Inspect actual cpu.max,
memory.max, pids.max and cpuset delegation for a bounded test container.
For io, inspect io.max after a small explicitly bounded test; do not stress or
benchmark UFS/microSD. Kernel controller support does not prove delegation.

**G. Network.** Record `iptables --version`, alternatives and read-only nft/
iptables rules. Require the Debian iptables-nft route with Docker's default
iptables backend; do not silently switch to Docker's distinct native nftables
backend. Test Docker DNS, IPv4 outbound HTTP, bridge attachment, NAT and port
publishing. Keep NCM/Wi-Fi rescue working while Docker installs firewall rules:

```sh
docker run --rm debian:trixie-slim getent hosts deb.debian.org
docker run -d --rm --name gts9-nginx -p 8080:80 nginx:alpine
curl --fail --max-time 10 http://127.0.0.1:8080/
docker stop gts9-nginx
```

Use a reviewed small client image with curl/wget for outbound access; don't
assume trixie-slim includes those tools. Verify IPv6 family/NAT rules separately
if no external IPv6 route exists; lack of upstream IPv6 is not a kernel fault.
macvlan/ipvlan/vxlan and minimal IPVS are kernel prerequisites here, not a claim
that Wi-Fi permits arbitrary external L2 addresses or that a Swarm cluster is
configured. Any isolated network/IPVS smoke test must preserve parent links
and host routes; do not run Swarm init or alter the physical network implicitly.

**Rootless prerequisite check.** Verify ordinary-user unshare, uidmap binaries,
subuid/subgid ranges and cgroup delegation. A separate rootless smoke run can
then record `docker info` rootless/seccomp/cgroup2 and bounded hello-world/
resource/network checks in its own context. This task does not install a
rootless daemon, disable rootful Docker, enable linger or change delegation.

**H. Regression.** Recheck battery voltage/current/temperature/SOC telemetry,
ordinary charging policy unchanged, Test253 physical ADB reconnect using its
adopted bounded observer, NCM, Wi-Fi and full boot-attributed kernel journal.
Charge/reconnect actions require the future physical attempt's explicit scope
and real operator readiness. No load/thermal/fast-charge or Stage2/3 test.

## Stop conditions and results

Stop at the first identity/config/module mismatch, DCC presence, CPU
non-response, panic/oops/RCU/CSD/soft-lockup, unexplained reboot, USB Code43,
unrecovered ADB+SSH loss, new unexplained failed unit, abnormal battery
telemetry/charging or incomplete evidence. Preserve raw logs and analyze before
further testing. Known unchanged aux_bridge/regulator warnings remain separate.
UPower must now pass; the earlier namespace-error exemption is not applicable.

Save complete stdout/stderr/exit status for each step, before/after boot IDs,
all identities, raw journal JSON and text, systemd failures, container digests,
rules, resource files and transport/battery evidence in a new attempt directory.
A future RESULTS/summary must separate compiled, packaged, deployed, booted and
physically verified, with bounded observations and no universal reliability or
hardware-safety claim. Current [BUILD_RESULTS](BUILD_RESULTS.md) records only
offline evidence.
