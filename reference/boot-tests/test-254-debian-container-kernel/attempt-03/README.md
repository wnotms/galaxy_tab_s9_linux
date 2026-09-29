# Test254 attempt03: same-boot container and reconnect acceptance

The owner's authorization remains “刷入测试”. Attempt02 is stopped and sealed
at its first device registry pull failure. Independent read-only analysis found
device HTTPS cannot connect, whereas host official registry responds HTTP401;
precise network/DNS cause is unproven. No kernel/USB/adbd/proxy/DNS setting repair.

This independent test uses already installed Test254 boot6c3dde80… and Debian
Docker26.1.5, without any flash/rebuild/reboot/service restart. Fresh exact config/
notes/five partitions/181 current+181 Test252+181 Test249 files and Test253
protected settings plus ADB/source-bound NCM/Wi-Fi pass. Commit/push this
registration before loading images or starting workloads/cable cycle.

Four official docker.io/library ARM64 images are downloaded on the host, exported
with [Docker platform-specific save](https://docs.docker.com/reference/cli/docker/image/save/),
and independently checked against official registry index/platform/config digests
and every layer diff_id. Archive bytes/SHA and expected Docker26 config IDs are
in registration.json and host-images metadata. Load by verified tar transfer;
require matching IDs/architecture afterwards and use --pull=never. Device direct
registry pulling is **not accepted** by this path. No registry mirror or daemon
configuration change. Host Docker29 store ID differs from legacy config ID; raw
source manifests independently bind exported configs/layers, not an ID guess.

Run the remaining attempt02 registered OCI/resource/network checks on exactly
these images: hello-world, trixie uname/mqueue,256MiB/oneCPU/pids64/cpuset0,
metadata-only1MiB/s read/write io.max on microSD (no block device exposed/no I/O
stress), DNS/IPv4 outbound, bridge/NAT/nginx8080. Use an isolated disposable
namespace for macvlan/ipvlan/vxlan/bridge VLAN/nft-v4-v6/legacy/IPVS RR checks;
never attach it to physical Wi-Fi/USB or alter host routes. Record ordinary-user
unshare/uidmap/subuid/subgid and actual delegation, with rootless runtime untested.
Keep all prior stop conditions, known-warning policy and hardware exclusions.

One physical computer USB unplug>=20s/replug only after workloads pass. Reuse
Test253's actual10s conservative sampled-offline bound,60s native+NCM recovery,
150s ADB/NCM/Wi-Fi responsiveness and single contextual DISABLE warning5s+1s
policy. Host observer pins this new boot's actual daemon PID/hash (not historical
PID834), leaving the public Test253 observer and tests unchanged. Keep Wi-Fi,
no charger/reboot/reset/server rescan. Full final acceptance follows; preserve
first anomaly and stop. No Stage2/3, charge experiment or long-term guarantee.

Attempt03 acceptance never rewrites attempt01/02 or counts external registry
access as passed. Report all scopes and UPower's separate retained GUdev warnings.
