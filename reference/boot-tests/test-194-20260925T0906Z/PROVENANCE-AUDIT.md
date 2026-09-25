# Provenance audit of test-194: the round analysed the wrong boot

Round 30, in response to a review that required provenance to be proved before
any conclusion is drawn from test-194. The review was right, and the audit found
an error of mine rather than a defect in the evidence.

## The error

`test-194/README.md` and `boot-846e17b8-journal-facts.txt` analyse a boot called
**846e17b8**. That is the wrong boot. The round log says:

```
2026-09-25T09:06:13Z === baseline round 5/20 (boot_id before=846e17b8-...) ===
```

`boot_id before` is the boot **running when the round started** — round 4's
result. Round 5 reboots it (USB `False` at 09:06:23.768) and the boot that
returns at 09:06:43.570 is round 5's **result**. `journalctl --list-boots` names
the two boots:

```
 -2 846e17b8   <- round 4's result, round 5's "before"
 -1 0f056455   <- round 5's result: the boot that printed [8.623097]
```

So the boot carrying the disputed console line is **`0f056455`**, and everything
test-194 concluded about `846e17b8` was about the previous, healthy round.

## Binding the console line to a boot without assuming time order

Two independent clocks, because "it came next" is not evidence:

| clock | reading |
|---|---|
| journal, boot `0f056455` | `GTS9_DEBIAN_STAGE=multi-user` at monotonic **6.610508** |
| COM19, same event | `Reached target multi-user.target` at host **09:06:44.336Z** |
| derived offset | **09:06:37.725** |
| kernel `[ 8.623097]` → host | **09:06:46.35** |
| COM19 `frame done timeout` line at host | **09:06:46.537** |

0.19 s apart, which is ordinary console write latency. The line belongs to
`0f056455`. (For `846e17b8`, the same arithmetic lands at 09:03:35, where COM19
has nothing.)

## The claim that must be retracted

test-194/README.md said:

> `frame done timeout` in the kernel log | **0** (the one on the console never reached the ring)

**That is not established and must not be stated.** "Not in the journal", "not in
`/dev/kmsg`" and "not in the printk ring" are three different claims, and the
evidence supports only the first.

What the evidence does support:

* boot `0f056455`'s journal covers monotonic **2.474737 … 6.763559 and stops**,
  the last line being `Starting user@0.service`. Its pstore console shows the
  kernel still running at **170.255984** (`reboot: Restarting system`). The
  journal for that boot ends at 6.76 s, so **the 8.623 s line had no journal to
  appear in** — the capture stops before it.
* `grep -ra 8.623097 /var/log/journal/` returns **0 hits** across all 100 journal
  files including 77 rotated ones, while `frame done timeout` **is** found in
  other raw journal files. So the message class is journalable; this boot's
  journal simply stopped earlier. That is a capture-coverage fact, not a
  printk-path fact.
* **Level is not the explanation.** `DPU_ERROR_ENC_RATELIMITED` is
  `pr_err_ratelimited` (`dpu_kms.h:44`), i.e. `KERN_ERR`, and `loglevel=4`
  filters what reaches the *consoles*, not what enters the ring.

**Correct wording:** "the line is absent from that boot's journal capture,
which ends at 6.76 s."

**Forbidden wording:** "the line never reached the ring" / "never reached the
printk ring" — no ring-level evidence exists either way.

## What remains true from test-194

The measurement correction stands, on the right boot:

* boot `0f056455`'s journal runs **1111 lines / 934 kernel lines** over
  2.47–6.76 s, with `soft lockup`, `hung task`, `rcu stall`, `Kernel panic`,
  `frame done timeout`, `mmc1 Timeout`, `AMC RPMH` and
  `haven't responded to the NMI` all at **0**;
* its pstore console is 296 B and ends in `reboot: Restarting system` at
  170.26 s — a **clean restart, no panic text**;
* the operator's report (boot screen held, dead keyboard, then the login screen)
  is consistent with a quiet machine whose console had nothing more to say, not
  with a CPU wedge.

So `console silence != kernel freeze` is still the lesson. Only the supporting
analysis was aimed at the wrong boot.

## One attribution stays open

The restart of `0f056455` at 170 s is a **clean** restart, so it was requested,
not a watchdog panic. The harness never wrote a `round 6/20` header and no
`round-5.txt` exists, so the harness's own log does not account for it. Round 5's
probe was still running when I killed the process tree at ~09:09:1x, and the
restart lands at 09:09:28 — the most likely explanation is that a round 6 had
already been reached and had issued its reboot, and that killing the tree removed
the only record of it. **That is a hypothesis and is recorded as one.** Under the
new rule this round's ending is `unattributed`.

The durable fix for exactly this is the boot-identity work committed alongside:
a `run/round/boot_id` marker written into the journal and `/dev/pmsg0` before
every reboot, so console, journal, pstore and USB trace can be bound to one round
by construction instead of by inference.
