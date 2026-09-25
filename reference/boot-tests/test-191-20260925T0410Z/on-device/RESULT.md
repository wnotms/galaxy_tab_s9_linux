# test-191 on hardware: the fifth provider defect is fixed, verified over ssh

Flashed 2026-09-25T06:31:12Z, verified on boot `7a389436-f61f-4d24-9427-f52cf5430d4c`.

`boot` and `vendor_boot` were written and **both read back and verified**; nothing
else was touched. The backup confirms the delta is what was claimed:
`boot-before-osm-l3.img` = `bf6a02bbe19e9561be2bae6d691cbaad0c3871ed4efc3878b8f689f2af00bd3e`,
the byte-for-byte test-187-baseline kernel that was on the tablet.

## Every pre-agreed criterion, measured

| check | expected | measured |
|---|---|---|
| `17d90000.interconnect` has a driver | bound | **1, bound** |
| `17d91000.cpufreq` has a driver | bound | **1, bound** |
| cpufreq policies | 3 | **3** |
| governor | `schedutil` | **`schedutil` on all three** |
| `Failed to find icc paths` | 0 | **0** |
| `osm-l3 … error hardware not enabled` | 0 | **0** — ABL *does* enable the EPSS block |
| `sync_state() pending due to 17d91000.cpufreq` | 0 | **0** |
| deferred devices | 3 → 2 | **2** |

The three policies, one per cluster, and the frequency ranges are **exactly** what
the X910 port measured after making the same one-line change:

```
policy0 cpus=0,1,2  gov=schedutil min=307200 max=2016000 cur=1555200
policy3 cpus=3,4,5,6 gov=schedutil min=499200 max=2803200 cur=1785600
policy7 cpus=7      gov=schedutil min=595200 max=2956800 cur=2956800
```

307–2016 / 499–2803 / 595–2956 MHz against X910's `307–2016` / `499–2803` /
`595–2956`. Two independent ports on the same SoC, same numbers.

The `cur=` readings differ per cluster, which is the point: the governor is actively
scaling, where before this boot all eight cores ran at one firmware-left OPP with no
governor at all.

The deferred list is down to two, and the cpu one is gone from it:

```
aux_bridge.aux_bridge.0   aux_bridge: failed to acquire drm_bridge
1c00000.pcie              qcom-pcie: cannot initialize host
```

## What this establishes, and what it does not

**Establishes**: the round-19 finding was right about the symptom and wrong about
the mechanism, and the round-20 mechanism is confirmed. `cpu0` names three
interconnect providers; the third, `epss_l3`, had no driver because
`CONFIG_INTERCONNECT_QCOM_OSM_L3` was unset in a port that builds no module tree.
With it built in, the provider binds, `qcom-cpufreq-hw` probes, and all three
clusters get OS-controlled frequency and voltage for the first time on this port.

**Does not establish**: that this changes the stall. The wedge is a separate
question, and the rate series that would answer it has not been run on this kernel.
`docs/CPU_WEDGE_EVIDENCE.md` records the baseline it must be compared against.

## Two honest differences from X910

* **no energy model.** X910 reports the kernel building one; here every
  `policy*/energy_model` is absent. Recorded as measured rather than explained -
  it is a real difference between the two ports and it is not part of this fix;
* **a slow first boot.** The operator reports the boot log on screen for a long
  time before the login screen appeared, and console probes returned nothing for
  ~2.5 minutes. It recovered on its own and did not reboot. That is recorded in
  `SLOW-FIRST-BOOT.md` with what could and could not be measured, because it may be
  the stall rather than a slow boot.

## Harness note: the console was at a login prompt, not a shell

`verify-osm-l3.sh` failed on its first run, and the reason was not the kernel: the
single 1963-character command was echoed back in fragments and never executed,
because **ttyGS0 was showing a Debian login banner instead of the autologin root
shell**. Every console probe after that boot returned nothing for the same reason.
The verification above was done over ssh instead.

That is a defect in the harness's assumptions, not in the fix, and it is recorded so
the next person does not read "the console does not answer" as a stall.
