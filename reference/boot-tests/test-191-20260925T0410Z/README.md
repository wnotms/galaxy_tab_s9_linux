# test-191 candidate — the EPSS L3 provider built in (`epss_l3`)

Status: **bundle assembled and validated locally. NOT flashed.** No partition has
been written and no power action has been taken. See `candidate.txt` for hashes,
flash order, result matrix and rollback.

## Object of this round

`17d91000.cpufreq` has never probed on this port. `qcom-cpufreq-hw` resolves every
`interconnects` phandle on `cpu0` before it registers anything, and `cpu0` names
three providers. The first two bind to `qnoc-sm8550`; the third is `epss_l3`
(`17d90000.interconnect`), driven only by `osm-l3`, and
`CONFIG_INTERCONNECT_QCOM_OSM_L3` was **unset**. Upstream asks for it as `=m`
(`arch/arm64/configs/defconfig`), and this port installs no module tree, so `=m`
would have built nothing either.

With no provider for path 2, `of_icc_get_provider()` returns `-EPROBE_DEFER`,
`qcom_cpufreq_hw_driver_probe()` returns it up the stack through
`dev_err_probe(dev, ret, "Failed to find icc paths")`, and the device sits on the
deferred list forever. Measured:

```
platform 17d91000.cpufreq: deferred probe pending: qcom-cpufreq-hw: Failed to find icc paths
gcc-sm8550 100000.clock-controller: sync_state() pending due to 17d91000.cpufreq
```

So **no cluster has OS-controlled frequency or voltage scaling**, the L3 vote is
whatever ABL left, and `gcc`'s `sync_state()` has a second, independent blocker on
top of the GMU one.

The X910 port hit exactly this on the same silicon, diagnosed it, and fixed it the
same way. Their `docs/development-notes.md` decodes the same phandles
(`gem-noc` 0x7, `mc-virt` 0x8, `epss-l3` 0x9, driver "none") and reports three
policies, `schedutil` and an energy model once it is built in. Full account:
`docs/PROVIDER_FOLLOWUPS.md` §4 and `docs/X710_X910_GPU_RPMH_DIFF.md` §11.

## Why this is a clean one-variable test

The bundle's `vendor_boot.img`, `init_boot.img`, `dtbo.img` and `vbmeta.img` are
**byte-identical** to the images the tablet is running now
(`out/boot-bundle-test187-baseline/`). Only `boot.img` differs, and the only
source difference in it is the one config symbol:

```
out/boot-bundle-test187-baseline/boot.img   bf6a02bb…  (flashed 2026-09-25T00:46:07Z)
out/boot-bundle-test191-osm-l3/boot.img     78ec7a35…  (this bundle)
```

This matters because `CONFIG_INTERCONNECT_QCOM_OSM_L3` is the *only* delta, and
because the flashed kernel was built with `GTS9_RPMH_DEBUG=1` (diagnostic `0021`
compiled in, inert unless `gts9_rpmh_debug=1` is on the command line). This bundle
is built with the **same** flag so that the diagnostic does not become a second
variable. Verified: both build logs apply the same seven default-queue patches,
and this one applies `diagnostic 0021-gts9-rpmh-timeout-state-dump.patch` too.

## What this test can and cannot show

Two questions, deliberately separated.

### Q1 — does the provider bind? (definite, one boot, cheap)

`verify-osm-l3.sh` answers this in a single probe. Success is all of:

| check | expected |
|---|---|
| `/sys/bus/platform/devices/17d90000.interconnect/driver` | exists |
| `/sys/bus/platform/devices/17d91000.cpufreq/driver` | exists |
| `/sys/devices/system/cpu/cpufreq/policy*` | **3** |
| `scaling_governor` on each policy | `schedutil` |
| `dmesg \| grep -c "Failed to find icc paths"` | `0` |
| `deferred` count in `/sys/kernel/debug/devices_deferred` | **2**, down from 3 |
| `dmesg \| grep -c "sync_state() pending due to 17d91000.cpufreq"` | `0` |

**Pre-agreed failure reading.** If `dmesg` says
`osm-l3 17d90000.interconnect: error hardware not enabled`, then ABL does not
enable the EPSS block and `qcom_osm_l3_probe()` refused with `-ENODEV`. The
provider then still does not register, the cpufreq deferral persists, and that is
not a failed experiment — it is a definite answer that the fix has to be a
resource handed over from the bootloader path, and it has never been visible
before because nothing ever probed the node.

Equally, if `17d90000.interconnect` binds but `17d91000.cpufreq` still does not,
the deferral is *not* path 2 and the next step is `initcall_debug` on the probe
rather than more config guessing.

### Q2 — does the wedge rate change? (statistical, tens of cycles)

`wedge-rate.sh` measures it with the confound-free marker from
`docs/CPU_WEDGE_EVIDENCE.md`: the unanswered NMI, not any watchdog message.

```
pre-fix   10 of 46 boots  (21.7%)
post-fix   1 of 29 boots  ( 3.4%)     Fisher p = 0.043
```

A rate of 3.4% needs **~85 clean cycles** to distinguish "0%" from "3.4%" at all,
and 20–30 cycles can only detect a large change. That is stated here in advance so
a short series cannot be read as a fix.

**Do not read Q2's result as the object of the round.** The port defect in Q1 is
real and worth fixing on its own terms. The most likely outcome given 1/29 post-fix
is that this is a real bug fix that **does not change the wedge rate**. Nothing yet
connects a firmware-left fixed OPP to a CPU that stops answering NMIs, and the
defect removes frequency scaling from all three clusters equally while the wedge
lands on big and prime.

## Files

| file | purpose |
|---|---|
| `candidate.txt` | image hashes, bundle delta, flash order, result matrix, rollback |
| `verify-osm-l3.sh` | Q1: one read-only console probe, prints PASS/FAIL per criterion |
| `wedge-rate.sh` | Q2: presence-driven warm-reboot series; per-run output dir, NMI is a stop condition, and a survived cycle is cut short |
| `flash-profile.sh` | verified flash of `boot` + `vendor_boot` only, with backup and readback |

## Cycle cost, measured

test-190's hunt ran 18 cycles of the same shape, so the cost is known rather than
guessed:

| | |
|---|---|
| tablet away per cycle (USB presence, gone -> back) | **19.4 s** mean, 18.6-20.2 s |
| cycle period | **208.9 s** |

So **91% of every cycle was the fixed capture window, not the reboot.** The window
is not waiting for the boot: a wedged boot reaches multi-user and *then* freezes, so
it looks healthy for its first ten seconds. It is waiting for the panic, which
`softlockup_panic=1` prints about 180 s after the wedge.

`wedge-rate.sh` therefore ends a cycle as soon as the boot has **provably survived**:
a shell that answers a command past `GTS9_EARLY_MIN_UPTIME` (45 s, well past the
5.4-14.3 s in which every recorded wedge struck) with **zero** wedge markers in the
capture. If the shell does not answer, or any marker is present, the full window is
kept - which is exactly the case the window exists for. That turns a clean cycle
from ~209 s into ~45-50 s. `GTS9_EARLY_EXIT=0` restores the old behaviour.

It is safe to cut the watcher short because `console-watch.ps1` writes each line
with `Add-Content`, which flushes per call, so nothing already captured is lost.

## Honest limits

* The kernel **builds**, the symbol is in the resolved config
  (`out/kernel-gts9wifi/config`, `CONFIG_INTERCONNECT_QCOM_OSM_L3=y`), and
  `osm-l3` is in `modules.builtin`. That is `compiled` and `packaged`, **not**
  `booted`. Whether the provider binds is a physical-boot question.
* A warm reboot is not a cold boot, and `wedge-rate.sh` never calls it one.
* `wedge-rate.sh` has been dry-run and syntax-checked on the host only; its first
  real cycle is part of the test.
