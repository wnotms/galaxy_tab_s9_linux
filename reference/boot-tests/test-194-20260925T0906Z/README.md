# test-194: a console-silence episode that was NOT a stall

2026-09-25T09:06–09:12Z, during the 20-round baseline hunt. This directory
records a **false positive** — my own — because the negative result is worth more
than the claim it replaced.

Nothing was flashed. The round was a warm reboot of the `baseline` profile, which
is byte-identical to the configuration already on the tablet.

## What I thought I saw

The round-5 boot printed, on COM19:

```
09:06:46.537Z RECV  [    8.623097][    C7] [drm:dpu_encoder_frame_done_timeout:2731] [dpu error]enc35 frame done timeout
```

and then **nothing** — 160 seconds of console silence, ICMP going from answering
to dead and back, ssh refused, and the operator reporting the tablet stuck on its
boot screen with a dead keyboard. That is the signature of every recorded stall,
so I reported a live stall capture.

`live-console-capture.txt` is the raw capture, preserved while it was happening.

## What the evidence says

Read from the two boots' own journals after the fact. The numbers below are
**both** boots, labelled, because the earlier version of this file mixed them:

**Boot `846e17b8` — round 4's result, healthy, and it is what round 5 rebooted**

| check | value |
|---|---|
| userspace journal (846e17b8) | ran to **168.83 s** |
| how it ended | `systemd-logind: The system will reboot now!` at monotonic **168.829708** |
| what that is | a **requested** reboot — and its host time, 09:06:23.8, matches the COM19 `USB False` of round 5's own reboot at 09:06:23.768 |

That match is worth noting on its own: it confirms the round-substitution chain
independently of the boot list.

**Boot `0f056455` — round 5's result, the boot that printed `[8.623097]`**

| check | value |
|---|---|
| journal span | monotonic **2.474737 … 6.763559** and then it **stops** |
| journal lines | 1111 total; 934 kernel |
| last journal line | `Starting user@0.service` |
| `soft lockup` / `hung task` / `rcu stall` / `Kernel panic` | **0 / 0 / 0 / 0** |
| `frame done timeout` / `mmc1 Timeout` / `AMC RPMH` / `haven't responded to the NMI` | **0 / 0 / 0 / 0** in the journal |
| pstore console | 296 B, ends `[  170.255984] reboot: Restarting system` |
| how it ended | a **clean** restart at 170.26 s — no panic text |

So the kernel of `0f056455` was still running at 170 s when something restarted
it cleanly, while its **journal stops at 6.76 s**. The `[8.623097]` line falls in
that gap, which is why the journal does not contain it — see
`PROVENANCE-AUDIT.md`, which is where the "never reached the ring" sentence is
retracted.

The operator's report (boot screen held, dead keyboard, then the login screen) is
consistent with a quiet machine whose console had nothing more to say. It is not
consistent with a CPU wedge: there is no lockup, no RCU stall, no unanswered NMI
and no panic anywhere in either boot.

## Why the console went silent

**Because the system went quiet.** Userspace finished its `[  OK  ]` lines at
8.6 s, and the kernel had exactly one message to print in the next 155 seconds.
An idle system with `consoleblank=0` leaves the panel showing the last text it
wrote, which is why it *looks* frozen — the operator's report is consistent with a
quiet machine, not a stuck one.

The `frame done timeout` at 8.623 s was the last line **before a quiet period**,
not before a stall. It is the same message that appears as the first abnormal
event in the three real records — which is exactly why it is dangerous on its own.

## What separates this from the three real stalls

| | the three real records | this episode |
|---|---|---|
| `Kernel panic - not syncing: softlockup: hung tasks` | present | **absent** |
| `rcu detected stall` | present | **absent** |
| `haven't responded to the NMI` | present | **absent** |
| kernel log | stops, then a panic | runs to a requested shutdown |

The markers were already known to be what distinguishes a real stall; this
episode is the control that shows they are **necessary**, not merely sufficient.
A lone `frame done timeout` plus console silence is not a stall.

## Two measurement defects found on the way, both mine

1. **A broken `awk` filter nearly produced the opposite conclusion.** I ran
   `journalctl -o short-monotonic | awk '$1+0 >= 9'` to look for kernel messages
   after 9 s. With `short-monotonic` the first field is `[`, so `$1+0` is 0 and
   the filter matched nothing — and an empty result reads exactly like "the
   kernel log stopped at 9 s", which would have confirmed the stall story. The
   correct form strips the bracket first: `sed 's/^\[ *//' | awk '$1+0 >= 9'`.
   Recorded because the wrong answer was the one I was looking for.
2. **`console_kernel_lines` was miscalibrated in the other direction.** It counts
   lines beginning with `[`, but every line in a console-watch file is prefixed
   with the host timestamp and `RECV  `, so it reported **0** while the capture
   held 85 kernel-prefixed lines. The metric is being fixed; the two channels it
   was meant to characterise are still the right ones, for a different reason
   than the one originally given.

## SysRq over this console is not possible, and that is now settled

When the console goes silent there is no way to ask the kernel anything, and the
obvious lever does not exist here. `scripts/sysrq-over-console.sh` exists to try
it, and it fails for two independent reasons:

* the USB serial adapter refuses `BreakState` ("the device does not have
  permission to send a break"), so the BREAK that serial SysRq requires cannot be
  sent at all;
* even with a BREAK, `serial_core.c`'s `sysrq_toggle_seq` path applies to
  **uart_port** consoles, and `ttyGS1` is a USB gadget tty, not one.

`sysrq_serial_sequence` is a **compile-time Kconfig string**, not a command-line
parameter, and its documented purpose is characters that *follow* a BREAK — so no
cmdline profile can open this path either. The pstore remains the only instrument
that survives a stall, which is why capturing it right after a restart is the
priority.

## Files

| file | what it is |
|---|---|
| `live-console-capture.txt` | the raw COM19 capture, taken while the episode was happening |
| `boot-0f056455-journal-facts.txt` | the checks above, extracted from the boot that actually printed the line |
| `PROVENANCE-AUDIT.md` | **read this first**: it corrects which boot this round is about |

> **Correction, round 30.** This file originally analysed boot `846e17b8`. That is
> round **4**'s result boot, not round 5's: the round log's `boot_id before` is
> the boot running when the round *starts*. The boot that printed `[8.623097]` is
> **`0f056455`**, bound to the COM19 capture by a two-clock offset check rather
> than by time order. The correction also retracts the sentence "(the one on the
> console never reached the ring)": the journal for `0f056455` stops at
> **6.763559 s**, so the line had no journal to appear in — which is a statement
> about capture coverage, not about the printk ring. See `PROVENANCE-AUDIT.md`.

The harness was stopped before it wrote `round-5.txt`, so this round has no
per-round record; the series' other rounds are unaffected.
