# Test254 attempt01: authorized deployment and bounded acceptance

The owner's new instruction is **“刷入测试”**. This separately authorizes
deployment and the future acceptance sequence recorded by the sealed offline
Test254 plan. The original root README/ARTIFACTS/summary/SHA256 remain historical
offline evidence, unchanged. This attempt does not promote Test252 or rewrite
any Test253 result. Registration must be committed and pushed to origin/test
before device writes. No GitHub Actions or main-branch update.

## Software and rollback

Use the already built Linux7.2-rc3 config-only candidate, not a new build.
Exact identities and scope are in registration.json and packaging/artifacts.json.
Only boot and its paired181 module files are deployed, through TWRP with the
Debian microSD root identified and machine-id verified. Retain the exact Test252
boot and module directory as a pair, plus the older Test249 backup. The module
swap has a host install/restore rehearsal with complete hashes. The original
build archive is unchanged; the deployment tar has verified release-relative
regular files, excluding host-only build/source symlinks.

Boot packaging uses the exact Test252 init_boot ramdisk, cmdline, bootconfig and
DTB. Generated vendor_boot/init_boot/dtbo/vbmeta images match the old bundle but
are **never flashed**. In particular the generated vbmeta differs from the
installed accepted vbmeta: preserve the installed partition. Check all five
partitions in Debian preflight, immediately before writes in TWRP and afterwards.
Keep Test253 daemon, launcher, units, restart guard, FunctionFS holder and
USB/NCM/SSH settings byte-identical. Preserve DCC off, Stage1 battery/current/
thermal policy and4.44V limit, CPU/radio/display/USB hardware configuration.
No Stage2 TCPM/PD/PPS or Stage3 SM5440, stress, fast-charge or power-path test.

## Fresh read-only preflight

Exact Test252 config/notes/five partitions/181 candidate+181 older rollback
files, DCC absence, failed units, profile, Bluetooth controller, battery telemetry
and protected Test253/USB/SSH settings are checked with raw complete journals.
Wi-Fi SSH works. Initial Windows ADB is empty and NCM is not connected; this is
an unresolved rescue prerequisite, not a kernel failure or permission to flash.
Wait for the operator's computer USB connection and require native shell,
source-bound Windows NCM SSH banner, authenticated NCM SSH and no Code43 before
entering recovery. No automatic host rescan, device daemon restart or USB change.

The first read-only observer incorrectly counted connected hci0:1 (DEVTYPE=link)
as a second controller. Its raw evidence remains in preflight-observer-rejected.
The successful capture counts only physical hciN hosts, still requiring the
single hci0 controller address, powered=yes and active services. This changes
host inventory parsing only; Bluetooth hardware/runtime is unchanged.

## Acceptance sequence

1. TWRP identity and all partition hashes; stage files and verify hashes; offline
   module swap; write boot only; read back boot and all preserved partitions;
   unmount microSD cleanly and issue one normal system boot.
2. Attribute the new boot uniquely using boot IDs and journal history. Verify
   candidate config/notes/boot/181 modules, Test252+Test249 rollback manifests,
   unchanged cmdline/DTB/protected userspace and DCC absence. Keep real responsive
   checks for150s, full kernel journals and ADB/NCM/Wi-Fi/battery evidence.
3. Activate/query the shipped UPower unit, retaining PrivateUsers=yes. Require
   active, battery enumeration and no new user-namespacing/217 error. Run unshare
   -Ur id as ms, check mqueue and cgroup2 cpu/cpuset/io/memory/pids controllers.
4. For the requested container acceptance, install Debian's docker.io, iptables,
   curl, uidmap and ipvsadm with --no-install-recommends from existing repositories
   if missing, preserving USB/SSH/adbd configuration. Record versions, apt output
   and package delta. This authorizes necessary ordinary Docker service/firewall
   setup and bounded image pulls, not a hardware or connectivity workaround.
   Stop on unexpected existing Docker storage/config/data rather than switching it.
5. Require rootful Docker cgroup2, overlay2 and seccomp; run hello-world, trixie
   uname/mqueue and a bounded256MiB/one-CPU/pids64/cpuset/io-control smoke test.
   Inspect actual controller files without sustained I/O or CPU stress.
6. Verify default Docker iptables backend through Debian iptables-nft, DNS,
   outbound IPv4, bridge/NAT and nginx publishing8080 with bounded curl. Record
   IPv6 family rules separately; no external IPv6 route is not a kernel failure.
   macvlan/ipvlan/vxlan/VLAN and minimal TCP/UDP RR IPVS can be exercised in one
   disposable namespace, never attached to real Wi-Fi/USB interfaces or host routes.
   Clean only test-owned containers/networks/namespaces; preserve pulled digests.
7. Check ordinary-user namespace/uidmap/subuid/subgid and cgroup delegation as
   rootless prerequisites. No rootless daemon, linger, service/sandbox/sysctl
   workaround or unsupported claim of full rootless runtime acceptance.
8. One operator-controlled computer USB disconnect>=20s/reconnect, preserving
   Wi-Fi and no separate charger/reboot. Use Test253's bounded60s recovery and
   actual150s ADB+NCM/Wi-Fi post-recovery observation; preserve initial transients
   and the contextual pre-enable DISABLE warning policy. Do not require the old
   PID834 after a legitimate new boot; bind the new daemon PID/hash before action.
9. Final same-boot full identity, modules/backups, UPower/failed units, protected
   settings, complete journals, ADB/NCM/Wi-Fi and healthy battery telemetry.

## Stops, evidence and limits

Stop at the first wrong identity, DCC presence, CPU non-response/panic/oops/RCU/
CSD/soft-lockup, unexplained reboot, Code43, unrecovered transport, unexplained
failed unit, incomplete evidence or abnormal battery telemetry. Preserve the
first event; no automatic diagnostic kernel/profile or retry. No preflight
baseline repair. If deployment partially fails or new boot is unsafe, use the
verified exact Test252 boot+module rollback pair through TWRP while preserving
Test253 userspace; document every recovery action and readback.

Known unchanged aux_bridge/regulator and existing bounded startup classifications
remain separate; the old UPower failure exemption does not apply after deployment.
Save full raw outputs/status/timing, journals JSON/text, boot attribution, hashes,
Docker versions/digests/rules/resources and operator responses. Report packaged,
deployed, booted and each acceptance stage separately, including untested parts.
This bounded test is not a failure-rate estimate, long-term reliability proof,
universal hardware-safety guarantee or evidence that all historical CPU stalls
shared the DCC cause.
