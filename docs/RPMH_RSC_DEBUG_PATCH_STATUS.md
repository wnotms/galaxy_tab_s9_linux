# Qualcomm RPMh RSC timeout-debug series: status and applicability

**Prepared, not applied.** Nothing in this file is in the default patch queue.
This is the record `docs/GPU_GMU_RPMH_STALL_PLAN.md` §7 profile **E** would need
if the A/B results require it. Recorded now so that the decision to enable it
later is a decision, not a scramble.

---

## 1. Identity

| field | value |
|---|---|
| title | `[PATCH v4 0/3] Output debug information from RSC` |
| latest revision | **v4** (no v5 or later found as of this writing) |
| posted | 2026-09-13 |
| authors | Maulik Shah `<maulik.shah@oss.qualcomm.com>` (patches 1–2), Raju P.L.S.S.S.N (patch 3) |
| change-id | `20260714-rpmh-timeout-debug-v1-785f011ce7e3` |
| message-id | `20260913-rpmh-timeout-debug-v1-v4-0-e94d3e416ea1@oss.qualcomm.com` |
| base-commit | `68142f986ff04b2b70b31db00f719bf690f64a9a` |
| series size | 3 patches, 5 files, +186/−2 |
| tested by author on | `x1e80100-crd`, against `linux-next next-20260811` |
| series URL (patchew) | https://patchew.org/linux/20260913-rpmh-timeout-debug-v1-v4-0-e94d3e416ea1@oss.qualcomm.com/ |
| patch 1/3 | https://patchew.org/linux/20260913-rpmh-timeout-debug-v1-v4-1-e94d3e416ea1@oss.qualcomm.com/ |
| patch 2/3 | https://patchew.org/linux/20260913-rpmh-timeout-debug-v1-v4-2-e94d3e416ea1@oss.qualcomm.com/ |
| patch 3/3 | https://patchew.org/linux/20260913-rpmh-timeout-debug-v1-v4-3-e94d3e416ea1@oss.qualcomm.com/ |
| previous revisions | v3 `20260812-rpmh-timeout-debug-v1-v3-0-68c0a40dce23`, v2 `20260717-rpmh-timeout-debug-v1-v2-0-81ade4fcdb49`, v1 a 2020 Qualcomm downstream posting |

Revision history that matters for applicability: **v3 added the `rpmh_read()`
timeout wiring and moved `WARN_ON()` inside the timeout condition**; v4 only
cosmetics (`dev_foo()` instead of `pr_foo()`, `str_yes_no()`, message wording).
So if a backport is ever needed, v4 is the right base and its delta from v3 is
not semantic.

## 2. Upstream status

**Not merged.** Not in mainline 7.2-rc3, and the helper symbols are absent from
the pinned tree:

```
$ grep -n "cmd_db_hw_type_str\|cmd_db_read_name\|rpmh_rsc_debug" \
      drivers/soc/qcom/cmd-db.c drivers/soc/qcom/rpmh-rsc.c \
      include/soc/qcom/cmd-db.h drivers/soc/qcom/rpmh-internal.h
ABSENT: not in v7.2-rc3
```

Consequences:

* **There is no upstream commit SHA to cite.** A backport would have to cite the
  message-id and revision, as `kernel/patches/0007-…` does for the still-unmerged
  GMU series.
* The series is still under review, so the revision to re-check is "v5 or later",
  not "v4".

## 3. What it adds, and why it is the right tool for this stall

Patch 1 adds `cmd_db_hw_type_str()`, patch 2 adds `cmd_db_read_name()` (reverse
address→name lookup, e.g. `cx.lvl`), patch 3 adds `rpmh_rsc_debug()` and wires it
into the `rpmh_write()`, `rpmh_write_batch()` and `rpmh_read()` timeout paths.

It answers almost the entire question list in
`docs/NEXT_STALL_DEBUG_PLAN.md` in one shot. Per-command output is:

```
addr=0x30000(ARC/cx.lvl) resp-required sts=triggered+sent-to-aoss+resp-received
```

and the block reports TCS index, controller status (`BUSY`, AMC mode), TCS IRQ
status (`DONE`/`WAITING`), whether the command requires a response, the decoded
`CMD_STATUS_{TRIGGERED,ISSUED,COMPL}` bits, **whether the HW IRQ is pending at
the GIC**, whether the completion is done, and a conclusion line. That is exactly
the type-A / type-B / type-C split this investigation needs:

| this series prints | classifies as |
|---|---|
| `sts=triggered+sent-to-aoss` but no `+resp-received` | **A** — reached AOSS/RSC, no response |
| `HW IRQ … is NOT PENDING at GIC` | **A**, and rules out IRQ delivery |
| `IRQ pending at GIC but not handled within timeout` | **B** — IRQ delivery / CPU stall |
| `Completion is done` yet the caller timed out | **C** — Linux-side lifetime/race |

Decisive corroboration that this series targets *our* failure: the example trace
in its own cover letter is

```
rpmh_write_batch+0x190/0x2b0
qcom_icc_bcm_voter_commit+0x33c/0x500
qcom_icc_set+0x20/0x34
icc_node_add+0xf8/0x118
qcom_icc_rpmh_probe+0x194/0x540
platform_probe
Workqueue: events_unbound deferred_probe_work_func
```

— an **interconnect BCM voter committing from `deferred_probe_work_func`**. The
X710's first captured RPMh timeout is also an interconnect path
(`1c00000.interconnect`, `kworker/6:0`) and the GPU probe that precedes it also
runs on `deferred_probe_work_func`. Same layer, same caller class.

## 4. Applicability to the pinned tree

Assessment from source inspection only; **not** compiled, because it is not being
applied this round.

| aspect | assessment |
|---|---|
| files touched | `drivers/soc/qcom/{cmd-db.c,rpmh-rsc.c,rpmh.c,rpmh-internal.h}`, `include/soc/qcom/cmd-db.h` — all present in 7.2-rc3 |
| base vs pinned | author's base is `next-20260811`; pinned is `v7.2-rc3`. The overlap of the touched files is small and stable, so hunks are likely to apply with offsets rather than conflicts |
| patch 1–2 (cmd-db) | additive helper functions; low conflict risk |
| patch 3 (`rpmh-rsc`) | needs `CMD_STATUS_{TRIGGERED,ISSUED,COMPL}`, `AMC`, and TCS control/status register definitions. These are in `rpmh-internal.h` / `rpmh-rsc.c` in v7.2-rc3 and must be confirmed field-by-field before the backport |
| patch 3 (`rpmh.c`) | wires the timeout paths, **including `rpmh_read()`**. `rpmh_read()` exists in v7.2-rc3, so the v3+ shape is applicable; this is the one spot where a real API difference is plausible and must be checked |
| `WARN_ON()` move | v3 moved `WARN_ON()` inside the timeout condition. Adding the dump must **not** suppress or relocate the existing `WARN_ON(1)` in a way that changes `panic_on_warn` behaviour during an A/B |
| runtime cost when no timeout occurs | the series is timeout-path-only, so it is inert on a clean boot — unlike the tracepoint/console approaches already rejected for observer effect |

## 5. Adaptation plan, if profile E is triggered

1. `git -C <worktree> apply --check` each of the three v4 patches against a
   prepared v7.2-rc3 worktree; record offsets and any rejected hunk verbatim.
2. If hunks reject, re-derive **only** the rejected hunk, and record the
   adaptation in the patch header (the brief forbids silently rewriting an
   upstream patch).
3. Put it in `kernel/patches/diagnostic/` as `0022-…`, opt-in behind a new
   `GTS9_RPMH_RSC_DEBUG=1` in `scripts/prepare-kernel.sh`, **not** in the default
   queue — the same shape as `0021`.
4. Keep `WARN_ON(1)` and its placement unchanged so the watchdog and
   `panic_on_warn` semantics are identical to the A/B baseline.
5. Build, then run profile E with the detector set unchanged.

## 5a. The local switch is already compiled into the running kernel (round 28)

This changes the cost of getting timeout-state evidence, so it is worth stating
plainly: **no backport is needed to ask the §15 questions.** `0021` is an opt-in
`early_param`, and it is present in the kernel the tablet is running right now.

Verified three ways, none of which depends on reading the patch:

```
$ zcat out/kernel-gts9wifi/Image.gz | strings -a | grep -E 'gts9_rpmh_debug'
gts9_rpmh_debug_enabled
gts9_rpmh_debug_setup
gts9_rpmh_dump_timeout
gts9_rpmh_debug

$ sha256sum out/kernel-gts9wifi/Image.gz
df00c53cabfae26c0a96c6b93ada4590dfb44d02f16c39bd139ef52a9a19e32f
$ grep image_gz_sha256 out/boot-bundle-test191-osm-l3/BUNDLE_INFO
image_gz_sha256=df00c53cabfae26c0a96c6b93ada4590dfb44d02f16c39bd139ef52a9a19e32f
```

The image that carries the strings is byte-for-byte the image in the flashed
bundle. The switch is registered as

```c
early_param("gts9_rpmh_debug", gts9_rpmh_debug_setup);
```

so it is **command-line only** - there is deliberately no
`/sys/module/*/parameters/gts9_rpmh_debug` on the device, and its absence is not
a missing feature.

`boot/cmdline.rpmh-debug.example.txt` already carries `gts9_rpmh_debug=1`, and
`out/boot-bundle-rpmh-debug/vendor_boot.img` already embeds it, so a
timeout-state run is a cmdline-only flash of `vendor_boot`.

**Where this sits in the brief's priority order.** The brief ranks *existing
kernel diagnostic switch* above *official Qualcomm debug patch* and puts
self-designed instrumentation last. `0021` is self-designed - but it is already
compiled into the running kernel, inert without the flag, and costs nothing to
use. That is not designing new instrumentation; it is using an asset that
exists. The Qualcomm v4 series stays the fallback for the fields §6 lists as
missing from 0021 (resource name, TCS command-status bits, AMC mode, GIC pending
state) - and those are exactly the fields that separate class A from class B.

**It must not be enabled during an A/B round.** The three cmdline profiles forbid
`gts9_rpmh_debug` by name because of the observer effect, and the ring plus the
branch are a behaviour change. It belongs in a dedicated run, aimed at capturing
a timeout, not in the rate comparison.

## 6. Relationship to patch 0021 (already in this repo)

Patch `0021-gts9-rpmh-timeout-state-dump.patch` is a **local, narrower**
diagnostic that already exists and is opt-in. It records a 128-entry in-RAM ring
of send/completion events with `(rsc_id, tcs_id, state, addr, data)` plus a
timeout-time snapshot of `tcs_in_use`, `irq_status`, `irq_enable` and the holding
TCS, and it prints a `ring_summary` that states whether the timed-out request was
programmed and whether it ever completed.

Overlap and difference:

* **Overlap**: both answer "was it programmed, and did it complete?".
* **CORRECTION (round 28).** An earlier revision of this section said 0021 "already
  produced the §4.2 table ... (`programmed-no-completion.log`, `victim.log`)".
  **It did not.** Those two files are synthetic fixtures under
  `reference/boot-tests/test-186-*/fixtures/`, written to pin `classify-round.sh`'s
  branches; test-186 has no `rounds/` directory because it was never run on the
  device, and the `13.400000` / `14.270000` timestamps in them appear nowhere
  outside that fixture and its README. `GPU_GMU_RPMH_STALL_PLAN.md` §4 already
  carries this correction for its own citation; this file was still making the
  same claim about the same two files.

  The consequence is not academic. "Was the request programmed and did it ever
  complete?" is the first question of the timeout-state analysis, and crediting
  0021 with a hardware answer to it invites the conclusion that the run which
  would actually answer it can be skipped. **Patch 0021 has never produced a
  hardware result on this device.**
* **What 0021 does not do**: decode the resource **name** from the address (it
  prints `addr=0x00017004`), decode the TCS command status bits, print the AMC
  mode, or test whether the **GIC** has the IRQ pending. Those are precisely the
  fields that separate class A from class B.
* **Therefore**: use 0021 first (already built, zero new code), and adopt the
  Qualcomm series only if the 0021 output leaves the A/B/C class ambiguous —
  which is the condition the plan already sets for profile E.
