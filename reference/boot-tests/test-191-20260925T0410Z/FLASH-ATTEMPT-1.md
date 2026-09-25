# Flash attempt 1: the tablet wedged on the way to recovery, and the watchdog did not save it

**Nothing was flashed. No partition was written.** The run stopped before
`flash-profile.sh` could reach a recovery prompt. This file records what happened,
because the failure is more informative than the flash would have been.

## What was attempted

1. confirmed the test-191 bundle is intact (`sha256sum -c SHA256SUMS`, all five
   images OK) and the tablet healthy: `boot_id=b0237b3d`, uptime 3852 s,
   **`policies=0`** — the cpufreq absence the test exists to change;
2. `/usr/local/sbin/gts9-debian-to-recovery --check` — resolved `misc` as
   `/dev/sda10`, BCB command empty, no change made;
3. `gts9-debian-to-recovery --yes` at ~06:00Z: *"BCB written to /dev/sda10 and
   verified: boot-recovery"*, then an ordinary restart;
4. polled adb for 3 minutes — **no recovery, no device at all**;
5. probed over COM17 at 06:07:10Z: the heartbeat echo came back, the command's
   *result* never did;
6. probed again at 06:07:24Z: **no heartbeat in 45 s**, and at 06:08:17Z the
   serial **write itself timed out** (`WriteLine` timeout) — the gadget stopped
   accepting data from the host.

## What that means

The tablet booted mainline, not TWRP: COM17/COM19 exist only because our Debian
`gts9-usb-acm` service created that gadget, and TWRP does not run it. So ABL
either ignored the `boot-recovery` request or the initramfs cleared it — both are
documented, benign outcomes of the BCB path.

Then it wedged, and **the operator reports the screen showing a reboot message
with a stuck cursor and a dead keyboard, and that it did not restart.**

That is the fourth independent instance of the documented shape
(`docs/CPU_WEDGE_EVIDENCE.md`): a boot that reaches userspace, stops answering,
and leaves the kernel echoing characters on a tty while nothing executes. The
06:07:10 probe is the cleanest example yet of the *signature itself* — echoed, not
executed — because it was taken with a host-side timestamp and no capture bias.

**Onset is not measured.** The gadget is created by userspace at roughly 6.5 s, so
a wedge at ~7 s would leave COM17/COM19 enumerated exactly as observed; a later
wedge would look the same. Without a console capture for this boot the onset
cannot be narrowed, and it is not claimed.

## The important new fact: the recovery guarantee is not reliable

The brief's standing assumption — item 6 of its retained conclusions, and
`AGENT.md` — is that a stall produces:

```text
stall -> panic -> panic=10 -> automatic restart
```

**This boot did not restart.** It sat wedged until the operator forced a power
cycle. In the previous instance (2026-09-25T04:57Z) it did restart, because CPU 4
was still taking its hrtimer interrupt and `watchdog_timer_fn` ran there; the
recovered record shows exactly that, and shows the panic path then **failing to
stop CPUs 0, 3, 6 and 7**.

So there are two severities of the same failure:

| | watchdog fires | outcome |
|---|---|---|
| 2026-09-25T04:57Z | yes, on CPU 4 | panic at 32.3 s, restart at ~45 s, unsaved work lost but the boot ends |
| 2026-09-25T06:0xZ | **no** | wedged indefinitely; only a forced power cycle recovers it |

This matters operationally and for the round's own rules: `docs/GPU_GMU_RPMH_STALL_PLAN.md`
§14 lists "the watchdog guarantees automatic recovery" as a precondition for
starting the RPMh debug backport, and **that precondition is now falsified**. Any
future unattended A/B series on this device must assume it can stop and stay
stopped, and must be attended.

## What survives, and what does not

* **nothing was written to the tablet's partitions** other than the 2048-byte BCB
  in `misc`, which is what the recovery path is for and which the next mainline boot
  clears;
* the rollback pair is untouched:
  `/home/ms/Samsung/gts9-flash-tests/test-187-baseline/{boot,vendor_boot}-before-baseline.img`;
* the bundle is untouched and still verifies;
* **this boot's console is probably lost.** Nothing was holding COM19, so there is
  no capture, and no panic means nothing flushed the ramoops console region — its
  contents after a forced power cycle are cache-dependent and may be truncated or
  absent. The next boot's pstore should be checked immediately anyway, and
  `gts9-prev-boot-evidence` now reads the right directory;
* the previously recovered failure record is safe: it is committed to this
  repository and archived on the tablet's rootfs, which TWRP does not touch.

## What to do next

1. **force a power cycle** (hold the power key until the panel goes dark, then
   release; the standard hardware reset). The BCB may still hold `boot-recovery`,
   in which case the next boot lands in TWRP — check `adb get-state` first, and if
   it says `recovery`, go straight to `flash-profile.sh`;
2. if it boots Debian instead, the flash needs TWRP entered by hand: **hold Volume
   Up during power-on**, which `docs/REBOOT_MODES.md` records as the manual path;
3. before any further automated reboot series, decide how to handle the "no
   watchdog" variant, because a series that assumes recovery will silently stop.
