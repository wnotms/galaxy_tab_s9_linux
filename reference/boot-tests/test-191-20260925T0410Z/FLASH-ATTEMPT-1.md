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

## 8. Addendum: the kernel is alive. Only userspace and the console are blocked.

Everything in section 7 said the tablet was wedged and needed a forced power cycle.
That is still true operationally, but the *reason* was wrong, and the correction
matters for every conclusion this project has drawn from console or journal silence.

Host-side probes against the same tablet while it sat there with a stuck cursor and
a dead keyboard:

| probe | result |
|---|---|
| NCM adapter | **Up, 426 Mbps** |
| ARP for `169.254.42.1` | **Reachable**, MAC `1A-98-27-23-AE-CB` |
| ICMP echo | **3/3 replies, 2 ms, TTL 64** |
| TCP 22 | refused |
| console write | `WriteLine` timeout - the host cannot write to the port |
| console command result | none |

**The kernel is running.** Its USB gadget is enumerated, its network stack answers
ARP and ICMP, at 2 ms, repeatedly. What is dead is userspace (no sshd) and the
console path (host writes to the CDC-ACM endpoint time out).

### Why this had to be nailed down before anything else

Console, journal and ssh are the only three instruments this project uses, and the
failure breaks all three *by construction*:

* **ssh** needs userspace, which is exactly what stops;
* **the console** needs `/dev/console -> tty0 -> fbcon -> DRM` and the gadget, which
  test-184 already showed can back up;
* **the journal** needs the microSD path, which the recovered 04:57Z record shows
  timing out.

None of them is a liveness test, and all three failing together looks identical to a
death. `scripts/gts9-kernel-alive.sh` now separates them: link, ARP, ICMP, ssh and a
console command that must *execute*, reported as a pair rather than one state.

```
link=up  arp=reachable  icmp=1  ssh=down  console=blocked
kernel=alive  userspace=blocked
```

### What it does and does not invalidate

* **does not invalidate the 04:57Z CPU wedge.** That boot had two independent
  measurements of unreachable CPUs - `SMP: failed to stop secondary CPUs 0,3,6-7`
  and an RCU stall naming CPU 0 - and its panic was recorded. That was a real CPU
  event;
* **does invalidate the inference from silence alone.** "The console stopped and the
  journal stopped" has been read as "the machine stopped executing" in several
  rounds, including in this document's own section 1. The two are now known to be
  different, because a live kernel was measured presenting exactly that way;
* **it reframes the 06:0xZ episode** as a third variant: kernel alive, userspace and
  console blocked, screen showing a reboot message, no restart. It is not the
  04:57Z wedge and it is not a normal boot;
* **it is a warning about the survey.** A boot in this state leaves no journal and
  no panic, and if a human power-cycles it, the survey records only "no orderly
  shutdown". Those boots may never have had a CPU wedge at all.

### Operational consequence

A power cycle is still the only way back, because with the console blocked there is
no shell to type into and no sshd to connect to. But "the tablet is dead" is no
longer an acceptable shorthand, and `gts9-kernel-alive.sh` should be run before any
future forced reset so the state is recorded rather than assumed.
