# RPMh timeout: request-lifetime analysis

**This document is analysis only. No lifetime semantics are changed by any patch
in this repository.** Diagnosis and repair are deliberately separate: the brief
requires it, and a change here would silently alter the behaviour of every RPMh
client on the SoC at exactly the moment the system is already wedged.

Source read: `.work/linux-mainline/drivers/soc/qcom/rpmh.c` at `a13c140cc`
(v7.2-rc3). Runtime evidence: `reference/boot-tests/test-186-*/fixtures/`.

---

## 1. The allocation

`rpmh_write_batch()` allocates **one** block for three things:

```c
ptr = kzalloc(sizeof(*req) +
              count * (sizeof(req->rpm_msgs[0]) + sizeof(*compls)),
              GFP_ATOMIC);
...
req    = ptr;
compls = ptr + sizeof(*req) + count * sizeof(*rpm_msgs);
```

so `req` (a `struct batch_cache_req`), the `rpm_msgs[]` array of
`struct rpmh_request`, and the `compls[]` array of `struct completion` are
**contiguous in a single allocation** and are freed together by a single
`kfree(ptr)` at the end of the function.

## 2. How the RSC learns about the request

For `RPMH_ACTIVE_ONLY_STATE` only, each message is submitted:

```c
rpm_msgs[i].completion = compl;
ret = rpmh_rsc_send_data(ctrlr_to_drv(ctrlr), &rpm_msgs[i].msg);
```

`rpmh_rsc_send_data()` → `claim_tcs_for_req()` stashes the request in the
controller's per-TCS slot:

```c
tcs->req[tcs_id - tcs->offset] = &rpm_msgs[i].msg;
```

**That stored pointer is a pointer into the block that `kfree(ptr)` frees.**

## 3. The timeout path frees it anyway

```c
time_left = RPMH_TIMEOUT_MS;          /* msecs_to_jiffies(10000) -> 10 s */
while (i--) {
        time_left = wait_for_completion_timeout(&compls[i], time_left);
        if (!time_left) {
                /*
                 * Better hope they never finish because they'll signal
                 * the completion that we're going to free once
                 * we've returned from this function.
                 */
                WARN_ON(1);
                ret = -ETIMEDOUT;
                goto exit;
        }
}
exit:
        kfree(ptr);
```

The code comment is candid about the hazard, and nothing on this path clears
`tcs->req[]`. `tcs->req[]` is cleared **only** by
`tcs_tx_done()` → `get_req_from_tcs()` → `rpmh_tx_done()`.

## 4. What a late completion would touch

If the RSC completes the transaction after the timeout:

1. `tcs_tx_done()` runs for that TCS and calls `get_req_from_tcs()`, which
   returns the **stale, freed** `struct tcs_request *` from `tcs->req[]`.
2. `rpmh_tx_done()` does `container_of(msg, struct rpmh_request, msg)` on that
   freed address, then:
   * calls `complete()` on `req->completion` — a `struct completion` **inside the
     freed block**;
   * for a non-`batch_cache_req` request it `kfree()`s the request again.
3. The controller slot is then set back to `NULL`, so the corruption is not
   self-announcing.

Expected observable damage: a `complete()` on a waitqueue whose memory has been
reused, and/or a double free. Both are the kind of damage that leaves unrelated
workers spinning and makes several subsystems look simultaneously stuck — which
matches the shape of the 13–14 s stalls (victims in unrelated subsystems).

## 5. Why this is *not* claimed as the root cause

It is a **hazard**, i.e. a mechanism by which a single RPMh timeout could become
a system-wide wedge. It is not evidence that it *did*. To promote it to a cause
one needs at least one of:

* a captured `LATE COMPLETION` (patch `0021` prints this, with the gap in ms
  between the timeout and the late completion) — the plan's test-186/E profiles
  exist to look for exactly this;
* a matching `rpmh_tx_done` for the timed-out address after the timeout in the
  event ring;
* a crash signature consistent with a freed-waitqueue `complete()` or a double
  free.

**CORRECTION (round 29): that observation does not exist.** An earlier revision
of this section said "test-186's captured rounds show `matched_done=0` ... no late
completion was observed in those runs". **There are no such rounds.** test-186 has
no `rounds/` directory because it was never run on the device, and the only
`matched_done=0` in this repository is inside
`test-186-*/fixtures/programmed-no-completion.log`, which is a synthetic fixture
written to pin `classify-round.sh`'s branches - as test-186's own README says in a
banner.

The consequence runs the other way from what the sentence claimed. The hazard is
not "weakened by observation"; it is **entirely untested on hardware**. Nothing in
this repository has ever looked for a `LATE COMPLETION` on this device, so:

* `matched_done` has no measured value, in either direction;
* the hazard stays open because it has never been probed, not because a probe came
  back negative;
* the first thing that would test it is a `rpmh-debug` run, because patch `0021`
  prints `LATE COMPLETION` with the millisecond gap between the timeout and the
  late completion. That run is now the cheapest way to move this item, and it
  needs no backport - the switch is already in the flashed kernel
  (`docs/RPMH_RSC_DEBUG_PATCH_STATUS.md` section 5a).

This is the third document found citing those same synthetic fixtures as device
evidence (the plan section 4, the RPMh status doc section 6, and here), which is
why `EvidenceProvenanceTests` now scans every document rather than one.

## 6. Timeout arithmetic (why the search window moved)

`RPMH_TIMEOUT_MS` is 10 s. A warning printed at `+14.27 s` therefore says the
batch was **submitted at ≈ +4.27 s**. (This arithmetic was first written from the
synthetic fixture's timestamp; §6a confirms it against the real capture at
`+14.273790 s`.) Two consequences that shaped
`docs/GPU_GMU_RPMH_STALL_PLAN.md`:

* the interesting window for the *first* bad actor is ~4–5 s, not 13–14 s; the
  13–14 s mark is when the 10 s completion expires and the cascade becomes
  visible;
* a "timeout then late completion" pair can be up to 10 s apart, so the hazard in
  §4 is not a narrow race at the timeout instant — any completion in the
  following 10 s lands on freed memory.

This is consistent with `docs/X710_X910_GPU_RPMH_DIFF.md`, where the GPU probe
and the `device_link_del` warning both fall at ~4.1–4.2 s.

## 6a. The real instance, which was in the repository all along

§6's arithmetic was written from the synthetic fixture's timestamp. **There is a
real capture of the same event**, and it says almost exactly the same thing:
`reference/boot-tests/test-183-20260924T082600Z/first-unattended-recovery.txt`, a
raw host console capture from the stall of 2026-09-24T08:41Z.

```
2026-09-24T08:41:59Z RECV  K kern  :info  : [ +14.273790] [     T57] ------------[ cut here ]------------
2026-09-24T08:41:59Z RECV  K kern  :warn  : [  +0.000015] [     T57] WARNING: ../linux-src-poweroff-trace/drivers/soc/qcom/rpmh.c:386 at rpmh_write_batch+0x1b4/0x25c, CPU#6: kworker/6:0/57
2026-09-24T08:41:59Z RECV  K kern  :warn  : [  +0.000020] [     T57] CPU: 6 UID: 0 PID: 57 Comm: kworker/6:0 Tainted: G S      W           7.2.0-rc3-gts9wifi-dirty #1 PREEMPT
2026-09-24T08:41:59Z RECV  K kern  :warn  : [  +0.000003] [     T57] Workqueue: events pogo_watch_work
2026-09-24T08:41:59Z RECV  K kern  :warn  : [  +0.000006] [     T57] pstate: 63400005 (nZCv daif +PAN -UAO +TCO +DIT -SSBS BTYPE=--)
2026-09-24T08:46:42Z shell never answered within 300 s
```

Four things this establishes, none of which the fixture could:

1. **`rpmh.c:386` is the `WARN_ON(1)` of the timeout path** (§3), verified against
   the pinned source at that line number - so this really is the 10 s timeout
   firing, not some other warning in the same function.
2. **The timestamp is `+14.273790 s`**, so by §6 the batch was submitted at
   **≈ +4.274 s**. The fixture's `14.270000` is within 4 ms of it, which is why
   the arithmetic survived being cited from the wrong source - but surviving by
   accident is not the same as being right for the right reason.
3. **`Workqueue: events pogo_watch_work`.** `rpmh_write_batch()` has exactly three
   direct in-tree call sites, all in `drivers/interconnect/qcom/bcm-voter.c`
   (`RPMH_ACTIVE_ONLY_STATE` at :315, `WAKE_ONLY` at :347, `SLEEP` at :355). So the
   request that timed out was an **interconnect bandwidth vote**, reached from the
   pogo watchdog worker. `rpmh_write()` does *not* funnel here - it uses
   `DECLARE_COMPLETION_ONSTACK` - so this is specifically the batch API.
   The intermediate frames are absent because the console went silent at
   `pstate:`, immediately after the WARN.
4. **The WARN is the last line before a five-minute silence.** That is a
   correlation and is recorded as one: the WARN is *printed by* the timeout path,
   so "last thing printed" is exactly what this code does when it gives up. It
   does not make the timeout the cause of the stall that follows - but it does
   make the hazard in §4 the immediate next thing in the sequence.

**What this changes.** The §11 item in the round brief ("a real failure showed
`rpmh_write_batch()` `ACTIVE_ONLY` transaction timeout") is this capture, and it
has been in the repository the whole time while three documents cited the
synthetic fixture instead. The real one is stronger evidence in every respect:
real timestamp, real taint, real caller, real silence after.

**What it still does not show.** `matched_done` - whether a *late* completion
arrived and wrote through the freed completion array. That is the §4 hazard's
direct test, it exists only in the synthetic fixture, and it has never been
measured here. `0021` prints `LATE COMPLETION` with the millisecond gap, and
`docs/RPMH_RSC_DEBUG_PATCH_STATUS.md` §5a records that the switch is already in
the flashed kernel - so this is a cmdline-only run away.

## 6b. The two ten-second timers, and which records separate them

There are **two** independent 10 s timers on this boot path, and both land at
~13–14 s if both start at ~3–4 s:

* `RPMH_TIMEOUT_MS = msecs_to_jiffies(10000)` in `drivers/soc/qcom/rpmh.c`, whose
  expiry prints the `WARN_ON(1)` at `rpmh.c:386`; and
* `CONFIG_DRIVER_DEFERRED_PROBE_TIMEOUT=10`, whose
  `deferred_probe_timeout_work_func()` re-probes every deferred device and walks
  `sync_state` - measured firing at **14.3076 s** in a real capture
  (`test-181-*/host-captures/r3-shutdown-window.log`).

They are easy to conflate, and the arithmetic separates them: an RPMh `WARN` at
time *T* means a vote was issued at *T* − 10 s. Applied to the three complete
failure records, using each one's `AMC RPMH` `-110` line (the BCM voter reporting
the same timeout) to infer when its vote was issued:

| record | `AMC RPMH` at | implied vote at | consistent with the 14.31 s burst? |
|---|---|---|---|
| 04:57Z | 24.804 s | **14.804 s** | **yes** — ~0.5 s after the burst |
| 06:00Z | 61.667 s | 51.667 s | no |
| 06:59Z | 39.654 s | 29.654 s | no |

**One of three.** So "the deferred-probe burst issues a vote, and that vote hangs
for 10 s" is a live explanation for the 04:57Z record and is *not* a general
mechanism — the other two imply votes at times nothing in this file accounts for.

Two further bounds, both from real captures:

* **test-181's stall carries no `rpmh_write_batch` warning at all**, so an RPMh
  timeout is **not necessary** for a stall;
* **test-183's stall is the reverse**: the WARN is the last line before five
  minutes of silence, so in that instance the timeout is immediately followed by
  the failure. Necessary: no. Present and adjacent in two of the records: yes.

That is the honest state of the RPMh direction, and it is why
`docs/RPMH_DEBUG_DECISION_RULE.md` pre-commits to reading a *no-dump* outcome as
evidence against this branch rather than as a failed run.

## 7. Candidate repairs (NOT implemented, NOT endorsed yet)

Recorded so the option space is written down before the data arrives. Each has
real cost and none is obviously right:

| approach | sketch | objection |
|---|---|---|
| Defer the free | keep the block alive until `tcs->req[]` no longer references it, e.g. refcount the batch | needs a lifetime rule for the sleep/wake cached paths too, and a bound on how long memory is pinned by a wedged TCS |
| Validate in `tcs_tx_done()` | null the slot on the timeout path under the controller lock, and have `tcs_tx_done()` skip a NULL slot | the timeout path runs in the *client* context, so it must take the controller lock to clear a slot owned by an IRQ handler — lock ordering and the "better hope they never finish" race both need care |
| Never free on timeout | treat it as a leak, bounded by the number of stuck TCSs | unbounded leak if the RSC never recovers; but "never recovers" is already fatal |
| Make the completion static | move `compls[]` out of the batch allocation into a slot the controller owns | does not fix the double-`kfree()` of the request itself |

Whichever is chosen must be argued on its own, in its own patch, with its own
review — not bundled into the diagnostic that found it.
