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
| `After 10 seconds, these CPUS still haven't responded to the NMI: N` | a CPU did not answer the backtrace request — see §"How much the 10 seconds is worth" before reading the timeout literally |
| `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:` | an RCU grace period cannot complete |
| `BUG: workqueue lockup - pool cpus=N ... stuck for Ns!` | a per-CPU worker pool has made no progress |
| `watchdog: BUG: soft lockup - CPU#N stuck for Ns!` | a CPU has not scheduled for longer than the soft-lockup threshold |

**Two corrections to how the first message must be read, both established by reading
the pinned source and the raw captures rather than the summaries.** They are in the
next two sections and neither weakens the conclusion, but both change what may be
claimed from it.

### It is a regular IPI on this build, not an NMI

`CONFIG_ARM64_PSEUDO_NMI` is **not set** (`out/kernel-gts9wifi/config:587`), and
arm64 says so itself (`arch/arm64/kernel/smp.c`):

```c
void arch_trigger_cpumask_backtrace(const cpumask_t *mask, int exclude_cpu)
{
	/*
	 * NOTE: though nmi_trigger_cpumask_backtrace() has "nmi_" in the name,
	 * nothing about it truly needs to be implemented using an NMI, it's
	 * just that it's _allowed_ to work with NMIs. If ipi_should_be_nmi()
	 * returned false our backtrace attempt will just use a regular IPI.
	 */
	nmi_trigger_cpumask_backtrace(mask, exclude_cpu, arm64_backtrace_ipi);
}
```

So the message means "did not take an ordinary interrupt", which is a *stronger*
statement than "did not take an NMI" and rules out "the NMI path specifically is
broken on this board". It also means the failure is not something an NMI-only
mechanism could have caught.

### How much the `10 seconds` is worth: less than the wording says

`lib/nmi_backtrace.c` waits for the backtrace mask to empty before it prints the
warning:

```c
	/* Wait for up to NMI_BT_TIMEOUT_SEC seconds for all CPUs to do the backtrace */
	for (i = 0; i < NMI_BT_TIMEOUT_SEC * 1000; i++) {
		if (cpumask_empty(to_cpumask(backtrace_mask)))
			break;
		mdelay(1);
		touch_softlockup_watchdog();
	}

	if (!cpumask_empty(to_cpumask(backtrace_mask)))
		pr_warn("After " __stringify(NMI_BT_TIMEOUT_SEC) " seconds, these CPUS still haven't responded to the NMI: %*pbl\n", ...);
```

`NMI_BT_TIMEOUT_SEC` is `10`, so the loop is meant to burn 10 s of `mdelay(1)`. In
**every** raw capture in this repository it does not:

| capture | interval between the two records |
|---|---|
| `test-181/host-captures/r3-stacks.log` (`-o short-monotonic`, raw) | `[36.340199] Sending NMI from CPU 4 to CPUs 5:` → `[36.340219] After 10 seconds … 5` = **20 µs** |
| same file, and the target answered | `[36.360250] Sending NMI from CPU 4 to CPUs 7:` → `[36.360265] NMI backtrace for cpu 7` = **15 µs** |
| `test-178/rcu-stall-backtrace.log` (raw) | three rounds — CPUs 4, 5 and 7 — all inside the single journal second `Apr 14 03:38:50` |
| `test-189/boot-1c082657-trace.txt` | `Sending NMI … 4` / `After 10 seconds … 4` / `Sending NMI … 5` / `After 10 seconds … 5` all at `47.261`–`47.262` |

A responsive CPU answers in ~15 µs, so the *ordering* is meaningful: a CPU that does
not answer inside even that short window is not answering. But the timeout is **not**
10 seconds of observation, and the marker must therefore be described as "did not
answer the backtrace request", never as "took no interrupt for 10 seconds".

**Why the loop finishes early is not established, and is not asserted here.** The
obvious candidate — `mdelay(1)` not being 1 ms on this board — does not survive
arithmetic: `dmesg` reports `Calibrating delay loop (skipped), value calculated
using timer frequency .. 38.40 BogoMIPS (lpj=76800)`, and with
`CONFIG_HZ=250` (and a 19.2 MHz arch timer, which is what `76800 = 19200000/250`
implies) arm64's `xloops_to_cycles()` gives

```
(1000 * 0x10C7 * 76800 * 250) >> 32 = 19200 cycles = 1.000 ms
```

i.e. exactly the millisecond it should be. So the two candidate explanations are
"`mdelay()` is short here after all" and "the displayed timestamps are not the
records' creation times", and this document does not choose between them. The
measurement that settles it is a console capture with **host** timestamps spanning
the pair — the captures above are journal reads, whose 1-second `short` format and
whose dependence on the (unset) RTC make them weaker than they look.
`reference/boot-tests/test-191-*/wedge-rate.sh` holds COM19 open for 300 s for
exactly this, because the panic that carries the NMI lines arrives ~180 s after the
wedge.

**What is unaffected.** CPUs 4 and 5 are wedged on evidence that does not involve
the backtrace at all. Same capture:

```
[   36.340179] rcu: (detected by 4, t=5255 jiffies, g=65, q=2442 ncpus=8)
[   36.340241] rcu: rcu_preempt kthread starved for 2495 jiffies! g65 f0x0 RCU_GP_DOING_FQS(6) ->state=0x0 ->cpu=7
```

`q=2442` is 2442 callbacks queued that the grace period cannot retire, and the
grace-period kthread has had no CPU for 2495 jiffies. Add the workqueue pool
reporting itself stuck for 55 s and the per-CPU items `pending` forever, and the
wedge stands on its own. The rate table below counts boots by this whole signature,
not by the backtrace line alone.

### `100% system, 0% idle` is the reporting CPU, not the wedged ones

`print_cpustat()` prints `smp_processor_id()`'s own `kcpustat` deltas, and it is
reached from the **soft-lockup** report path, not from the backtrace path:

```c
/* kernel/watchdog.c, watchdog_timer_fn() */
		pr_emerg("BUG: soft lockup - CPU#%d stuck for %us! [%s:%d]\n", smp_processor_id(), duration, current->comm, task_pid_nr(current));
		report_cpu_status();          /* -> print_cpustat() + print_irq_counts() */
```

and `report_cpu_status()` only exists because
`CONFIG_SOFTLOCKUP_DETECTOR_INTR_STORM=y`, whose purpose is to catch interrupt
storms. So the `CPU#N Utilization every Nms during lockup:` block describes **the
CPU that reported the soft lockup** — on the archived failure that is CPU 7, itself
spinning in `rcu_exp_gp_kthr` — and its `0% hardirq` says there was no interrupt
storm there. It is not a measurement of CPUs 4 and 5.

That matters because the earlier reading in this document ("the wedge dumps report
`100% system, 0% idle` on the affected CPUs, so they are executing kernel code
rather than asleep") used that line as evidence about the wedged CPUs. It is not.
What is known about CPUs 4 and 5 is the narrower and still-sufficient fact that they
did not answer an ordinary IPI.

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

## Which CPU wedges: the big and prime clusters, not the little one

Every one of the 11 carries the unanswered-NMI line, and that line names its target.
On SM8550 the CPUs are three clusters with three separate rails
(`sm8550.dtsi`: `capacity-dmips-mhz` 326 / 693 / 1024, and idle states
`cpu-sleep-0-0`, `cpu-sleep-1-0`, `cpu-sleep-2-0`):

| cluster | CPUs | rail | wedged |
|---|---|---|---|
| little (A510) | 0-2 | `silver-rail-power-collapse` | **1** |
| big (A715) | 3-6 | `gold-rail-power-collapse` | **10** |
| prime (X3) | 7 | `goldplus-rail-power-collapse` | **3** |

```
6a4ca9be  4          9cc7a79a  5          a4e5bd13  5
2e735128  4, 6       8eee6da9  5, 7       18b79721  5
6255990d  7          e0deedf7  2          d5adf27e  7
1c082657  4, 5       fa0f2151  4
```

**13 of the 14 (boot, CPU) pairs are in the big or prime cluster.** Under the null
that a wedge lands on any of the eight CPUs alike, big+prime are five of the eight
and that gives **P = 0.013**. Taking one sample per boot instead — the first CPU it
wedged — it is 10 of 11, **P = 0.043**.

Two caveats, because this is a narrowing and not a mechanism:

* the samples are correlates of each other. Eleven boots of one kernel on one board
  are not eleven independent draws, and a per-boot statistic was computed precisely
  because of that;
* the NMI target is chosen by the stall detector, not by the fault. What the
  histogram really measures is "CPUs that failed to answer", which is the right
  question, but it inherits whatever bias the detector's choice of target has.

What it is worth is direction. The little cluster — the one whose rail the kernel
spends ~92% of its idle time in — wedged **once**. The two clusters whose rails are
entered far less often wedged thirteen times. That does not fit "deep idle is simply
unreliable here"; it fits something specific to the big and prime clusters, and it is
the first time this investigation has had a hardware-shaped asymmetry rather than a
message.

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

The `#N: 100% system, 0% softirq, 0% hardirq, 0% idle` block that accompanies a
soft-lockup report is the **reporting** CPU's own utilization — CPU 7 on the
archived failure, which is itself spinning in `rcu_exp_gp_kthr` — and not a
measurement of the wedged CPUs. See §"`100% system, 0% idle` is the reporting CPU,
not the wedged ones" above; the earlier version of this section read it as evidence
about CPUs 4 and 5 and that was wrong.

What *is* established about the wedged CPUs is narrower: they did not answer an
ordinary backtrace IPI, and the RCU grace period cannot retire 2442 queued
callbacks because of them. `smp_call_function`'s `csd_lock_wait()` and RCU's
expedited handler both spin exactly like that while waiting for a CPU that will
never answer, so those are **victims of the same missing CPU**, not a second fault.

What can make a CPU stop answering an ordinary IPI altogether? On arm64 the short
list is a CPU parked with interrupts masked, an SError, or a PSCI `CPU_SUSPEND`
that never returns. The last is worth stating because the platform evidence points
at it:

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
