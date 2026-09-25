# Evidence-archive history: 8 boots on the post-fix kernel

> **Correction (round 16).** The ids in the first column are the **collecting**
> boots, not the boots described. The collector names its directory after the boot
> that runs it (`boot_id=$(cat /proc/sys/kernel/random/boot_id)`) while
> `prev-kernel.log` and `previous_boot_end=` describe the boot *before* it — so
> `…-8d7db274/` was created **by** `8d7db274` and holds its predecessor's journal.
> `176925b2` and `8d7db274` are therefore the boots that *followed* the two
> failures, whose own ids were never recorded. The quoted data is unaffected.
> See `docs/STALL_FAILURE_SHAPE.md` §7, which also resolves the open question in
> "What this does and does not establish" below: a live host capture of the
> `…-8d7db274` failure exists in this repository and shows 28.9 s of silence
> before the reset, refuting explanations (2) and (3).

Read from the device's own `gts9-prev-boot-evidence` archive
(`/var/log/gts9-boot-evidence/<utc>-<bootid8>/verdict.txt`). This is real,
already-collected per-boot evidence — not a synthetic fixture, and not pstore
(which does not survive on this port).

| evidence dir | `previous_boot_end` | markers | prev kernel lines | prev all lines |
|---|---|---|---|---|
| `…-1084b57a` | clean-shutdown | none | – | – |
| `…-14f0722f` | clean-shutdown | none | – | – |
| **`…-176925b2`** | **hard-reset-or-incomplete** | **none** | 1006 | 1213 |
| `…-7f8878b7` | clean-shutdown | none | – | – |
| **`…-8d7db274`** | **hard-reset-or-incomplete** | **none** | 990 | 1215 |
| `…-b0caae4b` | clean-shutdown | none | – | – |
| `…-f83c4b83` | clean-shutdown | none | – | – |
| `…-fd4589fa` | clean-shutdown | none | 996 | 1326 |

All eight show **zero** panic / soft-lockup / hard-lockup / hung-task / RCU-stall /
DPU-timeout / MMC-timeout markers, and all eight had the GPU bound
(`GPU=adreno`, confirmed on the live boot).

## The two anomalous boots, in detail

The journals are substantial, so these are not truncated-collection artifacts:

**`8d7db274`** — ends at 70.5 s with an *orderly-looking* shutdown already begun:

```
[   62.980049] gts9-debian: GTS9_DEBIAN_STAGE=multi-user
[   70.506420] systemd[1]: Stopping gts9-power-key.service ...
[   70.506685] systemd[1]: gts9-prev-boot-evidence.service: Deactivated successfully.
[   70.506895] systemd[1]: Stopped gts9-prev-boot-evidence.service ...
```

**`176925b2`** — ends much later, at 344.7 s, with a *root login on ttyGS0*:

```
[  344.721441] systemd[1]: Started user@0.service - User Manager for UID 0.
[  344.722243] systemd[1]: Started session-1.scope - Session 1 of User root.
[  344.723403] login[823]: ROOT LOGIN ON ttyGS0
```

Compare the clean case, `fd4589fa`, which ends with the shutdown actually in
progress:

```
[   89.848265] systemd-shutdown[1]: Syncing filesystems and block devices.
[   90.042607] systemd-shutdown[1]: Sending SIGTERM to remaining processes...
[   90.042985] systemd-journald[269]: Journal stopped
```

So a `clean-shutdown` verdict requires the `systemd-shutdown` marker in the
previous journal, and the two anomalies lack it while still looking like ordinary
running systems.

## What this does and does not establish

**Does establish:** this evidence path works, records real per-boot verdicts, and
distinguishes an unattended reset from a clean one. That is the capability the
previous series lacked (see `STALL-SERIES-ATTEMPT.md`, where the device rebooted
by itself and nothing noticed).

**Does NOT establish:** that these two boots stalled. Three candidate explanations
are all consistent with the data and the evidence cannot separate them:

1. a genuine hang whose journal simply stops (no panic ⇒ no marker, no
   `systemd-shutdown`);
2. an orderly but *fast* shutdown where journald stopped before flushing the
   `systemd-shutdown` lines — note `8d7db274` shows services already stopping at
   70.5 s, which looks like a shutdown in progress whose tail was lost;
3. a reset issued by something other than `systemctl reboot` (for example
   `reboot -f`, which skips orderly shutdown entirely).

Distinguishing them needs the *ordering* of events around the reset, not just the
last line — specifically whether anything was still making progress in the final
seconds. `prev-signatures.txt` in each directory is the place to look, and a
round that ends this way should be treated as "inspect", not "stall captured".

## Why this matters for the next series

`reboot-rounds.sh` now computes exactly this verdict per round and prints
`verdict=unattended-reboot` for it. That turns a silently-lost reboot into a
recorded, inspectable event — which is the difference between the previous
attempt (two unattended reboots, noticed only by accident) and a usable series.

It is also the honest limit of the current result: **2 of 8 boots on the
post-fix kernel ended without an orderly shutdown record and without any stall
marker.** That is a real observation that needs explaining, and it is *not* the
same claim as "the stall still happens" or "the fix failed".
