# The RPMh debug run: what each outcome will mean, decided in advance

Round 29. Written **before** the run, for the same reason
`WEDGE_RATE_DECISION_RULE.md` was: a reading chosen after seeing the output is
not a reading. Nothing below is adjusted afterwards; if the result disagrees with
the table, the table stands and the disagreement is written down.

## What the run is, and what it is not

**It is a cmdline-only run.** `gts9_rpmh_debug=1` is an `early_param` that is
already compiled into the flashed kernel
(`docs/RPMH_RSC_DEBUG_PATCH_STATUS.md` §5a, verified by hash), and
`boot/cmdline.rpmh-debug.example.txt` plus
`out/boot-bundle-rpmh-debug/vendor_boot.img` already carry it. No kernel change,
no backport, one `vendor_boot` flash.

**It is not an A/B round.** Patch `0021` adds a bounded ring and one branch on the
send and completion paths, and on timeout it dumps registers. The three A/B
profiles forbid `gts9_rpmh_debug` by name for exactly that reason. Its numbers
cannot be compared against the A/B series, and must not be.

**Expressed as a rule: `gts9_rpmh_debug=1` must not be enabled during an A/B
round.** It runs alone or not at all - never alongside `msm.skip_gpu`,
`msm.disable_acd`, `deferred_probe_timeout=300` or `cpuidle.off`. The profile is
one token from baseline (`gts9_rpmh_debug=1` and nothing else), so the ablation is
the switch itself and no comparison against an A/B series is possible or wanted.

**And the switch has to be provably alive.** `0021` prints only when a timeout
happens and exposes no sysfs or debugfs handle, so a round that captures no dump
cannot be told from a kernel that has no such switch. The harness therefore reads
the kernel's own `Unknown kernel command line parameters` list: a token with no
consumer appears there, which means the switch is dead and every round of that
profile would be unfalsifiable. Measured on this kernel, `gts9_rpmh_debug` does
**not** appear in that list, while `gts9_watchdog_debug` does - and the latter is
consumed by `rootfs-overlay/usr/libexec/gts9-watchdog-debug`, a userspace reader,
which is why a userspace allowlist is part of the check.

**It only speaks when something times out.** `0021` prints nothing on a healthy
boot. So a run that captures no timeout is not a null result about the machine -
it is a statement about the sample, and it needs the same denominator discipline
as everything else here.

## The pre-registered reading

`0021` prints a `ring_summary` line that already ends in one of three verdicts, and
a separate `LATE COMPLETION` line. The mapping to the brief's type A / B / C is
direct, and the verdict strings below are quoted from the patch:

| what the capture says | type | what it means | next step |
|---|---|---|---|
| `ring_summary ... matched_send=1 matched_done=0 => this request was programmed but never completed: look at RSC/TCS/IRQ` | **A** | the TCS was written and triggered, the RSC never answered | AOSS / RPMh hardware / the resource vote / power-domain state. Compare with X910. This is the hardware-or-firmware branch |
| `irq_status` has the done bit **set** while the request is still `in_use`, and no `LATE COMPLETION` follows | **B** | the response was ready and the IRQ is pending, but the handler did not run | IRQ delivery / CPU lockup / scheduler / masked interrupts. RPMh is then a **victim**, and the search moves to whatever stopped the CPU from taking the IRQ |
| `ring_summary ... matched_send=1 matched_done=1 => completion was seen: look at completion/lifetime handling` | **C** | `tcs_tx_done()` ran; the caller timed out anyway | request and completion lifetime - `RPMH_TIMEOUT_LIFETIME_ANALYSIS.md` §4, `rpm_msgs[]`, `compls[]`, `tcs->req[]` |
| `gts9-rpmh: LATE COMPLETION for a request that already timed out ... - the rpmh_write_batch() lifetime hazard is real` | **C, confirmed** | a completion arrived **after** `kfree(ptr)` and wrote through the freed `struct completion` | the §4 hazard is live and is a memory-corruption mechanism, not a theory. §7 of that file lists the candidate repairs, none endorsed |
| `ring_summary ... matched_send=0 => no matching send in the ring: it did not reach TCS programming` | not in the brief's list | the request never reached programming - the TCS claim or the send path failed | TCS availability and `rpmh_rsc_send_data`, not the RSC |
| no RPMh output at all, and the stall still happened | - | the stall did **not** go through an RPMh timeout | the RPMh direction is downgraded for that failure mode, and the display/`mmc1` common denominator becomes the object of study |

Two details that decide which row applies and are easy to miss:

* **`matched_done` is the field that has never been measured.** Every existing
  value for it in this repository comes from a synthetic fixture
  (`reference/boot-tests/test-186-*/fixtures/`, which carries a
  `NOT-DEVICE-EVIDENCE.md` banner). Its real value is the run's main product.
* **The real instance to compare against is test-183**, not the fixture:
  `+14.273790 s`, `rpmh.c:386`, `Workqueue: events pogo_watch_work`, then five
  minutes of silence. The caller chain is the interconnect BCM voter
  (`bcm-voter.c` is the only direct caller of `rpmh_write_batch()` in-tree), so
  the request to look for is an **interconnect bandwidth vote**, at ~4.27 s.

## How long to run, and when to stop

The RPMh timeout is 10 s (`RPMH_TIMEOUT_MS`), and the A/B series' failure rate is
2 in 29 warm reboots. At that rate a timeout should appear within ~15 rounds; the
rule is therefore:

* **stop at the first RPMh dump** and read it against the table. One dump is worth
  more than the rest of the series, because it is the only state snapshot the
  suite can produce;
* **if 20 rounds pass with no dump and no stall**, record that as "no RPMh timeout
  in 20 rounds with the detector armed" - which is bounded evidence against the
  timeout-triggered branch, not proof;
* **if a stall happens with no dump**, that is the last row of the table and is
  itself a result: the failure did not go through this path.

Because the switch is invasive and the run is not an A/B, the harness's
`stall-ab.sh` profile list must not be extended with it. It needs its own run,
with the observer-effect rule stated in its record.

## What would falsify the hazard

Stated in advance so it cannot be quietly dropped:

1. **A dump showing `matched_send=1 matched_done=1`** - the completion was seen
   before the timeout path ran, so the free is not a use-after-free on that
   occasion, and the C branch's mechanism is not what stalled the machine.
2. **Twenty rounds with no dump at all.**
3. **A `LATE COMPLETION` immediately followed by no observable damage** - the
   hazard would be real but not, by itself, sufficient to wedge the system, which
   is a narrower claim than §4 currently allows.

## Related

* `docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md` - the hazard, the arithmetic, §6a's real
  instance, and the candidate repairs
* `docs/RPMH_RSC_DEBUG_PATCH_STATUS.md` - the switch, its provenance, and the
  Qualcomm v4 series as the fallback for the fields `0021` lacks
* `docs/STALL_FIRST_EVENT_ORDERING.md` - the marker ordering this run is meant to
  sit underneath
