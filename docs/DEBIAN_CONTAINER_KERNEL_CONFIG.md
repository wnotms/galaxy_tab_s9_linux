# Debian UPower / OCI kernel configuration audit

This change prepares an **unflashed** Linux7.2-rc3 candidate. Installed state
remains Test252 SM5714 Stage1 plus Test253 userspace adbd reconnect repair.
It does not promote that candidate to Test249 production, retroactively pass
Test252, or start SM5714 Stage2/SM5440 Stage3.

The Test252 `ARTIFACTS.json` config identity is
`410e4fe28f6fcc25950aba0029f8cda310b39ddbf1653f3eaa7b334e62f3b722`.
Its archived resolved config and Test253 attempt04 final embedded config match
byte for byte. Audit the actual resolution, not the fragment alone. Full
[build results](../reference/boot-tests/test-254-debian-container-kernel/BUILD_RESULTS.md),
[config table](../reference/boot-tests/test-254-debian-container-kernel/validation/config-audit.json),
[exact delta](../reference/boot-tests/test-254-debian-container-kernel/validation/expected-delta.json)
and [complete textual diff](../reference/boot-tests/test-254-debian-container-kernel/validation/config.diff)
record every resolved change and its category.

## UPower and existing prerequisites

The captured Debian service requests `PrivateUsers=yes` but Test252 has
USER_NS=n. In pinned Linux `include/linux/user_namespace.h`, the no-USER_NS
`unshare_userns()` stub rejects CLONE_NEWUSER with EINVAL, matching the saved
`Failed to set up user namespacing: Invalid argument`/217/USER failure.
USER_NS=y compiles the real implementation while preserving the shipped
sandbox. No PrivateUsers=no, service edit or namespace-limit workaround is
introduced. This removes the observed missing kernel prerequisite; UPower
active state and battery enumeration still require device acceptance.
[systemd's PrivateUsers description](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.exec.xml)
defines the service user namespace and identity mapping.

Test252 already has namespaces except USER_NS, cgroups including memory/pids/
cpuset/BPF/device accounting, seccomp/filter, keys, overlayfs, tmpfs, ext4 ACL/
security, veth/bridge/bridge-netfilter, conntrack/NAT/masquerade and x_tables
addrtype/conntrack/mark/NAT/REDIRECT. These remain built in. It has NF_TABLES=y
but lacks the actual IPv4/IPv6 families and NAT/compat expressions. Legacy
IP_NF_IPTABLES/IP6_NF_IPTABLES=y alone are also insufficient on this pin.

## Explicit new enabled switches and their reasons

All switches below resolve to **y**. Names omit the CONFIG_ prefix in this
table only. Exact old values (including absent rather than n) are in JSON.

| Switches | Reason / category |
| --- | --- |
| USER_NS | UPower PrivateUsers and rootless Docker/userns-remap prerequisite. |
| POSIX_MQUEUE | OCI /dev/mqueue filesystem and IPC operations. |
| CFS_BANDWIDTH | Docker --cpus/CPU quota; FAIR_GROUP_SCHED is already y. |
| BLK_DEV_THROTTLING | Block IO rate control/io.max; BLK_CGROUP is already y. |
| CGROUP_PERF | Requested optional cgroup perf integration; PERF_EVENTS already y. |
| NET_CLS_CGROUP | Requested legacy cgroup packet classifier compatibility; not a new cgroup-v2 controller or net_prio enablement. |
| MACVLAN | Common Docker macvlan virtual network driver. |
| IPVLAN | Common Docker ipvlan virtual network driver. |
| VXLAN | Docker overlay virtual network transport; existing UDP tunnel/GRO prerequisites retained. |
| BRIDGE_VLAN_FILTERING | VLAN-aware bridge/overlay capability; bridge and VLAN_8021Q already y. |
| NF_TABLES_INET | Mixed IPv4/IPv6 nftables family; selects both family providers. |
| NF_TABLES_IPV4, NF_TABLES_IPV6 | Explicit family providers for iptables-nft and ip6tables-nft. |
| NFT_CT | nftables conntrack expressions. |
| NFT_NAT | nftables SNAT/DNAT, including default port publishing. |
| NFT_MASQ | nftables masquerade. |
| NFT_REDIR | nftables redirect support; NF_NAT_REDIRECT already y. |
| NFT_COMPAT | Existing x_tables match/target extensions over nftables, required for compatibility userspace rules. |
| NFT_FIB_IPV4, NFT_FIB_IPV6 | IPv4/IPv6 route/FIB expressions checked by current Moby nftables audit. |
| NETFILTER_XTABLES_LEGACY | Explicit Linux7.2 evaluator parent for the requested legacy fallback; compatible with current non-RT baseline. |
| IP_NF_IPTABLES_LEGACY, IP6_NF_IPTABLES_LEGACY | IPv4/IPv6 old sockopt/table evaluators; the generic iptables symbols alone do not provide these. |
| IP_NF_FILTER, IP6_NF_FILTER | Legacy filter tables. |
| IP_NF_MANGLE, IP6_NF_MANGLE | Legacy mangle tables. |
| IP_NF_RAW, IP6_NF_RAW | Legacy raw tables, including current default Docker direct-access filtering. |
| IP_NF_NAT, IP6_NF_NAT | Legacy NAT tables/port mapping; retain existing x_tables NAT targets. |
| IP_NF_TARGET_MASQUERADE, IP6_NF_TARGET_MASQUERADE | Legacy compatibility selectors for the existing masquerade target. |
| IP_VS | Requested minimal Swarm/service load-balancing kernel infrastructure. |
| IP_VS_NFCT | IPVS/conntrack integration. |
| IP_VS_PROTO_TCP, IP_VS_PROTO_UDP | Ordinary transport protocols for IPVS. |
| IP_VS_RR | Single round-robin scheduler, no broad scheduler enablement. |
| NETFILTER_XT_MATCH_IPVS | x_tables IPVS match used by Swarm-related networking. |

The six automatically selected/default dependencies are also y:
CGROUP_NET_CLASSID (NET_CLS_CGROUP), GROUP_SCHED_BANDWIDTH (CFS_BANDWIDTH),
POSIX_MQUEUE_SYSCTL (mqueue plus existing SYSCTL), hidden NFT_FIB (family
providers), IPVLAN_L3S (default under IPVLAN+NETFILTER) and NET_L3_MASTER_DEV
(IPVLAN_L3S select). All96 symbolic changes are accounted for:39 explicit
enabled switches,6 dependencies,48 newly visible disabled declarations and3
default IPVS integer declarations. Default TAB_BITS=12 sizes the enabled IPVS
table; SH_TAB_BITS=8 and MH_TAB_INDEX=12 do not enable the disabled SH/MH
schedulers. Changes of absent to n are recorded, not hidden or called active
features. The raw text diff also preserves comments/menu layout changes.

## Linux7.2 dependencies and Moby correspondence

The current official [Moby check-config script](https://raw.githubusercontent.com/moby/moby/a4c5b2be6f69f86fe7b13eb4822676f8d273cf8b/contrib/check-config.sh)
is pinned by URL, commit and SHA256 in
[Moby provenance](../reference/boot-tests/test-254-debian-container-kernel/validation/moby-provenance.json).
The content matches the current repository tree fetched for this audit.
Its Linux7 Generally Necessary section has33 unique config checks: Test252
misses12; the candidate misses none. The script calls USER_NS, seccomp and
several resource/nftables features Optional; this project's explicit goal
requires the chosen subset regardless of those labels. Obsolete pre-5.x
NF_NAT_IPV4/NF_NAT_NEEDED and pre-4.8 DEVPTS flags are not Linux7 requirements.

NETFILTER_XTABLES_LEGACY depends on x_tables and !PREEMPT_RT. Each new
IP{,6}_NF_IPTABLES_LEGACY depends on that parent; filter/mangle/raw/NAT require
the corresponding legacy evaluator. In contrast NFT_COMPAT uses x_tables
extensions without the legacy evaluator. NF_TABLES_INET requires IPV6 and
selects both families. NFT_NAT needs conntrack and a family and selects NAT;
MASQ/REDIR need conntrack+NAT. NFT_FIB is hidden and selected by the requested
family FIB implementations. These exact pinned dependencies and real
olddefconfig resolution are retained in
[Kconfig declarations](../reference/boot-tests/test-254-debian-container-kernel/validation/kconfig-dependencies.json).

Debian iptables-nft is a userspace compatibility route. It is distinct from
Docker's native nftables firewall backend; this task changes neither the
backend nor runtime forwarding sysctls. Docker ordinarily creates firewall
rules for bridge/NAT/port publishing and requires forwarding. Runtime rules/
sysctls, daemon setup and controller delegation remain future acceptance.
[Docker iptables documentation](https://docs.docker.com/engine/network/firewall-iptables/)
and [native nftables documentation](https://docs.docker.com/engine/network/firewall-nftables/)
describe the distinction.

Opening these menus initially exposed additional stock requests. Explicitly
disable ARP tables, security tables, NETMAP, unused legacy REJECT/REDIRECT
aliases, IPv6 RPFILTER and CT/DSCP/NOTRACK/TPROXY/TRACE targets. The existing
NETFILTER_XT_TARGET_REDIRECT=y and NF_NAT_REDIRECT=y still implement REDIRECT;
an optional missing IP_NF_TARGET_REDIRECT alias is not evidence that actual
REDIRECT support disappeared. `DOCKER-CT` is a chain using the existing
conntrack match and ACCEPT; it does not by itself require the CT target.
This is verified in [current pinned Moby network.go](https://raw.githubusercontent.com/moby/moby/366ebd37ab54dfebe670278e9ba8ac14e2ca2061/daemon/libnetwork/drivers/bridge/internal/iptabler/network.go).

Unmodified Moby auxiliary script execution against the candidate config exits0
(baseline exits1). Its cgroup/sysctl/keys/device/tool probes inspect the **host
WSL**, not the tablet; only the static config comparison is candidate evidence.
The complete outputs explicitly label this limitation and retain all optional
missing flags. Do not call it device Docker acceptance or require optional
features to be green.

## Preserved optional scope and risk

AppArmor=n, CHECKPOINT_RESTORE=n, SCTP=n and CGROUP_HUGETLB remains absent.
SELinux is **already y in Test252 and remains y**; it was not newly enabled.
Existing CGROUP_NET_PRIO=y also remains unchanged. IPVS stays TCP/UDP/RR;
other schedulers, debug, SCTP/ESP/AH and IPv6 IPVS remain disabled. Basic IPv6
nftables/NAT is enabled separately. No CRIU, LSM policy bring-up, encrypted
Swarm overlay project, Kubernetes/CNI or eBPF specialization is introduced.

Rootful namespaces, overlay2, cgroup/seccomp/mqueue, virtual networks, IPv4/
IPv6 firewall/NAT and requested resource controls now have their kernel
prerequisites. Rootless still needs ordinary-user namespace permission/limits,
uidmap, subordinate UID/GID ranges, networking helpers, runtime setup and
cgroup delegation. USER_NS=y is necessary, not a fully installed rootless
Docker service. See [Docker rootless prerequisites](https://docs.docker.com/engine/security/rootless/).
Kernel overlay support includes rootless overlay on this version; on Docker29+
a fresh install may use the containerd image store rather than displaying the
classic overlay2 driver. Preserve existing data/config and handle that runtime
choice separately. See [Docker storage selection](https://docs.docker.com/engine/storage/drivers/select-storage-driver/).

No DTS/provider/OPP/USB/charge/radio config change is permitted by the exact
delta review. Protected-source hashes and unchanged DTB support this boundary;
they do not prove that a new kernel cannot regress at runtime. New generic
kernel paths increase code/attack surface, USER_NS permits user namespaces and
network/resource features allocate state when used. Container load can consume
CPU/RAM/IO and produce heat even though no electrical policy is changed.
Test254 must use small bounded workloads, preserve rescue connectivity while
Docker installs firewall rules, and stop on faults or abnormal telemetry.
There is no device exposure during this offline-only task, no claim of
guaranteed safety and no change to4.44V/current/thermal charging controls.

The [Test254 future plan](../reference/boot-tests/test-254-debian-container-kernel/README.md)
orders exact identity/rescue, UPower, ordinary-user unshare, mqueue, cgroup2,
Docker/limits, network/port publishing and battery/ADB/NCM/Wi-Fi regression.
No hardware step in it has been executed.
