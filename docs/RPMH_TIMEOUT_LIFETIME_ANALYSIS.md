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

Test-186's captured rounds show `matched_done=0` for the timed-out address, i.e.
**no late completion was observed** in those runs. That weakens the hazard as an
explanation for *those specific* stalls and is the reason the hazard is carried
as a separate open item rather than being folded into the primary hypothesis.

## 6. Timeout arithmetic (why the search window moved)

`RPMH_TIMEOUT_MS` is 10 s. A warning printed at `+14.27 s` therefore says the
batch was **submitted at ≈ +4.27 s**. Two consequences that shaped
`docs/GPU_GMU_RPMH_STALL_PLAN.md`:

* the interesting window for the *first* bad actor is ~4–5 s, not 13–14 s; the
  13–14 s mark is when the 10 s completion expires and the cascade becomes
  visible;
* a "timeout then late completion" pair can be up to 10 s apart, so the hazard in
  §4 is not a narrow race at the timeout instant — any completion in the
  following 10 s lands on freed memory.

This is consistent with `docs/X710_X910_GPU_RPMH_DIFF.md`, where the GPU probe
and the `device_link_del` warning both fall at ~4.1–4.2 s.

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
