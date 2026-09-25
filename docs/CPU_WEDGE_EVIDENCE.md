# The stall is a CPU-level wedge, and it is measurable across the boot history

This is the first result in this investigation that is both **specific** (it names a
failure mode, not a window) and **quantitative** (it has a rate with a confidence
interval and a significance test). It comes from the device's own journal rather
than from host captures, so it covers 88 boots instead of the 22 a host ever
watched.

**Boot ids, not journal indices.** journald numbers boots relative to the current
one, so an index changes every time the tablet reboots or an old boot ages out -
during this round `1c082657` moved from `-67` to `-66` between two runs of the same
survey. Everything below is keyed by boot id, which is stable.

## What the signature is

Four kernel messages, none of which a machine that is merely being power-cycled or
flashed can produce:

| message | what it means |
|---|---|
| `After 10 seconds, these CPUS still haven't responded to the NMI: N` | a CPU is not executing at all — this is CPU-level, not a slow driver |
| `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:` | an RCU grace period cannot complete |
| `BUG: workqueue lockup - pool cpus=N ... stuck for Ns!` | a per-CPU worker pool has made no progress |
| `watchdog: BUG: soft lockup - CPU#N stuck for Ns!` | a CPU has not scheduled for longer than the soft-lockup threshold |

**That confound-freedom is the point.** The earlier comparison in this repository —
"45 of 46 pre-fix boots ended without an orderly shutdown against 6 of 29 post-fix"
— is real but unusable as a stall rate, because flashing, entering recovery and
pulling the power all end a boot that way too. None of them can produce an
unanswered NMI. Counting these four messages therefore measures the failure, not
the operator's activity around it.

## The rate

| era | boots that reached a full journal | boots showing the signature |
|---|---|---|
| pre-fix (the ACD error is present, GPU never binds) | 46 | **10 (21.7%, CI 12.3–35.6%)** |
| post-fix (no ACD error, `Initialized msm … for 3d00000.gpu`) | 29 | **1 (3.4%, CI 0.6–17.2%)** |

Two-sided Fisher exact **p = 0.043**.

The post-fix 29 is 28 boots that reached multi-user plus `fa0f2151`, which wedged
before it did and would otherwise be dropped by the "reached a full journal" filter
- dropping it would be the wrong way round, since wedging early is exactly the
thing being counted.

**All 11 of the 11 carry the unanswered-NMI line.** Not one of them is a software
stall that happens to have tripped a detector: in every case at least one CPU
stopped executing.

The 11, oldest first, with the marker counts. `rcu`, `nmi` and `wq` are counts of
`rcu detected stall`, `haven't responded to the NMI` and `BUG: workqueue lockup`;
`hung` is a *real* `blocked for more than` report, not the command-line token:

```
 boot_id   rcu nmi  wq hung  sl  last
 6a4ca9be    1   1   0   0   0   36.7 s
 2e735128    2   4   1   0   0  129.2 s
 9cc7a79a    3   3   1   0   0  218.1 s
 8eee6da9    1   2   1   0   0   46.4 s
 6255990d    1   1   2   0   0   62.4 s
 e0deedf7    7   7   6   0   0  479.2 s
 1c082657    4   8  28   2   0  357.4 s      <- the detailed trace
 a4e5bd13    2   2   3   0   0  132.4 s
 18b79721    7   7  47  18   0  496.8 s
 d5adf27e    3   3   0   0   0  182.9 s
 fa0f2151    1   1   2   1   1  104.5 s      <- POST-FIX, and the first post-fix boot
```

## The one post-fix wedge is the first post-fix boot

The boot immediately before `fa0f2151` is `f7b1e8de`, which still prints
`Unable to send ACD state to AOSS` and never binds the GPU; `fa0f2151` does neither
and binds it (`Initialized msm … for 3d00000.gpu`). Checked directly:

```
f7b1e8de   Unable to send ACD = 1   Initialized msm for 3d00000.gpu = 0   <- pre-fix
fa0f2151   Unable to send ACD = 0   Initialized msm for 3d00000.gpu = 1   <- post-fix
```

**So it is the first boot carrying the AOSS QMP + IPCC fix, and it wedged.**

Its timeline:

```
   0-10 s   1033 journal lines        <- the boot, normal
    50.16   systemd-logind: New session 1 of user root      <- LAST NORMAL LINE
   50-81   nothing at all
   81.168  rcu: INFO: rcu_preempt self-detected stall on CPU
   81.168  After 10 seconds, these CPUS still haven't responded to the NMI: 4
   93.157  BUG: workqueue lockup - pool cpus=2 ... stuck for 42s!   (and cpus=4)
  104.320  watchdog: BUG: soft lockup - CPU#7 stuck for 53s! [rcu_exp_gp_kthr:19]
  104.46   #3: 100% system, 0% idle   #4: 100% system   #5: 100% system
  104.517  <end of journal>
```

Three things there are worth keeping:

* the pools had been stuck since **~51 s**, and progress stopped at 50.16 s — the
  wedge begins there, not at 81 s where RCU first reports;
* **the watchdog worked.** `softlockup_panic=1` fired at 104.3 s and ended the
  boot. That is the first real instance of the profile's
  `stall → panic → panic=10 → reboot` chain doing its job on a wedge, rather than
  on a synthetic test;
* `workqueue.panic_on_stall_time=45` was armed on this boot and the pool was stuck
  for 42 s when the 93 s report came out — **three seconds short**. The soft-lockup
  panic got there first. Had the wedge been reported once more, the workqueue
  panic would have fired instead.

## One of them was caught live, with the operator watching

On 2026-09-25 at 03:37Z the wedge happened while a console capture was running and
the operator was looking at the tablet. It confirms the signature rather than adding
one, and it puts a number on the recovery:

| | |
|---|---|
| boot reaches multi-user | 03:37:44.251 |
| **last thing logged** | **03:37:45.185** (`Started session-1.scope`) |
| operator sees | screen stuck on the log, cursor blinking, keyboard dead |
| console probe | gets the **echo** of a command and no result — echoed, not executed |
| login screen back | ~03:40:5x |
| fresh boot caught on COM19 | 03:40:52 |

So the wedge began within a second of the boot completing and the machine was back
about **three minutes** later, `softlockup_panic=1` and `panic=10` having restarted
it. The USB gadget stayed up throughout and ssh was dead — kernel alive, userspace
not progressing, exactly as before.

Two operational consequences, both now in the harness:

* **a capture window of 60 s is too short.** The panic that ends the wedge comes
  about three minutes after it starts, so the stack trace was printed to a port
  nobody was holding. `test-190/wedge-hunt.sh` now holds COM19 for 200 s;
* **a run must not reuse capture filenames.** A second run overwrote the first run's
  files, and the live wedge's capture was only saved because the overlap was noticed
  and it was copied out. It is kept as
  `test-190-*/wedge-capture-20260925T0337-wedged-boot.log`.

The boot that wedged also carried a failure this project had introduced itself:
Debian's packaged `adbd.service` was still enabled alongside `gts9-adbd.service`, and
it fails on every boot because `adbd-usb-gadget setup` creates a second USB gadget
and then cannot bind a UDC that `gts9` already owns. That is a new suspect and not a
conclusion — the same unit failed on the preceding boot, which was fine — and the
hunt running since then has it masked. `test-190-*/LIVE-WEDGE-20260925T0337.md` has
the whole account.

## What this changes

**It gives the investigation a rate for the real thing.** The supportable statement
is: on the pre-fix kernel about one boot in five wedged at the CPU level; on the
post-fix kernel one boot in thirty did, and that one was the first boot after the
fix. 22% against 3% with p = 0.042 is not proof that the AOSS QMP + IPCC fix
removed the wedge — the two eras differ in more than that commit — but it is the
first comparison here that measures the failure instead of the operator.

**It moves the description of the failure up a layer.** §4.6 of
`docs/GPU_GMU_RPMH_STALL_PLAN.md` already showed that in boot `1c082657` the DPU,
workqueue and RCU messages all come *after* the wedge. This generalises it: in all
11 boots the first hard fact is "a CPU stopped answering", and everything this
project has been arguing about — DPU frame-done timeouts, `drm_fb_helper_damage_work`
parked in a vblank wait, `vmstat_update` pending, the deferred-probe burst — is
downstream of that.

**It replaces guesswork about the window.** The brief describes the stall as
occurring in a 13–14 s window; the boots that wedge do it at 7 s, at 50 s and at
unspecified later times (`last` ranges from 36.7 s to 496.8 s), and the two
freeze-shaped post-fix episodes stop at 6.2–6.5 s. The window was always a
property of when a host happened to be watching.

## What the CPU was doing, and what that points at

The wedge dumps report `100% system, 0% idle` on the affected CPUs, so they are
executing kernel code rather than asleep — and the RCU expedited grace-period
kthread is itself the task the soft-lockup detector names on `fa0f2151`
(`CPU#7 stuck for 53s! [rcu_exp_gp_kthr:19]`). `smp_call_function`'s
`csd_lock_wait()` and RCU's expedited handler both spin exactly like that while
waiting for a CPU that will never answer, so those are **victims of the same
missing CPU**, not a second fault.

What can make a CPU stop answering an NMI altogether? On arm64 the short list is a
CPU parked with interrupts masked, an SError, or a PSCI `CPU_SUSPEND` that never
returns. The last is worth stating because the platform evidence points at it:

```
$ cat /sys/devices/system/cpu/cpuidle/current_driver
psci_idle
$ for s in /sys/devices/system/cpu/cpu0/cpuidle/state*; do ...; done
state0 WFI                usage=50609   time=86 s
state1 cpu-sleep-0-0      usage=91839   time=1196 s     <- silver-rail-power-collapse
```

The CPUs spend about **92%** of their time in a rail power collapse, at roughly 70
entries per second, and the kernel reports no failed suspends at all — so the deep
idle path works overwhelmingly often. A wedge once per boot would be a failure rate
of order one in a million entries, which this cannot rule out and cannot confirm.

Two X710-specific findings from the X910 comparison the brief asks for, both in
this path:

* **`CONFIG_CPU_IDLE_THERMAL=y` and `CONFIG_CPU_IDLE_GOV_TEO=y` are X710-only**
  (`.work/x910/.../config-mainline.aarch64` has neither), and neither appears in
  `kernel/config/gts9wifi-mainline.fragment` — they are inherited from the stock
  Samsung config seed rather than chosen. The active governor on the device is
  `menu`, with `teo` available;
* the idle states themselves are upstream `sm8550.dtsi` and the board DTS does not
  touch them, so both boards describe the same hardware here.

That is a lead, not a conclusion: `CONFIG_CPU_IDLE_THERMAL` adds a cooling-device
path to idle-state selection and TEO is a different selection algorithm, and either
could in principle choose a state whose wakeup source is not up yet on this port.
Disabling the deep state at runtime needs no flash and no rebuild:

```sh
for c in /sys/devices/system/cpu/cpu[0-9]*; do
    echo 1 > "$c/cpuidle/state1/disable" 2>/dev/null
done
```

which is the cheap form of the experiment. `cpuidle.off=1` on the command line is
the blunt form.

## What it does not establish

* **Why a CPU stops.** Nothing in any of the 11 traces names a cause. There is no
  SError, no PSCI error, no panic before the wedge, and — on most of them — no
  detector armed that could have reported one.
* **That the post-fix era is genuinely quieter for the reason claimed.** The fix
  and the era boundary coincide by construction; a third era, or a pre-fix rerun,
  would be needed to attribute the change. The user has declined putting a pre-fix
  kernel back, and that remains the reason this is 22%-against-3% rather than a
  controlled comparison.
* **That 3% is the current rate.** n = 29 post-fix boots, CI 0.6–17.2%. The 22
  monitored post-fix cycles in test-187 and test-188 are inside that count.
* **What the journal loses.** It keeps 88 boots today and rotates; a boot that has
  aged out cannot be re-examined. The counts are therefore "of the boots retained",
  not "of all boots ever".

## Reproducing it

```
rootfs-overlay/usr/libexec/gts9-journal-survey    # on the device, read-only
reference/boot-tests/test-189-*/analyse-survey.py # the per-boot table
reference/boot-tests/test-189-*/journal-survey-wedge.txt
```

The survey writes one line per boot and touches nothing else. Two counting bugs
were found and fixed while building it, and both are worth knowing about because
this repository has hit the same class of bug before:

* the `Kernel command line:` line is excluded before counting. This board's cmdline
  carries `hung_task_panic=1`, so a bare `hung_task` pattern matched the command
  line and reported a hung task on 55 of 88 boots. It also carries
  `workqueue.panic_on_stall_time=45`, which is the same trap the workqueue metric in
  `warm-rounds.sh` fell into in round 16;
* `awk` was still being handed the file as well as the pipe, so it counted every
  line **twice** - once filtered and once not - and the `hung` column kept the
  unfiltered value. The corrected numbers are the ones above; the first run of this
  survey was discarded rather than interpreted.
