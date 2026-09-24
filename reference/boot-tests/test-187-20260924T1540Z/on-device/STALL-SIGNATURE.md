# The stall signature on this port, and why it leaves no panic report

Consolidated from the device's own evidence archive plus two episodes observed
live this session. This is the most specific description of the failure obtained
so far, and it also explains why five rounds have failed to capture a conventional
stall report.

## The live signature (observed twice)

| observation | meaning |
|---|---|
| COM17 opens and **echoes** typed bytes | the USB CDC-ACM gadget, the tty layer and the line discipline are all running ⇒ **the kernel is alive** |
| `login: timed out after 60 seconds` appears | agetty's own timer fired and printed ⇒ **userspace was running recently** |
| typing `root`, or any command, produces **no output and no execution** | nothing is reading the tty any more ⇒ **userspace has stopped making progress** |
| `adb` sees no device at any point | adbd is not running; expected, since Debian runs a ttyGS0 getty instead |
| the USB ports then **vanish and re-enumerate** | the tablet **reset** — USB gadget re-enumeration requires a full reset, not just a stuck process |

So the failure state is: **kernel alive and servicing interrupts and the tty, while
userspace makes no forward progress.** That is a much narrower and more useful
statement than "the system stalls".

## What the evidence archive shows for such a boot

`/var/log/gts9-boot-evidence/…-8d7db274/` records the boot that ended this way. Its
`prev-kernel.log` simply stops:

```
[   50.145630] qnoc-sm8550 24100000.interconnect: sync_state() pending due to 1c00000.pcie
[   50.146282] regulator: Not disabling unused regulators
[   62.672016] gts9-debian: GTS9_DEBIAN_STAGE=tty1-getty-active
[   62.980049] gts9-debian: GTS9_DEBIAN_STAGE=multi-user
<end of file>
```

and its `prev-signatures.txt` contains **only** two early entries, both
`Workqueue: events_unbound deferred_probe_work_func` at 2.29 s — the probe-time
WARNs, not stall markers:

```
627:[    2.292412] gts9 kernel: Workqueue: events_unbound deferred_probe_work_func
642:[    2.292528] gts9 kernel: Call trace:
686:[    2.293413] gts9 kernel: Workqueue: events_unbound deferred_probe_work_func
701:[    2.293527] gts9 kernel: Call trace:
```

No `Kernel panic`, no `BUG: soft lockup`, no `hung_task`, no RCU stall, no
`systemd-shutdown`. The boot reached multi-user at 62.98 s and then the record ends.

## Why there is no panic report — the important part

The profile has `softlockup_panic=1` and `panic=10`, and the archive confirms they
were armed (`watchdog_enabled=1`, `softlockup_panic=1`, `hung_task_panic=1`,
`wq_panic_on_stall_time=45`). A *soft lockup* would therefore panic and reset, and
the panic banner would be printed by the kernel.

The kernel's only surviving record of that banner would be:

* **pstore / ramoops** — ruled out; the DTS records that records do not survive a
  reboot on this device, and Samsung's own ramoops node ships `disabled`;
* **the serial console** — requires a host to be listening, which an unattended
  series does not have. **Corrected in round 7: it DOES carry kernel output.**
  Round 6 tested this without controlling `/proc/sys/kernel/printk` (which is
  `4.4.1.7`, so KERN_INFO is suppressed) and wrongly concluded the console was
  userspace-only. With the level raised, a `/dev/kmsg` marker reached COM19 as
  `[  345.478381][ T1011] GTS9_KERNEL_MARKER_B`. Since panic output is KERN_EMERG
  and bypasses the loglevel, **a host capture spanning the reset will catch a
  panic report** — see STALL-ROUND-7.md;
* **journald** — which runs in **userspace**.

So if the kernel panics *after* userspace has already stopped, the panic text has
nowhere durable to go: pstore is known-dead, journald is the thing that stopped,
and nobody is reading the console. **A stall that panics into `panic=10` can
therefore leave a completely empty trace on this port.** That is a property of the
evidence plumbing, not a claim about the stall, and it explains why five rounds
produced nothing but silent endings.

## The concrete consequence for the next attempt

The live signature is *directly observable* and cheap: open the console and check
whether a typed command executes. That gives a stall detector that does not depend
on any evidence surviving the event:

1. issue the reboot;
2. wait for the shell — **this board genuinely needs 4–6 minutes after a reset**,
   because the initramfs panel-recovery ladder can spend ~13–23 s and the rest is
   ordinary boot on a slow microSD (measured: a healthy boot reported uptime
   553.79 s when first reachable, and `systemd-analyze` says only 6.8 s of that is
   kernel+systemd);
3. send a harmless command **and require its output**, not merely an echo. Echo
   without execution *is* the stall;
4. treat "ports re-enumerated without an issued reboot" as a confirmed reset;
5. only then read the archive, and interpret an empty one as *unexplained*, never
   as clean.

Step 3 is the detector that five rounds lacked. `scripts/console-run.ps1` already
reports "shell answered"; what was missing was requiring a **command result**.

## What is still not established

* Whether the two `hard-reset-or-incomplete` boots and the two live episodes are
  the same phenomenon. They share the observable signature (reset, no marker) but
  were not captured with a command-result detector, so the userspace-progress
  check was never applied to them.
* Whether a panic actually occurs. Without pstore and without a listening console,
  this cannot be settled from the archive — it needs a **host-attached console
  capture spanning the reset**, which is the one experiment that would answer it
  and which no round has yet run.
