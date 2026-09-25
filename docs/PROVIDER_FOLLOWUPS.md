# X710 / X910 follow-ups: the providers behind the GPU fix

Written while the post-fix stall series was running on hardware. Two findings from
reading the X910 port (`agcarbajo/ubuntu-galaxy-tab-s9-ultra`, revision
`4ff9d4b0ba1ae40e7605ad54c0ffe561c1e26a60`) and the pinned tree. Neither is acted
on this round; both are recorded because they explain symptoms that appeared
*after* the AOSS QMP + IPCC fix.

## 1. The X910 port patches `qcom-ipcc` for channel starvation

X910 carries `kernel/patches/ipcc-reserve-gts9u-runtime-channels.patch`. Its own
message:

> The SM-X910 port creates some DSP endpoints after IPCC has probed, because
> changing the boot DTB layout breaks Samsung ABL. Counting only clients present
> at probe reserves seven channels; ADSP, CDSP, SPSS and MPSS need eight when
> combined with SMP2P and AOSS. MPSS plus CDSP then fails with `-EBUSY` even
> though the requested client/signal pair is unused.
>
> On this board reserve at least the 48 channels used by Samsung's downstream
> IPCC driver. This changes allocation capacity only, not interrupt routing.

and the change:

```c
/* Late-created SM-X910 DSP endpoints are absent from the initial DT. */
if (of_machine_is_compatible("samsung,gts9uwifi"))
        ipcc->num_chans = max(ipcc->num_chans, 48);
```

**Why this matters to X710.** `qcom_ipcc_setup_mbox()` sizes the mailbox
controller by *counting* the `mboxes` phandles that point at it in the DT:

```c
ipcc->num_chans = 0;
for_each_node_with_property(client_dn, "mboxes") {
        if (!of_device_is_available(client_dn))
                continue;
        i = of_count_phandle_with_args(client_dn, "mboxes", "#mbox-cells");
        for (j = 0; j < i; j++) { ... if (!ret && curr_ph.np == controller_dn) ipcc->num_chans++; }
}
```

Every channel is then an identical `{client, signal}` slot whose identity is
resolved at xlate time, so **the capacity is a pure client count and carries no
notion of which pairs exist**. Any client that appears after IPCC probed — a
late-registered platform device, a module, or an endpoint created by another
driver — consumes capacity that was never counted, and once the slots are gone
the next request fails with `-EBUSY` regardless of whether the pair is in use.

X710 had `CONFIG_QCOM_IPCC` unset until this round, so this starvation could not
have been observed before. Whether X710 hits it is **not yet determined**; what is
determined is that the mitigation is board-specific in X910 (`of_machine_is_
compatible("samsung,gts9uwifi")`) and would need an equivalent condition for
`gts9wifi`, or a non-board-specific fix.

### What X710 actually shows instead

After the IPCC fix, the `smp2p-*` devices changed their deferred reason:

| | before the fix | after the fix |
|---|---|---|
| `smp2p-adsp/cdsp/modem` | `qcom_smp2p: IRQ index 0 not found` | `qcom_smp2p: unable to allocate local smp2p item` |

The *first* reason was the missing IPCC interrupt controller, and the fix cured
it. The *second* is a different failure, from a different provider:

```c
/* drivers/soc/qcom/smp2p.c */
ret = qcom_smem_alloc(pid, smem_id, sizeof(*out));
if (ret < 0 && ret != -EEXIST)
        return dev_err_probe(smp2p->dev, ret,
                             "unable to allocate local smp2p item\n");
```

So this is **SMEM allocation**, not IPCC. It is a genuine remaining defect on
X710 and is *not* in the GPU/AOSS/ACD chain, so it neither explains nor is
explained by the GPU fix. It should be investigated on its own terms: what the
SMEM heap looks like for each remote pid, and whether `smem@81d00000` is sized or
partitioned differently from X910.

Note the ordering question this raises: IPCC channel starvation and SMEM
allocation failure are two different ways for the same three `smp2p-*` devices to
fail, and X710 currently shows the second. If the first is also present it is
masked, because `qcom_smp2p` allocates its SMEM item before it requests its
mailbox.

## 2. Why `gmu@3d6a000` can never bind, and why that is upstream-correct

The post-fix burst still reports:

```
gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
```

`gmu@3d6a000` has `compatible = "qcom,adreno-gmu-740.1", "qcom,adreno-gmu"`, and
in the pinned tree there is **no platform driver matching `qcom,adreno-gmu`**. The
GMU is not a standalone device: `a6xx_gpu.c` looks it up by phandle
(`qcom,gmu = <&gmu>`) and drives it through the `adreno` driver as a sub-device.
The only `qcom,adreno-gmu` string in the tree is a *compatible check* for the
wrapper variant:

```c
/* drivers/gpu/drm/msm/adreno/a6xx_gpu.c */
adreno_gpu->gmu_is_wrapper = of_device_is_compatible(node, "qcom,adreno-gmu-wrapper");
```

So the GMU platform device exists, never binds, and is a permanent `sync_state`
blocker for every clock controller that lists it as a consumer.

**This is upstream behaviour, not an X710 bug**, and it is why fixing the GPU did
not remove the `sync_state` line. It is also the mechanism behind the upstream
series already recorded in `kernel/patches/`:

> `[PATCH RFT 0/5] drm/msm: Attach a driver to GMU` — *"With the introduction of
> sync_state in the genpd framework, any consumer device of GCC and GPUCC which
> is not bound to a driver will result in bootup warnings like `gcc-kaanapali
> 100000.clock-controller: sync_state() pending due to 3d37000.gmu` … To silence
> these warnings and also to have a proper state in driver core, attach a driver
> to the GMU."*

That series is patch 5/5 — the part X710 has **not** backported. X710 carries only
patch 1/5 (`0007`, the stateless cxpd link). So the remaining `sync_state` line is
exactly the symptom the rest of that series exists to fix, and patch 5/5 is now
the natural next backport **if** the post-fix stall series shows the burst still
matters.

### Consequence for the investigation

Fixing ACD did not remove the sync_state blockage, because the blockage is
structural (no GMU driver), not ACD-dependent. So:

* if the post-fix series is clean, the remaining `sync_state` line is cosmetic and
  can wait for the upstream series to land;
* if the post-fix series still stalls in the 13-14 s window, the `sync_state`
  blockage is the prime suspect and patch 5/5 becomes the next experiment.

Either way the decision is now data-driven on the series that is running, which is
why this note stops short of proposing the backport as a fix.

## 3. Not investigated, recorded only

* **SMEM allocation failure** (§1) — needs its own analysis of
  `qcom_smem_alloc` and the `smem@81d00000` carve-out.
* **`aux_bridge.aux_bridge: failed to acquire drm_bridge`** and
  **`qcom-pcie: cannot initialize host`** remain on the deferred list. Both were
  on it before this round and are outside the GPU chain.
* **`17d91000.cpufreq: qcom-cpufreq-hw: Failed to find icc paths`** likewise.
* **Slow boot to login**: `systemd-analyze` reports 1.303 s kernel + 5.458 s
  userspace, so kernel init and systemd are both fast; the extra wall-clock time
  is before `systemd-analyze`'s window (initramfs) or in panel bring-up, and was
  not measured this round.

## 4. `17d91000.cpufreq` was permanently deferred: a fifth provider, `epss_l3`

Found in round 19 while chasing why the wedge favours the big and prime CPU
clusters (`docs/CPU_WEDGE_EVIDENCE.md`). Round 20 resolved the mechanism. It is the
same shape as the four provider defects already fixed, and it is on the CPU path.

Measured on the device:

```
[   14.820796] platform 17d91000.cpufreq: deferred probe pending: qcom-cpufreq-hw: Failed to find icc paths
[   14.820860] gcc-sm8550 100000.clock-controller: sync_state() pending due to 17d91000.cpufreq
```

Two things at once:

* **the CPU frequency driver never probes.** `cpufreq@17d91000` is
  `qcom,sm8550-cpufreq-epss` with three frequency domains — `freq-domain0/1/2`, one
  per cluster — so *no* cluster has OS-controlled frequency or voltage scaling. All
  eight CPUs run at whatever OPP the bootloader left them at;
* **`gcc-sm8550` cannot finish `sync_state()` because of it.** Round 11 attributed
  that entirely to `3d6a000.gmu`; there is a second, independent blocker, and this
  one is not upstream-correct behaviour but a probe failure.

### 4.1 The answer: `of_icc_get_by_index(cpu_dev, 2)` has no provider

`qcom-cpufreq-hw` resolves the interconnect paths named by the **CPU** nodes before
it registers anything (`drivers/cpufreq/qcom-cpufreq-hw.c`, the
`dev_pm_opp_of_find_icc_paths(cpu_dev, NULL)` call), and `cpu0` names **three**
providers, not two:

```dts
interconnects = <&gem_noc  MASTER_APPSS_PROC    QCOM_ICC_TAG_ACTIVE_ONLY
                 &gem_noc  SLAVE_LLCC           QCOM_ICC_TAG_ACTIVE_ONLY>,
                <&mc_virt  MASTER_LLCC          QCOM_ICC_TAG_ACTIVE_ONLY
                 &mc_virt  SLAVE_EBI1           QCOM_ICC_TAG_ACTIVE_ONLY>,
                <&epss_l3 MASTER_EPSS_L3_APPS
                 &epss_l3  SLAVE_EPSS_L3_SHARED>;
```

| phandle target | node | driver | built in? |
|---|---|---|---|
| `gem_noc` | `1500000.interconnect` | `qnoc-sm8550` | yes, `CONFIG_INTERCONNECT_QCOM_SM8550=y` |
| `mc_virt` | `interconnect-1` (no unit address) | `qnoc-sm8550` | yes, same symbol |
| **`epss_l3`** | **`17d90000.interconnect`** | **`osm-l3`** | **no — `CONFIG_INTERCONNECT_QCOM_OSM_L3` was unset** |

`epss_l3` is `compatible = "qcom,sm8550-epss-l3", "qcom,epss-l3"` and is driven by
`drivers/interconnect/qcom/osm-l3.c`. Upstream `arch/arm64/configs/defconfig` sets
`CONFIG_INTERCONNECT_QCOM_OSM_L3=m`; this port builds no module tree, so `=m`
produces **no driver at all**. `17d90000.interconnect` therefore kept no driver,
`of_icc_get_provider()` found no registered `icc_provider` for path 2 and returned
`-EPROBE_DEFER`, and the probe deferred forever.

Why the earlier audit missed it, and this is the trap worth remembering. The
round-19 version of this section listed the providers that *were* bound and
concluded:

> every interconnect provider is bound: `1500000.interconnect` (gem_noc),
> `24100000.interconnect`, `1600000`/`1680000`/`16c0000`/`16e0000`/`1700000`/
> `1780000`/`320c0000`, and the two virtual ones as `interconnect-0` and
> `interconnect-1`, all on `qnoc-sm8550`.

That list is accurate and the conclusion is still wrong, for a structural reason:
`mc_virt` appears in it as `interconnect-1` **because it is a virtual provider with
no unit address**, so a provider *with* a driver can appear under a name that does
not match its label. And a provider with **no driver at all has no entry in such a
list** — it is absent, not misnamed. `17d90000.interconnect` was never going to show
up in an enumeration of bound providers. The check that would have caught it is
per-path, not per-provider: for each `interconnects` phandle of the consumer, does
that specific node have a driver built in?

### 4.2 Why only the outer message is visible

`dev_err_probe()` prints at `dev_err` only when the error is not `-EPROBE_DEFER`; for
`-EPROBE_DEFER` it stores the reason and logs at `dev_dbg`. So the inner
`_of_find_icc_paths: Unable to get path2` from `dev_pm_opp_of_find_icc_paths()` was
recorded at debug level and never appeared, and the outer
`dev_err_probe(dev, ret, "Failed to find icc paths")` became the deferred reason.
The absence of an inner message was therefore **not** evidence that
`_bandwidth_supported()` was the failing call — that inference in the round-19 note
was wrong, and the fix removes the ambiguity instead of instrumenting for it.

The other ruled-out candidate stays ruled out: the CPU OPP tables do carry
bandwidth — `cpu0_opp_table`'s first entry is
`opp-peak-kBps = <(300000 * 16) (547000 * 4) (307200 * 32)>`, and `sm8550.dtsi` has
94 `opp-peak-kBps` occurrences — so `_bandwidth_supported()` returns the positive
count and the code proceeds to `of_icc_get_by_index()`, whose failures are
`-EPROBE_DEFER` or `-ENODEV`, never the `-EINVAL` that would have been treated as an
empty table.

### 4.3 X910 found this first, on the same SoC

This is the first *identified, named* difference between the two ports on the CPU
path, and it is an X710 regression against X910 rather than a hardware difference.
The X910 port's `docs/development-notes.md`, section "There was no frequency scaling
at all", decodes the same property to the same three providers — `gem-noc` (0x7),
`mc-virt` (0x8), `epss-l3` (0x9, driver "**none**") — reports the same
`deferred probe pending: qcom-cpufreq-hw: Failed to find icc paths`, and gives the
same cause: the inherited config left `INTERCONNECT_QCOM_OSM_L3` at `=m` in a port
that installs no module tree. `kernel/config/config-ubuntu-desktop.fragment`
(their line 136) fixes it the same way, and their measured result with `=y` is
three policies — `307–2016` / `499–2803` / `595–2956 MHz` — `schedutil`, and a
kernel-built energy model.

Their two extra patches in this area (`cpufreq-recompute-software-boost-limit.patch`,
`arm-topology-use-boost-frequency-reference.patch`) are *not* needed for the probe
and are not carried here.

### 4.4 What changes, and what is not yet claimed

Enabled in `kernel/config/gts9wifi-mainline.fragment` as a one-line change. With
`=y` the expected consequences are:

* all eight CPUs get a cpufreq policy and a governor, so frequency and voltage are
  OS-controlled for the first time on this port;
* the L3 vote (`EPSS_REG_L3_VOTE`, `epss_l3_l3_vote`) is driven from the CPU OPP
  bandwidth values instead of being left at the bootloader's setting;
* `gcc-sm8550`'s `sync_state()` loses one of its two blockers.

**Not claimed:** that this removes the CPU wedge. The mechanism by which a
firmware-left fixed OPP could produce a CPU that stops answering NMIs is not
established, and the cluster asymmetry (big + prime wedge, little does not) is not
explained by a defect that affects all three clusters equally. This is a genuine
port defect fixed on its own merits; whether the wedge rate moves is a measurement,
and `docs/CPU_WEDGE_EVIDENCE.md` records the confound-free baseline it must be
compared against.

Also unverified until the first boot: `qcom_osm_l3_probe()` refuses to register if
the EPSS block is not enabled, with `error hardware not enabled` and `-ENODEV` from
a `readl()` of `REG_ENABLE` at `0x17d90000`. If ABL does not enable it, the provider
will still not register and the cpufreq deferral will persist — but the boot log will
then say so explicitly, which it never has.
