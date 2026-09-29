# Test254 physical result: UPower fixed; Docker acceptance incomplete

The config-only Linux7.2-rc3 candidate was authorized by “刷入测试”, deployed
and is currently installed. Boot+181 matched modules read back correctly; four
other partitions/DTB/cmdline, all protected Test253 ADB/USB/SSH settings and139
repository hardware sources unchanged. DCC remains disabled. Exact Test252 and
Test249 rollback pairs retained. Original sealed offline build records remain
historical and unchanged; see BUILD_RESULTS.md for the96 reviewed config changes.

- Attempt01 stopped before any write on initial Windows Code43/absent rescue.
  Owner-confirmed manual reboot restored transports; cause remains unresolved.
- Attempt02 fresh registered deployment and151.6s responsive boot observation
  passed. UPower active with unchanged PrivateUsers=yes, no namespace/217 error,
  battery enumerated. Namespace/mqueue/cgroup2 prerequisites pass. Docker26.1.5
  installed, overlay2/cgroup2/seccomp/iptables-nft confirmed. First Docker Hub
  pull timed out; attempt stopped, no container/cable acceptance claimed.
- Attempt03 separately registered official ARM64 host-save/verified-load path
  passed actual hello-world/trixie/mqueue and CPU/memory/pids/cpuset checks.
  First ineffective I/O limit stopped the attempt. Fake-endpoint analysis shows
  the installed CLI already sends empty throttle arrays; kernel throttle flag
  and io.max exist. Client internal cause remains unproven. No software repair
  or follow-on physical/network tests were made.

Device stays on6c3dde80334e495589169a1e576c8024, ADB/NCM/Wi-Fi responsive, zero
new kernel fault/signature/failed unit; final telemetry Good,29.0°C,4.062V/71%.
UPower's two GUdev assertions remain unresolved. Rootless kernel prerequisites
are verified, rootless runtime/delegation not fully accepted. Docker I/O,
DNS/outbound/NAT/port publishing, optional namespace networks/IPVS and physical
ADB reconnect remain unaccepted. No Stage2/3 or ordinary extra charging test.

Read [attempt03 full result](attempt-03/RESULTS.md), [machine summary](PHYSICAL_SUMMARY.json)
and all raw per-command/journal/hash evidence. This bounded partial result is
not a failure-rate estimate, universal CPU repair or hardware-safety guarantee.

Final local `all --fail-on-skip` executes1148 retained tests in91.475s,
zero failures/errors/skips; raw structured report and command are in
attempt03/host-validation/ (relative to the Test254 root). Pre-deployment wrapper
also executed1148 in98.092s unittest time. No CI launched or main update.
