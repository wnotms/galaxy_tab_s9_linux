# Test 227 — a CPU wedge **with `cpuidle.off=1` active**: the PSCI-idle direction is downgraded

**Result: the plan's pre-registered first-row outcome.** A genuine CPU-level wedge
occurred twice on a boot carrying `cpuidle.off=1`, with the cpuidle framework
provably absent and no `PSCI CPU_SUSPEND` issued at all.

By `docs/CPU_IDLE_WEDGE_PLAN.md` §5.2 that row reads, and was written before the
data existed:

> **any `k ≥ 1` with CPU-level evidence** → **`full cpuidle framework is not
> necessary for the wedge`** → **stop the cpuidle direction immediately**; do not
> run profiles 2/3; go to §7.

That is what this document records. Nothing here is a fix, and nothing here is
`solved`.

## 1. What was flashed, and the one-partition delta

`cpuidle-off` — the baseline command line plus exactly one token. Write scope was
**`vendor_boot` only**, over USB-NCM ssh (the tablet was running mainline Linux,
not TWRP; adb saw no device and the harness's COM17/COM19 are absent on this
host). Full transcript: `FLASH-TRANSCRIPT.md`.

| partition | before | after |
|---|---|---|
| `boot` | `71e194a5…` | `71e194a5…` **unchanged** |
| `vendor_boot` | `49ae21b3…` | **`1245bb39…`** ← the only change |
| `init_boot` | `1a8c7148…` | `1a8c7148…` **unchanged** |
| `dtbo` | `c17418be…` | `c17418be…` **unchanged** |
| `vbmeta` | — | **not written** |

Backed up first, verified byte-exact: `dd if=/dev/sda24 of=/tmp/vb-before.img`
produced `49ae21b3…` on the device, and the pulled copy re-hashed to the same
value on the host. The token was read **out of the image on the tablet** before
the write, not assumed from the build:

```
$ grep -ao "console=tty0[^\x00]*cpuidle[^\x00]*" /tmp/vb-candidate.img | head -1
console=tty0 msm.separate_gpu_kms=1 cpuidle.off=1 panic=1...
```

## 2. The arming gate passed, and it is load-bearing

This is what makes the result usable: the profile was proven active **on every
wedged boot**, not just at flash time.

| check | result |
|---|---|
| `cpuidle.off=1` on `/proc/cmdline` | present on all three boots |
| `/sys/devices/system/cpu/cpuidle` | **ABSENT** — the framework never registered |
| `cat .../cpuidle/current_driver` | `No such file or directory` |
| `cpuidle: using governor` on the boot | **0** occurrences |
| `/sys/kernel/debug/psci` | `OSI is supported`, `Extended StateID format is used` |

The governor line's absence is the strong half: `cpuidle_register_governor()` is
reached only through the cpuidle core and returns `-ENODEV` when the framework is
off, so with `cpuidle.off=1` that line **cannot** be printed. It is present in 64
archived boot logs today and was absent from all three of these.

## 3. The genpd counters: no deep idle state was ever entered

Read on the running (post-wedge) boot:

```
power-domain-cluster  S0  Usage 0  Rejected 0
                      S1  Usage 0  Rejected 0
power-domain-cpu0     S0  Usage 1
power-domain-cpu4     S0  Usage 1
power-domain-cpu7     S0  Usage 1
```

**Every cluster state shows zero usage and zero rejections.** The cluster domain
was never entered at any level — not `0x41000044`, not `0x4100c344`. The
per-CPU domains show a single transition each, consistent with the CPUs parking
once at idle through WFI.

This is a stronger statement than "the profile was armed": it says the entire
PSCI suspend path — CPU-local *and* cluster — was never exercised, and the wedge
happened anyway.

## 4. The wedge

The tablet wedged twice in a row and recovered itself both times through the
profile's own chain (`softlockup_panic=1` → `panic=10` → reboot). The operator
observed: stuck, auto-reboot, stuck again, auto-reboot, then the login screen.

| boot | id | journal span | gap to next boot | reading |
|---|---|---|---|---|
| normal | `125c2350` | 01:21:14 → 01:23:07 | 16 s | my `systemctl reboot` |
| **wedged** | `658adbd0` | 01:23:23 → 01:23:30 | **54 s** | journal stops at **+7 s** |
| **wedged** | `9e5fca86` | 01:24:24 → 01:24:30 | **55 s** | journal stops at **+6 s** |
| healthy | `b0122aca` | 01:25:25 → … | — | login screen seen |

The ~54 s gaps are the panic chain: wedge at ~7 s, soft lockup detected 26 s
later, `panic=10`, then ~16 s to boot again — `7 + 26 + 10 + 16 = 59 s` against a
measured 54–55 s. A normal cycle is 16 s. **Both short boots wedged and both were
recovered by the watchdog**, which is why the operator saw two freezes and then a
login screen rather than a dead tablet.

### The pstore record

The surviving ramoops console belongs to the second of them (`9e5fca86`, journal
stopping at +6 s with ~54 s of silence after it). It carries the documented
signature, and the onset matches the established window:

```
[   28.659200][    C6] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[   28.659227][    C6] rcu: 	4-...!: (0 ticks this GP) idle=1244/1/0x4000000000000000 softirq=1391/1391 fqs=3
[   28.659251][    C6] rcu: 	(detected by 6, t=5256 jiffies, g=709, q=1727 ncpus=8)
[   35.114152][    C1] watchdog: BUG: soft lockup - CPU#1 stuck for 26s! [kworker/u32:9:179]
[   35.114886][    C1] Kernel panic - not syncing: softlockup: hung tasks
[   36.717932][    C1] SMP: failed to stop secondary CPUs 4,6-7
```

The victim chain is **byte-for-byte the project's documented canary**:

```
smp_call_function_many_cond+0x3ec/0x514
 kick_all_cpus_sync+0x48/0x7c
  arch_jump_label_transform_apply+0x14/0x24
   __jump_label_update+0x118/0x13c
    jump_label_update+0xe4/0x110
     static_key_enable_cpuslocked+0x6c/0xb4
      static_key_enable+0x24/0x3c
       toggle_allocation_gate+0x58/0x14c     <- Workqueue: events_unbound
```

**Onset, from this wedge's own two timers:**

| timer | report | subtract | onset |
|---|---|---|---|
| RCU stall | 28.659 s | 5256 jiffies ÷ 250 Hz = 21.02 s | **7.63 s** |
| soft lockup | 35.114 s | 26 s | 9.11 s |

The RCU figure lands in the established **~6.5–7.8 s** band (prior wedges:
7.13 / 7.74 / 7.29 / 7.58 s). The soft-lockup figure is the less reliable of the
two, as `docs/NEXT_STALL_DEBUG_PLAN.md` already notes.

Note the `softirq=1391/1391` field — **unchanged across the stall**, which is
`Documentation/RCU/stallwarn.rst`'s documented indicator of a CPU spinning with
interrupts disabled rather than one executing normally.

## 5. What this establishes, and what it does not

**Establishes**, by the plan's own pre-registered rule:

* **The full cpuidle framework is `not necessary` for the wedge.** The framework
  was provably absent, no `PSCI CPU_SUSPEND` was issued, no cluster state was
  ever entered (zero usage, zero rejections), and the wedge still occurred at the
  documented onset with the documented signature and the documented victim chain.
* **The PSCI-idle hypothesis is `downgraded`** as a necessary condition. It is not
  refuted as a *contributor* — this profile removes the idle entry, not the
  domain topology (`psci` genpd still registers, and OSI mode is still enabled) —
  but "some CPU entered deep idle and did not return" cannot be the mechanism
  when no deep idle state was entered at all.
* **Profiles 2 and 3 (`no-llcc-off`, `no-cluster-idle`) need not be run.** The
  plan says so explicitly for this row, and their whole subject — the cluster
  suspend parameter — is something firmware never received here.

**Does not establish:**

* **Any cause.** The wedge is now known to survive the removal of the entire
  cpuidle framework, which narrows the space but names nothing in it.
* **That `cpuidle.off=1` is harmful.** This was one round on one boot; the
  pre-existing rate is ~3.4–6.9 % and a single wedge (here two, on consecutive
  boots) does not show the profile made things worse. It shows the profile does
  not remove the failure.
* **Anything about a fix.** No workaround is proposed. `docs/CPU_IDLE_WEDGE_PLAN.md`
  §7 is the next branch, and it is now the active one.

## 6. Where this sends the investigation — §7 of the plan

The idle direction is out, so the plan's §7 list becomes the working order:

1. **IRQ delivery** — `/proc/interrupts` and `/proc/softirqs` deltas across a
   wedge, and the `ipi:*` tracepoints, to ask whether the target CPU's GIC
   redistributor is still routing.
2. **CPU hotplug state** — `online` vs `present` for the wedged CPU at the moment
   of failure.
3. **`SError`** — note `CONFIG_ARM64_PSEUDO_NMI=n`, so an SError is an ordinary
   IRQ on this build.
4. **arch timer / `local-timer-stop`**.
5. **RCU callback / IPI delivery**.
6. **firmware-level CPU state** — the one thing Linux cannot see.

Two things make that branch more attackable than it was:

* **`CONFIG_CSD_LOCK_WAIT_DEBUG` is not set, and is now the first build item.**
  It is the only facility in mainline that prints *which IPI handler the stuck
  CPU was executing* — precisely the question. The canary here
  (`toggle_allocation_gate → smp_call_function_many_cond`) is an
  `smp_call_function*()` caller, so this instrument is pointed exactly at the
  observed victim. It belongs in a separate diagnostic profile, not bolted onto
  an ablation.
* **The victim is CPU 4, a big-core CPU, and it fits the documented pattern
  rather than departing from it.** Reading the three CPUs in the record
  correctly matters, because two of them are not victims:

  | CPU | core | role in the record |
  |---|---|---|
  | **4** | A715 (big) | **the stalled CPU** — `rcu: 4-...!`, and the `!` marks it as having failed to answer the backtrace IPI |
  | 6 | A710 (big) | the **detector** — `(detected by 6, ...)` |
  | 1 | A510 (little) | the **reporter** — its soft-lockup stack is `toggle_allocation_gate → smp_call_function_many_cond`, i.e. the canary spinning while it waits for CPU 4 |

  An earlier draft of this section called CPU 1 a victim. It is not: it is the
  `events_unbound` worker that noticed, and its stack is the same
  `toggle_allocation_gate → kick_all_cpus_sync → smp_call_function_many_cond`
  chain that `docs/CPU_WEDGE_EVIDENCE.md` and
  `docs/STALL_FIRST_EVENT_ORDERING.md` already identify as **the canary, not the
  cause**. Reporting it as a victim would have re-introduced exactly the mistake
  this project corrected three rounds ago.

  So the stalled CPU is big-cluster, consistent with the historical
  concentration on big/prime (13 of 14 pairs), and `SMP: failed to stop
  secondary CPUs 4,6-7` is a second, independent statement that the wedge
  involved 4, 6 and 7 — again big and prime.

## 7. Evidence index

| file | what |
|---|---|
| `PRE-WRITE-STATE.txt` | device identity and all five partition hashes before the write |
| `FLASH-TRANSCRIPT.md` | backup → hash → write → read-back, with the token read on-device |
| `evidence/pstore-raw.txt` | the surviving ramoops console, the full wedge record |
| `evidence/wedged-boot-minus1-klog.txt` | journal of `9e5fca86` (1 064 lines) |
| `evidence/wedged-boot-minus2-klog.txt` | journal of `658adbd0` (1 062 lines) |
| `evidence/boot-list.txt` | journald's boot table, the timing evidence |
| `evidence/arming-during-wedges.txt` | the gate re-checked on each wedged boot |
| `evidence/genpd-with-cpuidle-off.txt` | cluster and CPU domain counters |
| `evidence/both-wedges.txt` | side-by-side of the two short boots |

**Not captured, and marked absent rather than implied:** `/proc/interrupts` and
`/proc/softirqs` snapshots from inside a wedged boot — a wedged kernel cannot be
read, and no trace was armed. That is the §7 instrument list's first item, and it
is the reason the next round should arm a trace *before* it reboots.

## 8. Recovery and current device state

The tablet is healthy and was never stranded: the profile's own watchdog chain
recovered both wedges, and the third boot reached the login screen.

To revert to the pre-test state, restore the single partition that changed:

```sh
# vendor_boot: 1245bb39... -> 49ae21b3...
dd if=<49ae21b3 image> of=/dev/sda24 bs=1M && sync
sha256sum /dev/sda24    # expect 49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9
```

A verified byte-exact copy of that image is held at
`.work/test-227/vendor_boot-device-before.img`. Nothing else on the tablet was
written.

## Related

* `docs/CPU_IDLE_WEDGE_PLAN.md` — the pre-registered rule this result is read against
* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — the states that were never entered
* `docs/CPU_WEDGE_EVIDENCE.md` — the signature and the rate
* `reference/boot-tests/test-226-cpuidle-off-gate/CANDIDATE-MANIFEST.md` — the candidate as built
