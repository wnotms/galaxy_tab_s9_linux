# Which boot does the panel photo belong to?

Round 30. The review asked for an evidence table before any timestamp is used as
causal evidence, and forbade using `17.887 - 10 = 7.887 s` as a fault argument
for test-194 until the table is closed. This closes it.

## The photo

`reference/boot-tests/test-191-20260925T0410Z/wedge-rate-pre-test191-capture/panel-20260925T0457-failed-boot.jpg`
— 2730x1536, sha256 `9a65eb4f6772879d1a1b6a377cf8af73c9422d4ec8755894e008e143a0f8b414`.
It is a photograph of the panel console, and its first line is
`GTS9_MINIMAL_STAGE=mounting-root`, so it is a **minimal-rootfs boot**.

The lines the review quoted, read off the photo:

```
[    6.755336] [drm:dpu_encoder_frame_done_timeout:2731] [dpu error]enc35 frame done timeout
[    7.911344] ... (repeats every ~1.184 s)
[   21.987343] mmc1: Timeout waiting for hardware interrupt.
[   24.487343] Error sending AMC RPMH requests (-110)
```

## The table

| photo event | kernel monotonic | host UTC | boot_id | source channel | in console? | in journal? | in pstore? | round marker |
|---|---|---|---|---|---|---|---|---|
| `encoder is disabled id=35` | 4.435920 | 04:57:07.6 | **not named in any journal** | pstore console | yes (pstore) | — | **yes** | none (pre-test-191) |
| `frame done timeout` ×1 | 6.755336 | 04:57:09.9 | unnamed | pstore console | yes (pstore) | — | **yes** | none |
| `frame done timeout` ×15, 1.184 s cadence | 6.755 → 21.9 | 04:57:09.9 → 04:57:25 | unnamed | pstore console | yes (pstore) | — | **yes** | none |
| `mmc1: Timeout waiting for hardware interrupt` | 21.987343 | 04:57:25.1 | unnamed | pstore console | yes (pstore) | — | **yes** | none |
| `Error sending AMC RPMH requests (-110)` | 24.487343 | 04:57:27.6 | unnamed | pstore console | yes (pstore) | — | **yes** | none |

The 04:57Z pstore record is
`reference/boot-tests/test-191-20260925T0410Z/wedge-rate-pre-test191-capture/failed-boot-pstore/console-ramoops-0`,
and all four photo timestamps (`4.435920`, `6.755336`, `21.987343`, `24.487343`)
are present in it exactly once each, with 15 frame-done events. **That record is
the photo's boot**, to the millisecond.

**Its boot id is not recoverable, and that is itself the finding.**
`FAILED-BOOT-20260925T0457.md` §4 establishes it: the boot is *absent from
`journalctl --list-boots`* (the list runs `c97ee7d7` then `b0237b3d`, and the
failing boot is not between them); no journal file contains either marker, while a
control grep for `gts9-debian` finds 25 of 29 files, so the search works; and
`gts9-prev-boot-evidence` reports `previous_boot_id=c97ee7d7` with
`marker_dpu_timeout=0` / `marker_mmc_timeout=0`, because `journalctl -b -1` for
the next boot resolves to `c97ee7d7` rather than to the boot that failed.

So the table's `boot_id` column reads "not named in any journal" — not because the
identity is unknown, but because **a boot that dies at ~7 s leaves no journal
record to name it**. An earlier draft of this table wrote `a2997452`, which is the
**06:59Z** episode, not this one; it was wrong and is corrected here.

## Answers

**Is `8.623097` uniquely round-5 of test-194?** Yes, and it is **not** this photo.
The photo's frame-done line is at **6.755336 s**, in a *flood* (15 events at a
1.184 s cadence); test-194's is a **single** event at **8.623097 s**. Different
boots, different shapes:

| | photo (04:57Z) | test-194 round 5 |
|---|---|---|
| boot | unnamed (absent from `--list-boots`), pre-`epss_l3` kernel | `0f056455`, flashed test-191 kernel |
| frame-done events | **15** at 1.184 s cadence | **1** |
| `mmc1 Timeout` | at 21.987 s, 2 dumps | **0** in the journal |
| `AMC RPMH` | at 24.487 s | **0** in the journal |
| pstore console | 15030 B, carries the panic | 296 B, ends in a clean restart |
| how it ended | `Kernel panic … softlockup: hung tasks` | clean restart at 170.26 s |

**Are the photo's console lines in the journal?** No, and here the check *was*
made rather than assumed: `FAILED-BOOT-20260925T0457.md` §4 grepped all 29 journal
files for `enc35 frame done timeout` and for `Timeout waiting for hardware
interrupt` and found **nothing**, with a working control grep. The photo's boot
has no journal entry at all. That is a stronger statement than the one available
for `0f056455`'s `8.623097`, and the two must not be conflated: this boot's
absence was *verified*, `0f056455`'s was *not checked*.

## The forbidden inference, and the conditional form that is allowed

The review forbade using `17.887 - 10 = 7.887 s` as test-194 fault evidence.
Agreed: that inference is **withdrawn**, and the table shows why it was wrong
twice over - `17.887` is not in this photo at all, and test-194 is a different
boot. **Nothing in this repository establishes that number.** Since the
inference is withdrawn, only the conditional form below is permitted, and only
for the photo's own boot.

What may be said is the conditional form the review allows, about the photo's own
boot only:

> *If* the `AMC RPMH` line at 24.487343 s belongs to the same real failure boot as
> the rest of the photo — which the 04:57Z pstore record supports, since all five
> events appear in that single record — *then* the 10 s `RPMH_TIMEOUT_MS` places
> the timed-out submission at **≈ 14.5 s** of that boot. That is a hypothesis
> about an unnamed boot, derived from one record, and it is the same arithmetic
> `docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md` §6b already tables for the three
> records (04:57Z → implied vote 14.804 s, consistent with the 14.31 s
> deferred-probe burst; 06:00Z and 06:59Z inconsistent).

It is **not** evidence about test-194, and it is not used as any.
