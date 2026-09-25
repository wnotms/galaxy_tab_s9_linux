# Next stall-debug plan: from "13-14 s stall" to a layer in the RPMh chain

Status: **plan of record, revised in round 30.** Sections 1-3 are the original
test-185/186 plan with its stale facts corrected in place; the round-30 rewrite at
the end supersedes its reasoning, because test-194 changed the evidence base - a
console-silence episode that looked exactly like a wedge was a quiet healthy boot.

## 1. Confirmed facts (do not re-derive)

| # | fact | evidence |
|---|---|---|
| 1 | ABL → mainline Linux → Debian boots on real hardware | `reference/boot-tests/test-178-*`, `docs/MINIMAL_ROOTFS_BOOT.md` |
| 2 | microSD rootfs reaches Debian multi-user reliably | test-178 stage history |
| 3 | display works (ANA38407 panel, DPU/DSI) | `docs/DISPLAY_X710_OFFICIAL_V1.md` |
| 4 | `ttyGS0` = USB ACM userspace root shell | `docs/USB_SERIAL_CONSOLE.md`, test-184 |
| 5 | `ttyGS1` = USB ACM kernel printk console (`CONFIG_U_SERIAL_CONSOLE=y`, `console=ttyGS1`) | test-183/184 |
| 6 | software watchdog panics on soft lockup / hung task and `panic=10` reboots | test-183: 3/3 soft-lockup, 1/1 hung-task rounds |
| 7 | PCIe0 is **not** the stall cause | test-182 A/B with `pcie0` + PHY disabled still stalled |
| 8 | the 4.7 s → 125 s "pause" was `/dev/console → tty0 → fbcon → DRM` output backlog | test-184: all 28 report lines journal-timestamped `[4.646574]`, `ExecMainExit` at 155.87 s |
| 9 | the DPU really does fail later in a stall, but that is not proof it is the common cause | `docs/DPU_TRACE.md` §"failure chain" |
| 10 | **CORRECTED (round 30).** real stalls do *not* cluster at 13.3-14.3 s. The three complete records that now exist struck at **6.8 s, ~52.5 s and ~76 s**, and test-195's wedge ran to 28.8 s before the RCU stall. The window is one instance, not a law | test-194/195; `docs/STALL_FIRST_EVENT_ORDERING.md` |
| 11 | an **ACTIVE_ONLY RPMh transaction timeout** is the last line before a five-minute silence in **one** real failure (test-183), and it is not necessary: test-181's stall carries no such warning. `rpmh_write_batch()`'s only in-tree direct callers are `bcm-voter.c`, so the request was an interconnect bandwidth vote | `reference/boot-tests/test-183-*/first-unattended-recovery.txt`; `docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md` §6a |
| 12 | `pogo_watch_work` was the *caller* of that transaction | same log; the keyboard is docked and healthy in clean boots too |
| 13 | **CORRECTED (round 30).** ramoops **does** survive a reboot and is the project's only surviving instrument for a real wedge. Every complete failure record since test-191 was read out of `/var/lib/systemd/pstore/`, and test-195's wedge was captured that way | test-191/194/195 pstore records; the old `pstore_records=0` was a *directory* bug (`systemd-pstore` moves records to `/var/lib/systemd/pstore`) |
| 14 | no Gunyah/`qcom,gh-watchdog` driver exists in this tree | test-183 audit |

## 2. Hypotheses already excluded

* **PCIe0 / its PHY** — disabled in DTS for a full A/B, stall reproduced.
* **The watchdog helper's own output** as a *system* stall — it was console
  backlog (fact 8); the helper now runs in ~0.5 s and journal-only.
* **The kmsg mirror / DPU ftrace stream** as the cause of the stall — off in
  test-184 profile A, on in profile D, both 0 stalls; no rate difference
  measurable (and no claim is made either way).
* **The pogo keyboard as root cause** — it is docked and answering
  (`MCU model 0x1 hw 0 firmware 1.4 mode 1`) on clean boots; only its *call
  path* shows up in the failing one.
* **`ttyMSM0`/`ttyGS0` device timeouts** as the stall — they were getty/device
  ordering issues, fixed, and the stalls predate them.

## 3. Open questions

1. Where in the chain
   `client → rpmh_write_batch → rpmh_rsc_send_data → claim TCS → program TCS →
   trigger → RSC → IRQ → tcs_tx_done → rpmh_tx_done → completion`
   does an ACTIVE_ONLY request actually stop?
2. Is there a `rpmh_send_msg` without a matching `rpmh_tx_done` for the same
   address/data?
3. Is the RSC IRQ status set while `tcs_tx_done()` never ran (IRQ delivery /
   masking / CPU stall), or does `tcs_tx_done()` run and the completion still
   not fire (request/completion lifetime)?
4. Is the RPMh timeout the **first** anomaly of the boot, or is it preceded by
   scheduler/workqueue/RCU trouble (in which case RPMh is a victim)?
5. Does the timeout-then-late-completion hazard in `rpmh_write_batch()` (the
   code comment about a completion firing after the request is freed) actually
   occur? `tcs->req[]` is cleared in `tcs_tx_done()` only, so a late IRQ would
   touch a `tcs_request` that `rpmh_write_batch()` already `kfree()`d.
6. Does shutting off the DPU ftrace stream remove the multi-minute
   shutdown/reboot observed in test-184?
7. Does the stall still reproduce with only the detectors armed plus an
   opt-in RPMh timeout dump?

### 3a. The request-lifetime hazard, spelled out

`rpmh_write_batch()` frees its batch on timeout while the RSC may still be
holding a pointer to it. Concretely, in this tree:

1. `rpmh_rsc_send_data()` → `claim_tcs_for_req()` programs a TCS and stashes
   `tcs->req[tcs_id - tcs->offset] = &rpm_msgs[i].msg`; the request itself is
   the `struct rpmh_request` that `rpmh_write_batch()` allocated as one `ptr`.
2. If the RSC does not raise the completion interrupt inside `RPMH_TIMEOUT_MS` —
   which is **10 seconds** in this tree
   (`drivers/soc/qcom/rpmh.c: #define RPMH_TIMEOUT_MS msecs_to_jiffies(10000)`) —
   `rpmh_write_batch()` warns, sets `-ETIMEDOUT` and `kfree(ptr)` — freeing the
   request, its message array and the completion array.
3. `tcs->req[...]` is **only** cleared by `tcs_tx_done()` → `get_req_from_tcs()`
   → `rpmh_tx_done()`. Nothing clears it on the timeout path, and the code
   comment there says so: "Better hope they never finish because they'll signal
   the completion that we're going to free once we've returned from this
   function."
4. If the RSC completes **later**, `tcs_tx_done()` reads the stale pointer,
   `rpmh_tx_done()` runs `container_of()` on freed memory, calls
   `complete()` on a freed `struct completion` and may `kfree()` the same
   object a second time.

### 3b. What the 10 s timeout means for the 13-14 s window

The recorded stall printed the `rpmh_write_batch()` warning at **+14.27 s**. With
a 10 s timeout that warning is not a statement about 14 s — it says the batch
was submitted at roughly **+4.3 s** and never completed. Two consequences:

* the search window for the first bad actor is **~4-5 s**, i.e. early userspace
  (`gts9-usb-acm` / panel recovery / the first Pogo poll after the MCU handshake)
  — not the 13-14 s mark where the *symptom* becomes visible. The stall hunt has
  been looking at the wrong end of the chain: +13-14 s is when the 10 s timeout
  expires and the cascade starts, not when it began.
* a "timeout then late completion" pair can be up to 10 seconds apart, which is
  why §3a's hazard is not a narrow race at the timeout instant: any completion
  in the following 10 s lands on freed memory.

Both statements are source-derived and falsifiable by test-186: the dump prints
the timeout instant and the ring's timestamps, and `LATE COMPLETION` prints the
completion instant, so the gap is measurable rather than assumed.

That is a use-after-free on a live interrupt path, and it is a *plausible
mechanism* for a one-off RPMh timeout to become a system-wide wedge: a corrupted
waitqueue or a double free inside an IRQ handler is exactly the kind of damage
that leaves several CPUs spinning and makes unrelated workers look stuck. It is
also entirely consistent with what the recorded stalls look like — one early
`rpmh_write_batch` timeout, then victims in unrelated subsystems.

What this round does about it: nothing to the lifetime. Patch 0021 *reports* the
hazard (`LATE COMPLETION ... the rpmh_write_batch() lifetime hazard is real`,
plus `holder_tcs` in the dump so "the request is still stashed" is visible), and
test-186 records whether it happens. A fix — for example deferring the free
while `tcs->req[]` still references the request, or making `tcs_tx_done()`
validate the pointer — is a separate patch with its own argument and its own
review, and is deliberately not bundled here.

## 4. Why RPMh/RSC is the next thing to investigate

* It is the **earliest** anomaly we have actually captured in a failing boot
  (fact 11), and it is a *software-visible* one: `rpmh_write_batch()` detects it
  itself and warns, so we do not have to infer it from a symptom.
* Its blast radius matches the observed symptom family: every late-stall victim
  (`pm_runtime_work`, `pogo_watch_work`, `toggle_allocation_gate`,
  `fqdir_free_fn`, SDHCI, DPU) reaches power/clock/interconnect votes through
  RPMH. One wedged RSC explains *why the victims vary*.
* The failure is at a **layer boundary** (Linux ↔ RSC firmware/TCS), which is
  exactly where a 13-14 s, load-dependent, low-rate race would live.
* It is cheap to instrument **only at failure time**: the timeout is detected in
  Linux, so an opt-in dump costs nothing on the normal path (no continuous
  trace to the microSD, no observer effect like test-184's).

## 5. Why not DPU / Pogo / PCIe / PMIC right now

* **DPU**: it does fail, but always *after* the RPMh anomaly in the one boot
  where we have both; treating it as the common cause is the "last module to
  print" mistake the brief warns about. Its own evidence (`docs/DPU_TRACE.md`)
  shows it can also fail late and slowly (display death at 109.87 s), which is a
  different shape from the 13-14 s wedge.
* **Pogo**: the driver's own history (test-100) shows acting on a NACK makes
  things worse; nothing yet distinguishes its I2C runtime-PM vote from any other
  RPMh client's.
* **PCIe**: already falsified (fact 7).
* **PMIC / regulators / voltages**: no measurement points at a rail; the brief
  forbids guessed register work, and a wrong regulator change risks the SoC.

## 6. test-185 — shutdown/reboot baseline, no kernel change

Question: *does the multi-minute shutdown/reboot still happen with the DPU
ftrace stream off?* test-184 observed ~3.5 min once, but the stream was writing
megabytes/s to the microSD at the time, and the stale `/etc` unit meant the
"off by default" flag was not actually in effect then. It is now.

Profile: the current image, `gts9_watchdog_debug=1` only (no
`gts9_kmsg_mirror`, no `gts9_dpu_flight`), `ttyGS0` shell, `ttyGS1` console.

Rounds: 3 × {`systemctl reboot`, `systemctl poweroff`, and `shutdown -P now`
only if a command disagrees}. Per round record: boot_id, `/proc/cmdline`,
failed units, command issue time, USB-gap start/end, shutdown journal tail,
watchdog state, flight/mirror service state, ttyGS0/ttyGS1 state, and whether
any workqueue stall / RCU stall / RPMh timeout / DPU timeout / MMC timeout
appeared.

Evidence needed to conclude: command→USB-gap and USB-gap→shell-return times for
each of the 3 rounds, with the recorder services confirmed inactive.

What must **not** be concluded: that a slow shutdown is "fixed" by lowering
instrumentation, or that it is a PSCI/PMIC problem — a slow shutdown with the
recorder off only says the recorder was not the (only) reason.

Harness: `reference/boot-tests/test-185-*/shutdown-baseline.sh`, built on
test-184's `observer-ab.sh` (same console-run/console-watch helpers, no flash,
no partition writes).

## 7. test-186 — capture one real 13-14 s stall with one new variable

Profile: watchdog ON, `ttyGS1` console ON, DPU flight OFF, kmsg mirror OFF,
**RPMh timeout diagnostic ON** (`gts9_rpmh_debug=1`), Pogo untouched, PCIe
untouched, regulators untouched, PMIC untouched, panel-recovery timing
untouched.

The only new variable versus test-184 profile A is the RPMh diagnostic.

Harness: `reference/boot-tests/test-186-*/rpmh-stall-capture.sh` — cold/warm
boots, console capture on `ttyGS1`, then per boot collect: boot_id, boot
monotonic time, first anomaly time, first RPMh timeout, caller, command
addr/data, TCS id, RSC IRQ status, `tcs_in_use`, whether a matching
`rpmh_tx_done` exists, and the later DPU/MMC/workqueue/RCU markers, watchdog
panic, USB disappearance, automatic reboot and the new boot_id.

If no stall occurs: record **"not reproduced this round"**. No claim of a fix.

## 8. Decision tree (fixed before data collection)

| Observation | Conclusion to draw | Next step |
|---|---|---|
| `rpmh_send_msg` recorded, no `rpmh_tx_done`, TCS still in use with CMD_ENABLE set | the request reached the RSC and never completed | investigate RSC/TCS hardware completion and the RSC IRQ path |
| RSC IRQ status shows the TCS bit set, but `tcs_tx_done()` never ran | completion happened in hardware, Linux did not service it | investigate IRQ delivery/masking and what that CPU was doing |
| `tcs_tx_done()` ran for that TCS, yet `rpmh_write_batch()` timed out | Linux-side completion/lifetime bug | investigate request matching and the timeout/late-completion hazard (§3.5) |
| scheduler/workqueue/RCU anomalies precede the first RPMh timeout | RPMh is a **victim** | move to the CPU/scheduler side; keep RPMh as symptom |
| RPMh timeout is the first anomaly | keep RPMh/RSC as the prime direction | extend the dump (TCS/IRQ history) rather than switching subsystems |
| No timeout, but a different first anomaly | record it; do not bend the RPMh story | follow that anomaly with its own opt-in diagnostic |
| No stall at all | "not reproduced" | repeat test-186; do not change code |

## 9. Evidence discipline

* "First thing printed" ≠ "root cause": build the chain in monotonic order, and
  say explicitly which link is missing.
* A dump proves the state **at** the timeout, not what caused it. Any statement
  about cause needs either an earlier first anomaly or a controlled A/B.
* Zero reproductions are a result, not a failure: they bound the rate.
* Every claimed number must come from `journalctl -o short-monotonic`, the
  kernel console capture, or a `/proc/uptime`-based trace — never from screen
  ordering (test-184 fact 8).

## 10. Safety boundaries for real-device work

* No flashing, no partition writes, no BCB writes, no `dd` to any device node
  without an explicit instruction for that specific action.
* No PMIC register writes, no regulator/voltage changes, no PCIe changes, no
  bootloader/recovery changes, no keyboard firmware.
* The diagnostic is default-off and changes nothing unless
  `gts9_rpmh_debug=1` is on the command line.
* A stalled tablet is recovered by the software watchdog when the detectors see
  it; otherwise a physical power hold is the operator's call.

## 11. Rollback

* Kernel diagnostic: rebuild without `GTS9_RPMH_DEBUG=1`
  (`scripts/prepare-kernel.sh` + `scripts/build-kernel.sh`), or `git -C
  .work/build/linux-src-* checkout -- drivers/soc/qcom/`; the default patch
  queue does not contain it.
* Boot images: test-183's `rollback.sh` writes the known-good pair back with the
  verified backup → SHA256 → flash → readback → SHA256 chain. Current known-good:
  `boot.img 2e8a693f…` (with `CONFIG_U_SERIAL_CONSOLE`), `vendor_boot` profile A
  `123f35f2…`, profile D `f1f4ccf7…`, dtb `b3e068e7…`.
* Device-side services: each new unit is inert without its flag; `systemctl
  disable --now` removes it.

---

# Round 30 rewrite: CONFIRMED / CORRECTED / OPEN / NEXT

test-194 changed the evidence base. A console-silence episode that looked exactly
like a wedge turned out to be a quiet healthy boot, so nothing may be concluded
from console silence, a stale panel, a failed ssh or a lone `frame done timeout`.
The rule this section enforces:

> First prove this is the same boot and that it really is a wedge. Only then ask
> which driver caused it.

## CONFIRMED

**test-194 is a false-positive console-silence episode.** Boot `0f056455` printed
one `frame done timeout` at 8.623 s, went silent on COM19 for 160 s, held a stale
panel and refused ssh. Its journal ran 1111 lines to 6.76 s, its pstore console
shows the kernel alive at 170.26 s ending in a clean restart, and
`soft lockup` / `hung task` / `rcu stall` / `Kernel panic` / `nmi_unresponsive`
are all **0**. A quiet kernel with `consoleblank=0` looks frozen because it has
nothing to print. `reference/boot-tests/test-194-20260925T0906Z/`

**Console silence is not a stall.** Nor is a stale framebuffer, a failed ssh, a
transient ICMP loss, or a lone `frame done timeout`. All five were present in
test-194 together and the boot was healthy. Each is `SUSPECT`, never `WEDGE`.

**The ttyGS console does carry kernel text, after enumeration.** test-194's own
capture carried the frame-done line; `console_kernel_lines` reported 0 only
because the pattern was anchored on `^\[` against lines prefixed
`<host ts> RECV  [`. Early output never appears there, later lines do.

**ttyGS serial BREAK SysRq is unavailable, settled.** The adapter refuses
`BreakState`, and `serial_core.c`'s SysRq path applies to `uart_port` consoles,
not a gadget tty. `sysrq_serial_sequence` is a compile-time Kconfig string. **So
pstore is the only instrument that survives a stall.**
`scripts/sysrq-over-console.*` now refuses by default with exit 3.

**A real CPU-level wedge exists and is reproducible (test-195).** One baseline
round produced, in its own pstore: `rcu_preempt detected stalls` at 28.839 s,
`Sending NMI from CPU 7 to CPUs 6` at 28.844 s,
`soft lockup - CPU#5 stuck for 26s` at 33.127 s,
`Kernel panic - not syncing: softlockup: hung tasks`, and
`SMP: failed to stop secondary CPUs 3,6-7`, with the victim chain
`toggle_allocation_gate -> jump_label_update -> kick_all_cpus_sync ->
smp_call_function_many_cond`. `reference/boot-tests/test-195-20260925T1023Z/`

**And it is provably one round.** The harness writes
`GTS9_AB run/profile/round/boot_id` into `/dev/kmsg` and `/dev/pmsg0` before each
reboot; the next boot reads both back. test-195 carries
`identity=GTS9_AB run=verify1 profile=baseline round=1 boot_id=6d8b975c` and the
device's pmsg holds the same string.

## CORRECTED

* **"COM19 carries zero kernel lines"** — withdrawn. It carries them after USB
  enumeration; the claim came from a broken regex.
* **"frame timeout + console silence = stall"** — withdrawn. That is `SUSPECT`.
  `WEDGE` requires a wedge-class marker or an unrequested restart, bound to the
  round's boot.
* **"The console line never entered the printk ring"** — withdrawn. *Not in the
  journal*, *not in `/dev/kmsg`* and *not in the printk ring* are three different
  claims and only the first is supported: `0f056455`'s journal stops at
  6.763559 s, so the line had no journal to appear in. Level is not the
  explanation either — `DPU_ERROR_ENC_RATELIMITED` is `pr_err_ratelimited`.
* **test-194's own boot identity** — the first pass analysed `846e17b8` (round
  **4**'s result), not `0f056455` (round 5's). Bound by a two-clock offset.
* **The panel photo is a different boot.** Every line in it binds to the 04:57Z
  pstore record: 15 frame-done events at a 1.184 s cadence from 6.755 s, `mmc1`
  at 21.987 s, `AMC RPMH` at 24.487 s. A **flood**, not test-194's single event.
  Its boot id is unrecoverable, because a boot that dies at ~7 s leaves no
  journal. The `17.887 - 10 = 7.887 s` inference is **withdrawn**.
* **The harness's automatic-restart detector had never worked.** `klog-watch` is
  not a valid bash identifier, so the assignment was a command-not-found and
  `"$klog-watch.txt"` expanded to a nonexistent path. **`presence_outages=0` in
  the test-193 records means the check did not run**, not that no restart
  happened.
* **Necessary vs sufficient.** Panic, RCU stall and NMI non-response are strong
  discriminators in every *completely captured* CPU-level wedge on record. They
  are **not** necessary conditions: a detector may not get to run, pstore can be
  lost, an external reset can land before a threshold — and test-195 is a genuine
  wedge that carries `Sending NMI` but **not** the `haven't responded` line,
  because the state came out through the RCU stall instead.

## OPEN

* **Why does test-194's journal stop at 6.76 s** while the kernel runs to 170 s?
  This is the same stoppage `FAILED-BOOT-20260925T0457.md` §4 records for a boot
  that wedges at ~7 s, and it makes such a boot invisible to every journal-based
  instrument — including the 88-boot survey the rate table is computed from.
* **Is the panel photo's boot the same as any recorded failure?** Its boot id is
  unrecoverable; the sequence is real but nothing binds it to a round or kernel.
* **What is a real wedge's earliest invisible event, now bracketed to ~1.3 s?**
  The onset is **~6.5-7.8 s** by two independent timers (test-195 and test-197,
  subtracting the 26 s soft-lockup duration and the 21.02 s RCU stall timeout),
  and **nothing is logged there**. test-197's kernel ring holds exactly two
  messages between 4.6 s and 29 s - both userspace stage markers at 6.52 s and
  6.88 s - and a clean round's window is equally quiet, so the window's contents
  do not discriminate. test-192's `loglevel=7` profile exists, unflashed, and it
  is now the cheapest way to see whether anything is printed between those two
  stage markers and the RCU stall.
* **Do the three old markers matter at all on this kernel?** `frame done timeout`,
  `mmc1: Timeout` and `AMC RPMH` are absent from both wedges captured on the
  flashed kernel, after being present in 3 of 3 older records. Either the older
  association belonged to the pre-`epss_l3` kernel, or it was an artefact of
  reading a flood of DPU messages as a sequence. `PHOTO-EVIDENCE-TABLE.md` shows
  the old records had a 15-event frame-done *flood*; the new ones have none.
* **Is the RPMh timeout a cause or a victim?** §6b of the lifetime analysis: the
  10 s arithmetic fits 04:57Z (implied vote 14.804 s, consistent with the 14.31 s
  deferred-probe burst) and **does not** fit 06:00Z or 06:59Z — one of three. And
  `matched_done` has **no real value anywhere in the repository**.
* **Is the GPU involved?** Untested. Profile C has never been run correctly: the
  old profile named a parameter that does not exist, so it would have been a
  no-op. Profile, parameter guard and run identity are now in place; the flash has
  not happened.

## RESOLVED IN ROUND 31: the GPU direction is out

**Profile C ran and wedged identically with the Adreno driver never registered**
(`reference/boot-tests/test-198-20260925T1235Z/`). Same canary, same victim chain,
same `SMP: failed to stop secondary CPUs 0,3,6-7`, on a boot whose own kernel ring
has **zero** GPU init lines - against a baseline wedge that has one. The four-gate
ablation check passed before the run and the wedged boot confirms it independently.

By this plan's own rule, **the GPU / GMU / AOSS / ACD path is downgraded**: it is
not necessary for the wedge. Three clean rounds then a wedge, the same shape and
apparently the same rate as baseline - removing the GPU changed neither the failure
nor its frequency.

That also closes two open questions above:

* "Do the three old markers matter on this kernel?" - **yes, and they are not
  GPU-dependent.** This is the first record since the old era carrying all three:
  `AMC RPMH` x2 (first 17.65 s), the frame-done flood x7 at a 1.22 s cadence
  (18.73 s) and `mmc1` (23.27 s, with the SDHCI dump). The two baseline wedges had
  none of them, so the kernel's marker set is broader than either record showed.
* "Is the GPU involved?" - **no**, in the only sense that matters here.

**The onset check holds a third time**: soft lockup 32.804 - 26 = **6.80 s**, RCU
stall 28.307 - 21.02 = **7.29 s**, landing in the same ~6.5-7.8 s band as both
baseline wedges. And `AMC RPMH` at 17.65 s is ~11 s *after* that onset, so it is
not the trigger either - it is a consequence, like every other marker so far.

**What is left, and it is what the cluster has in common:** the RPMh/RSC path, the
SD controller (`mmc1`), the display commit path, and whatever those three share -
power, clocks, and the RSC itself. The next ablation should remove one of *those*,
and the only remaining command-line-scale candidate is the display: there is no
`msm.no_dpu`-style token, so that would need a DTS or config change rather than a
profile, which puts it beyond this round's boundary.

## RESOLVED IN ROUND 32: the RPMh timeout branch is out too

**The `gts9_rpmh_debug=1` run produced the pre-registered last row**: a wedge with
`wedge_markers=7` and **zero** RPMh output in every channel
(`reference/boot-tests/test-199-20260925T1314Z/`). Per the rule written before the
run, *no RPMh output at all, and the stall still happened* means **the stall did
not go through an RPMh timeout** - the RPMh direction is downgraded for this
failure mode.

This rests on the switch having been proven live first, because `0021` prints only
on a timeout and has no runtime handle, so a quiet run is otherwise
indistinguishable from a dead switch. The arming gate shows the token on the
cmdline, every A/B token absent (it ran alone), and the token **absent from the
kernel's own unknown-parameter list** - proof an `early_param` handler consumed it.
All 14 dump strings are `pr_err`, so the ring would have kept them at `loglevel=4`.

The victim's stack carries no RPMh path either: `toggle_allocation_gate ->
static_key_enable -> arch_jump_label_transform_apply -> kick_all_cpus_sync ->
smp_call_function_many_cond`, with no rsc, rpmh, bcm or interconnect frame. That
does not falsify `0021`'s hazard - it never fired, so it was never tested - but the
timeout branch is out as an explanation for this failure mode.

Two things this closes and one it opens:

* **the RPMh/RSC direction is downgraded**, alongside the GPU;
* **the canary is confirmed as reporter, not cause** - fourth record, and here it
  is the *entire* trace;
* **but the cause is still not identified.** Four wedges, four victim CPUs
  (5, 2, 2, 4), one repeated canary, and the onset is consistently **~7-8 s** by
  the RCU timer (7.13 / 7.74 / 7.29 / 7.58 s). Nothing is logged there on any boot.

Note the soft-lockup timer is the less reliable of the two now: test-199 reported
`stuck for 56s` rather than 26 s, i.e. on its *second* pass, so its onset figure
reads 8.75 s while the RCU figure reads 7.58 s. **Use the RCU timer.**

## NEXT PHYSICAL TEST

**1. Baseline sanity run with the fixed harness — DONE (test-197).** No flash
needed. The identity marker, the verdict field and the repaired restart detector
all worked: 3 rounds `verdict=clean` with `presence_outages=1`, then round 4
`verdict=wedge` with `presence_outages=2`, evidence preserved automatically and the
series stopped itself. Two wedges are now on record from this harness
(test-195, test-197) plus test-193's five clean rounds.

**2. Profile C: `msm.skip_gpu=1` — DONE, and the GPU is out.** See the section
above and `reference/boot-tests/test-198-20260925T1235Z/`. A genuine CPU-level
wedge occurred with the GPU never registered, so the path is **downgraded**: it is
not necessary for the wedge.

The rule for any future ablation still stands, and it cuts both ways: a genuine
CPU-level wedge bound to the round downgrades that subsystem, while a clean series
records `not reproduced in N rounds` and must never be written as "GPU excluded".
Five clean rounds would not have excluded the GPU, and this run is the reason the
rule exists - it is the wedge, not the clean rounds, that settled it.

**3. Preserve pstore the moment a wedge appears.** Only one of the records so far
was captured before the ring was overwritten.

**4. `gts9_rpmh_debug=1` as a separate diagnostic run, only if warranted.** The
switch is already in the flashed kernel (`early_param`, cmdline only), so this is
one `vendor_boot` flash and no backport. Run it **alone** — never alongside
`msm.skip_gpu`, `msm.disable_acd`, `deferred_probe_timeout=300` or
`cpuidle.off` — and read it against the pre-committed
`RPMH_DEBUG_DECISION_RULE.md`.

## NOT THIS ROUND

No kernel change follows from test-194; it is a measurement correction, not a root
cause. Specifically not: DPU timeout, MMC driver, RPMh timeout, regulator, clocks,
IRQ, cpuidle, watchdog threshold. Any of those would be a driver fix built on a
console line, which is the reasoning this document exists to stop.

