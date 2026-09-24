# Next stall-debug plan: from "13-14 s stall" to a layer in the RPMh chain

Status: **plan of record for test-185 / test-186.** Written before any code of
this phase, so the decision points below cannot be re-interpreted afterwards.

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
| 10 | real stalls cluster at **13.3-14.3 s** after boot | four/five recorded stalls, `docs/DPU_TRACE.md` |
| 11 | the earliest known anomaly in one real failure is an **ACTIVE_ONLY RPMh transaction timeout** | `rpmh_write_batch()` `WARN_ON(1)` at `rpmh.c:386`, 14.27 s into that boot |
| 12 | `pogo_watch_work` was the *caller* of that transaction | same log; the keyboard is docked and healthy in clean boots too |
| 13 | ramoops is registered but no record survives a reboot | test-183/184: `pstore_backend=ramoops-registered`, `pstore_records=0` |
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
