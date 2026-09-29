# Offline UPower / OCI candidate build

The configuration-only candidate compiles and its paired module archive is
prepared. **No device command, flash, reboot, daemon/rootfs change or physical
acceptance was performed.** Installed Test252 Stage1/Test253 status remains
unchanged. No boot bundle was packaged; no Stage2/3 work started.

## Audit and exact configuration identity

The Test252 manifest-pinned config and Test253 attempt04 final embedded config
are byte-identical, SHA256
`410e4fe28f6fcc25950aba0029f8cda310b39ddbf1653f3eaa7b334e62f3b722`.
Candidate config SHA256 is
`c80d3c661cca3588fc85c93ba3402356bd99b7e4fe85674773230914fb8e6b71`.
The compiled Image.gz embedded config equals both the saved config and actual
olddefconfig output byte for byte. Linux remains7.2-rc3 at
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa` with unchanged toolchain config.

[config-verdict.json](validation/config-verdict.json) passes the actual
85-symbol built-in prerequisite gate, two retained battery/provider checks,
DCC-off check and non-goal stock-request suppression. Full baseline comparison
has **96 symbol changes, zero unexpected changes and zero missing expected
changes**:39 explicit new y,6 selected/default dependency y,48 newly visible
n declarations and3 default IPVS integer declarations. Every active addition
belongs to the requested container features or reviewed dependencies.
See [complete config.diff](validation/config.diff),
[expected-delta.json](validation/expected-delta.json),
[config-audit.json](validation/config-audit.json) and
[per-switch explanation](../../../docs/DEBIAN_CONTAINER_KERNEL_CONFIG.md).

USER_NS=y fixes the missing kernel implementation used by UPower
PrivateUsers=yes; no systemd workaround was added. It does not establish that
the still-installed old kernel now runs UPower. Kernel support for rootful/
rootless namespaces, overlay2, cgroup2/seccomp/mqueue, virtual networks,
IPv4/IPv6 iptables-nft/NAT and legacy fallback, common limits and minimal
TCP/UDP/RR IPVS is compiled. Runtime Docker setup, forwarding, delegation,
rootless uidmap/subuid/subgid and real container operation remain unverified.

AppArmor=n, checkpoint=n, SCTP=n and hugetlb cgroup absent remain unchanged.
SELinux and CGROUP_NET_PRIO were already y and stay y. No broad IPVS schedulers
or IPv6 IPVS were added. Do not call Moby optional missing entries failures or
enable unrelated features merely for green output.

## Build and binary checks

The normal `JOBS=8 USE_CCACHE=1 BUILD_MODULES=1 ./scripts/build-kernel.sh`
pipeline was run with independent KERNEL_WORKTREE/KERNEL_BUILD_DIR/
KERNEL_OUT_DIR overrides listed in [README](README.md). Exit0, ARM64/LLVM,
kernel Image.gz plus all modules, no source-profile or hardware-patch change.
Raw [kernel-build.log](validation/kernel-build.log),
[timing](validation/build-timing.json),
[kernel SHA256SUMS](validation/kernel-SHA256SUMS) and
[ARTIFACTS](ARTIFACTS.json) are retained. Time to last artifact was about870s;
the later observed-completion timestamp includes collection delay.

The four existing stock/fragment-resolution warning classes remain:
BASE_SMALL value0, two panic bool values and repeated GENI console assignment.
They were already recorded by Test252; final resolution has no unexpected
change. Draft builds were stopped during scope review, before acceptance,
when opening the parents exposed unrelated stock controls. Only the final
scoped configuration/build is the candidate recorded here.

Image.gz SHA256:
`69abcdbf67960bd2a46d1c457e1807120c5a92e3e525ae36a70733b5b33e0823`,
size22,109,618 bytes. Kernel release remains`7.2.0-rc3-gts9wifi-dirty`.
Kernel notes SHA256:
`7bbb0dc382d4b89b2d6c5b79c1f02805ef0afc8459fe6b48a423d9f26744332b`.
No hvc_dcc path symbols exist in vmlinux; create_user_ns, unshare_userns and
sm5714_probe are present. [Symbol verdict](validation/symbol-verdict.json)
and [kernel notes](validation/kernel-notes.txt) retain the checks.

**DTS source unchanged; compiled DTB byte-identical to Test252**:
`eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0`.
CONFIG_HVC_DCC=n, BATTERY_SM5714=y and QCOM_SPMI_ADC5_GEN3=y remain unchanged.
The protected [139-file source manifest](validation/protected-sources.json)
was rechecked unchanged, including all kernel hardware sources/patches/DTS,
boot, rootfs and userspace adbd inputs. No CPU OPP/cpufreq/cpuidle, watchdog/
panic, GPU/display/radio, DWC3/PHY/gadget/FunctionFS, SM5714 charge/current/
4.44V/thermal, SM5440/TCPM/PD/PPS or Test253 helper/unit logic changed.

The existing `.work/linux-mainline` checkout carried historical overlay edits
at task start. It was left untouched; all audited Kconfig bytes equal pinned
git objects. An independent worktree applied the unchanged normal patch queue.
No claim is made that the pre-existing checkout was clean.

## Paired modules and retained baseline

Candidate modules have the same181-file set/167 .ko as Test252, with new full
[module hashes](validation/module-hashes.json) and
[module SHA256SUMS](validation/module-SHA256SUMS). `depmod -n -e -E
Module.symvers` exits0 with [empty stderr](validation/depmod.stderr).
The archive at `out/kernel-container-candidate/modules-container-candidate.tar.gz`
has SHA256
`4ef282f778f01acf4b69b15fd1926dc615319160970d4b3f41704ae2051d4bfe`.
Every one of its181 file payloads matches that new paired manifest.
Build/source host symlinks are excluded. Kernel/module/archive binaries remain
ignored local outputs, not committed images.

Original Test252 Image.gz/config/DTB/release and all181 original modules were
rehashed against its existing manifest and remain unchanged. Same release
string/file set does **not** imply ABI or signature identity: future deployment
must pair the newly built kernel and its entire matched module directory.
No module was installed on the tablet and no partition was written.

## Moby comparison and local regression

The unmodified current official Moby check-config content is pinned at script
commit`a4c5b2be6f69f86fe7b13eb4822676f8d273cf8b`, SHA256
`fda4343e9b50c47896653ca774ccbe9614bfcdb60f080d2b6277baf27efc0a71`;
its content matches the current tree`366ebd37ab54dfebe670278e9ba8ac14e2ca2061`.
For Linux7, all33 Generally Necessary unique config checks are enabled;
Test252 had12 missing. [Comparison](validation/moby-check-config.json) and
[provenance](validation/moby-provenance.json) retain the list and exact source.
Auxiliary script execution exits0 for the candidate and1 for Test252.
Raw outputs are labelled **host WSL runtime**, not tablet cgroup/sysctl/Docker
evidence. [Kconfig dependencies](validation/kconfig-dependencies.json) explain
Linux7.2 legacy evaluator parents versus nftables/x_tables compatibility.

New24 focused tests pass. Required wrapper/changed/full results and exact
commands are retained in `validation/host-tests.json` and corresponding raw
logs/reports; all existing tests remain present with their original assertions.

| Command | Executed result | Command wall time |
| --- | --- | --- |
| `bash scripts/check-stall-offline.sh --changed --base HEAD~1` | 1148 pass; zero failures/errors/skips; shell syntax included | 94.068s |
| `python3 scripts/run-host-tests.py changed --report out/host-tests/container-config-changed.json` | 1148 pass; zero failures/errors/skips | 80.118s |
| `python3 scripts/run-host-tests.py all --fail-on-skip --report out/host-tests/container-config-all.json` | 1148 pass; zero failures/errors/skips | 78.342s |

Each selection contains1043 core+18 artifact+87 archive tests. Changed runs use
the existing conservative full fallback for config/build/unknown dependencies;
these are real executed checks, not zero-selection passes. Durations are separate
runs in the host environment below, not a test-speed benchmark. Full suite
runner time is78.236s; unittest time is78.165s. The exact JSON takes precedence
over rounded prose.

No test routing map was changed, no test deleted/skipped/weakened, and no CI
workflow was started or awaited.

The first ordinary host run was interrupted as incomplete: an existing panel
fixture's no-argument global sync waited more than236s in WSL
request_wait_answer. Real `sync -f` completed on Linux repo ext4 and /tmp tmpfs.
An initial environment-staging guard wrongly assumed they shared one filesystem;
that short rerun was also interrupted, corrected and preserved as incomplete.
Final runs use the retained [host syncfs wrapper](validation/host-syncfs-wrapper.sh):
no-argument sync actually flushes **both** Linux filesystems containing the
test records, while explicit-file sync argv is unchanged. It does not use an
exit0 no-op. The wrapper changes only the temporary host PATH; production
helpers/rootfs and every test/selector/assertion are untouched. See
[stop record](validation/host-global-sync-stop.json), raw incomplete logs and
syncfs invocation log. This environment qualification is part of the local
test result, not a workaround applied to Debian. An early focused development
run before build completion lacked the candidate output; its artifact test
failed then. Only the final24-test run is reported as passing.

## Safety and next step

Only generic kernel capabilities and required host validation/docs were changed.
Identical DTB/protected sources and exact allowed config delta support the
hardware boundary but cannot guarantee that any new kernel is regression-free.
New user namespaces/network/resource paths add code and attack surface;
container load can consume CPU/RAM/IO and cause heat. Electrical charge
policy/limits were not changed. No new software was exposed to the device.

Future **separately authorized Test254** must freshly verify baseline/rollback,
package and verify boot with unchanged ramdisk/cmdline, use paired modules,
then follow README A–H: identity/rescue, active UPower without namespace error,
ordinary-user unshare, mqueue, cgroup2 controllers, overlay2/seccomp Docker,
small CPU/memory/pids/io checks, DNS/outbound/bridge/NAT/port publishing, and
battery/charging/ADB physical reconnect/NCM/Wi-Fi/kernel-fault regression.
Stop on the first mismatch/fault/incomplete evidence. Do not flash generated
vbmeta or other partitions, silently change Docker storage/firewall modes, or
start Stage2/3. There is no current device result or pending automatic flash.
