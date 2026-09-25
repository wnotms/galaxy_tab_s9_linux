# test-196 Profile C: the ablation took, and round 2 stopped the series

Flashed 2026-09-25T11:36Z (`vendor_boot` only), gate run 11:44Z, rounds
11:44–11:52Z. The series ran 12 rounds planned and **stopped itself on round 2**.

## The ablation is real — all four gates pass

| gate | expected | measured |
|---|---|---|
| `skip_gpu` exists under its real name | `Y` | **`Y`** |
| `no_gpu` does not exist | 0 | **0** |
| `/proc/cmdline` carries `msm.skip_gpu=1` | 1 | **1** |
| `msm.no_gpu=1` on the cmdline | 0 | **0** |
| `3d00000.gpu/driver` symlink | absent | **absent — UNBOUND** |
| `adreno` driver registered | no | **no (`/proc/modules` 0, `/sys/bus/platform/drivers/adreno` 0)** |
| DSI connector | `connected` | **`connected`** |
| display drivers bound | >0 | **16** |
| side effect: `Initialized msm … 3d00000.gpu` | 0 | **0** |
| side effect: `Unable to send ACD state` | 0 | **0** |
| cpufreq policies | 3 | **3** |

So the GPU genuinely never registers, the display survives, and the profile is a
real ablation rather than the silent no-op the old `msm.no_gpu=1` would have been.
Full transcript in `ABLATION-GATE.txt`.

## Rounds

| round | verdict | markers | outages | note |
|---|---|---|---|---|
| 1 | `clean` | 0 / 0 | 1 | the harness's own reboot |
| 2 | `wedge` | **0 / 0** | **2** | stopped the series; evidence preserved |

## Round 2 is a wedge by the restart criterion, and NOT by CPU-level evidence

`presence_outages=2`, second outage `2026-09-25T11:49:42.705Z`, back
`11:50:02.339Z`. The harness's own reboot accounts for the first outage only.

Boot `621c88a4` — round 2's result — has a kernel ring of **941 lines ending at
monotonic 7.366521 s** on `GTS9_DEBIAN_STAGE=multi-user`, and then nothing. Its
journal simply stops. There is **no** soft lockup, **no** RCU stall, **no** hung
task, **no** panic and **no** unanswered-NMI line, so `wedge_markers=0`.

That makes this a **different shape from the two baseline wedges** (test-195,
test-197), which both carried the full CPU-level set. Two readings remain, and
this record does not choose between them:

* **an abrupt death of the guest at ~7.4 s** — the journal stopping mid-boot is
  what a hard reset looks like, and it is the same stopping point
  `FAILED-BOOT-20260925T0457.md` §4 records for a boot that dies at ~7 s;
* **a host-side USB reset** — the COM19 capture's last two lines before the
  presence drop are `read failed … ReadLine … I/O …` and `port closed (read
  error)`, one second earlier at 11:49:41. A host controller reset would drop
  presence, and the guest's 7.4 s journal would then be a coincidence.

**The second reading is not excluded and matters:** if this was the host resetting
the bus rather than the tablet dying, then Profile C did not wedge at all and the
series was stopped for nothing.

## What would settle it, and why it is not settled here

The `dmesg-ramoops-0.enc.z` record is **28131 bytes** — up from 16499 earlier in
the session, so something did write a fresh crash dump — and its mtime is later
than the console record's. It cannot be read:

* the live kernel says so on every boot:
  `[2.192373] pstore: zlib_inflate() failed, ret = -3!` (confirmed present, count 1);
* its first four bytes are `c4 5c 5d 77`, which is not a gzip (`1f 8b`) or zlib
  (`78 ??`) header, so no userspace `zcat`/`openssl` can help either — the
  `zcat` attempt confirms it is not gzip.

So the one artifact that would name the dead boot's last state is present, is
larger than before, and is unreadable on this port. That is a concrete gap worth
naming: `CONFIG_PSTORE_COMPRESS=y` (with `CONFIG_PSTORE_RAM=y`, no explicit
algorithm symbol) is producing `dmesg-ramoops-*.enc.z` records this kernel cannot
inflate. The pstore *console* channel is unaffected and has carried every failure
record — but the *dmesg* channel, which would hold the oops/panic dump itself, has
never been readable on this port.

The pstore console, meanwhile, belongs to `83807280` — the *previous* boot — and
records that boot's clean `systemd-shutdown` at 186 s. So the one readable pstore
record for this window describes the boot before the one that died.

## What this does and does not say about the GPU

**It does not downgrade the GPU/GMU/ACD path**, because the event is not
classified: `wedge_markers=0` and the host-reset reading is open. The rule in
`docs/NEXT_STALL_DEBUG_PLAN.md` is that a wedge must be *bound* and carry
CPU-level evidence before it downgrades anything, and this one fails both tests.

**It does not exonerate it either.** One `clean` round and one unclassified event
is not a series. The honest summary is: **not determined in 2 rounds.**

## The harness defect this round exposed

A round record carries three different boot ids and, before this round, **none of
them named the boot the kernel-log evidence came from**:

* `identity=` — the boot the marker was *written on* (`83807280`), i.e. the boot
  the harness rebooted;
* `boot_id_before=` — the same boot;
* `boot_id_after=` — the boot running at probe time (`edb6499f`), two boots later;
* while `klog-2.txt` describes `621c88a4`, which none of the three names.

`journalctl -b -1` is the correct *selector* — at probe time it is the boot
immediately before the current one, which is the round's result — but the record
did not say which boot that resolved to. The probe now emits
`under_test_boot_id` and a four-entry `boot_list`, and the round record carries it.
Without that, a reader comparing `identity` against `klog` would conclude the
evidence was mislabelled when it was merely unnamed.

## Files

| file | what it is |
|---|---|
| `ABLATION-GATE.txt` | the four-gate transcript, taken on boot `8495ed74` |
| `candidate.txt` | the pre-flash plan, hashes and success/failure criteria |
| `c-round1.txt` | round 1's record: `verdict=clean` |
| `c-round2/` | round 2's preserved evidence, including the 406-byte pstore and both kernel channels |
