# test-214: the Galaxy prime OPP, verified on the tablet

Boot `a7b9ef68-9e67-4c84-a029-2919801a6894`, 2026-09-26. Raw capture in
`EVIDENCE.txt`.

## What was flashed

Two partitions, both of which carry the DTB. `init_boot` and `dtbo` were left
alone because nothing in this change reaches them.

| partition | sha256 | changed |
|---|---|---|
| `boot.img` | `71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d` | **yes** |
| `vendor_boot.img` | `49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9` | **yes** |
| `init_boot.img` | `1e98bea223cf8e6ee58a4a0e8378f9c916d02e3a9c4bde7aa431e5472cbe6175` | no |
| `dtbo.img` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` | no |

Both written images were read back from the partition and matched the staged
`SHA256SUMS` before the reboot. `Image.gz` inside `boot.img` is byte-identical to
what the tablet was already running (`f74728727418cc83`), so the kernel binary is
unchanged - this is a device-tree-only deployment.

## Before and after

| | before (`375b6442`) | after (`a7b9ef68`) |
|---|---|---|
| `Voltage update failed freq=3360000` | present at 0.381943 | **absent** |
| `failed to update OPP for freq=3360000` | present at 0.381963 | **absent** |
| `/proc/device-tree/opp-table-cpu7/opp-3360000000` | absent | **present** |
| `policy7/scaling_boost_frequencies` | empty | **`3360000`** |
| `policy7/scaling_available_frequencies` top | 2956800 | 2956800 (unchanged) |
| `policy7/cpuinfo_max_freq` | 2956800 | 2956800 (unchanged) |
| reboot to ssh over USB NCM | - | **36 s** |

All three success criteria from the brief are met: the compiled live DT carries
the OPP, the cpufreq policy registers the frequency, and the warning is gone.

## It registers as a boost frequency, which is the driver's own classification

`3360000` appears in `scaling_boost_frequencies` and not in
`scaling_available_frequencies`, and the non-boost ceiling stays at 2956800. That
is `qcom_cpufreq_hw_read_lut()` setting `CPUFREQ_BOOST_FREQ` for the last
`LUT_TURBO_IND` entry - the hardware LUT's own core-count field deciding what is
a boost bin. It is precisely the behaviour this change left alone: the board node
declares no `turbo-mode`, and the driver never reads one.

The global boost switch reads `0` and was not modified.

## The frequency was not observed, and that is not a failure

A brief single-thread load bound to cpu7, with the frequency unpinned, held
2956800; it did not reach 3360000. That is reported rather than hidden, because
the temptation is to read it as "the fix did not work".

It is not the criterion. The prime bin is a boost state, boost is off, and
thermal, current-limit and scheduler state can all legitimately keep a short test
below the top bin. Validation rests on the three criteria above, none of which
involves observing the clock.

Nothing was forced to make it appear: no `scaling_min_freq` write, no boost
enable, no governor change. Locking the frequency would have proved only that the
hardware accepts a value the DT now describes - it would not have tested the
thing that was wrong.

## No regressions

`console=tty0`, zero `/dev/ttyGS*`, gadget `ncm.usb0` only, `ssh.service` active,
0 failed units, 0 AF_VSOCK warnings, `usb0` at `169.254.42.1/16`, and the boot
record reaches `switch-root-synced` with `failure=none`. This evidence was
collected over the USB NCM link, which is the management path working.

## What this does not show

**It does not show the CPU wedge is fixed.** One clean boot says nothing about a
failure measured at 1 in 29 boots (`docs/CPU_WEDGE_EVIDENCE.md`), and the two are
separate problems with separate evidence. A causal claim would need a
pre-registered A/B experiment - see the "What this does NOT claim" section of
[docs/GALAXY_PRIME_OPP.md](../../../docs/GALAXY_PRIME_OPP.md).

What is established is narrow and complete: the board device tree now describes
the operating point the hardware LUT already advertised, the prime frequency is
registered with cpufreq, and the `Voltage update failed` warning is gone.
