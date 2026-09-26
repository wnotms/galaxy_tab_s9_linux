# Test 228 — the CSD/IPI diagnostic: candidate, arming gate, and the on-device plan

**Status: prepared and built, NOT flashed.** The tablet is at its pre-test state
and no write has been made. This is the round-34 hand-off: everything a physical
run needs is fixed here in advance.

The decision rule is pre-registered in `docs/CSD_IPI_WEDGE_PLAN.md` §4 and was
committed before this candidate existed. It is not re-derived here.

## 1. What this test is for

test-227 removed the last mechanism the project had a name for: with
`cpuidle.off=1` provably in effect and every cluster idle state at usage 0 /
rejected 0, the wedge still happened twice. The open question is now:

> At about 7 s, why does a CPU that Linux still believes is online stop executing
> an ordinary cross-CPU IPI?

`CONFIG_CSD_LOCK_WAIT_DEBUG` instruments the exact wait the canary is spinning in
(`csd_lock_wait()` inside `smp_call_function_many_cond()`), and its first report
fires at **5 s** — before the RCU stall at onset+21 s, while the target CPU is
still wedged. It reports the waiting CPU, the **target CPU**, the CSD function
and argument, and whether the target is handling *this* request, a *prior* one, or
nothing at all.

## 2. The round's success condition

**Not "no wedge".** It is:

> **a real CPU wedge produces more target-CPU / CSD / IPI state information than
> test-227 did.**

test-227 showed 2 wedges in 4 boots is achievable, so the series is expected to
be short. **Stop at the first genuine wedge with usable output.** This is failure
forensics, not a rate experiment — a clean series is `not reproduced in N boots`
and is *not* a result about CSD.

## 3. Candidate identity

| field | value |
|---|---|
| repo commit | see `source-commit.txt` |
| upstream kernel | `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3) |
| `kernel.release` | `7.2.0-rc3-gts9wifi-dirty` |
| diagnostic | **`CONFIG_CSD_LOCK_WAIT_DEBUG=y`** + `_DEFAULT=y` |
| profile | `csd-lock` — `boot/cmdline.stall-ab-csd-lock.example.txt` |
| build method | `KERNEL_CLEAN=1` |

```
Image.gz          87569b85c6f8f9f60a152de6e999bb6f5ac4005c4179e101be013d1a36ec62ce
board DTB         eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0
config            1ea31ba89a2c8829fb5b4016becb7648572bd47ca39af51adbe339b1b7a19832
```

Bundle (`out/boot-bundle-csd-lock/`):

```
boot.img          f0f893c724cf22e99bf0f5e6e883549f847177f74ee298e04a10694b0830b48c
vendor_boot.img   41111e7095de769be4629d6aa7f879a1135f44c282c2d40e3d87f079aedcf7c3
init_boot.img     1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0
dtbo.img          c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
vbmeta.img        b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4
```

`BOOT BUNDLE VALIDATION PASSED` with
`--cmdline boot/cmdline.stall-ab-csd-lock.example.txt --kernel-out out/kernel-gts9wifi-csd-lock`.

**The instrument was verified inside the flashable artifact, not just in `out/`:**
the gzip payload of `out/boot-bundle-csd-lock/boot.img` contains
`csd: %s non-responsive CSD lock` and `smp.csd_lock_timeout`, and the production
bundle contains neither.

### A note on the `Image.gz` hash

`Image.gz` is **not reproducible** by any build method — see the round-34
addendum in `docs/BUILD_REPRODUCIBILITY.md`. The kernel embeds a build timestamp,
so two builds of identical source differ by exactly two strings while every
functional string is identical. `config`, the DTB and `kernel.release` **are**
byte-stable. So the hash above identifies *this built artifact*; it is not
expected to be reproducible from the same source, and a mismatch on a rebuild is
not evidence that the source moved. Compare `config` and the DTB first.

## 4. What the tablet has now, and what to write

Device state, read from the device:

```
boot         71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d
vendor_boot  49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9
init_boot    1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0
dtbo         c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
vbmeta       9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4
```

| partition | write? | why |
|---|---|---|
| **`boot`** | **YES** — `71e194a5` → `f0f893c7` | the diagnostic kernel lives here |
| **`vendor_boot`** | **YES** — `49ae21b3` → `41111e70` | carries the DTB **and** the cmdline with `csdlock_debug=1` |
| `init_boot` | **NO** — stays `1a8c7148` | unchanged, and its ramdisk was carried forward byte-for-byte |
| `dtbo` | **NO** — stays `c17418be` | unchanged; the DTB is identical (`eecc98b8`) |
| `vbmeta` | **NO** | never written by this repository's tests |
| `recovery`, `misc`/BCB, `userdata`, partition table | **NO** | — |

**Both kernel-carrying partitions must be written.** `build-boot-bundle.sh`
appends the DTB to `boot.img`'s payload *and* passes the same file to
`vendor_boot.img`; writing only one would leave the bootloader and the kernel
disagreeing. This was measured in round 33 and is the mistake the corrected
artifact table exists to prevent.

## 5. Arming gate — run BEFORE counting anything

The gate is a **positive capability test**, not an absence test. Both CSD
`module_param`s live inside `#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG`, so their sysfs
files exist *only* in a kernel built with the option. The file appearing cannot be
produced by a stale image or by a cmdline that failed to take — which is what
makes it a real gate.

```sh
# 1. THE decisive check: a capability only the diagnostic kernel has.
ls /sys/module/smp/parameters/
#    production today: EMPTY   (verified on the tablet)
#    diagnostic:       must list csd_lock_timeout and panic_on_ipistall

# 2. the token is on the running command line
grep -o 'csdlock_debug=1' /proc/cmdline

# 3. and a handler consumed it - the same gate the project applies to
#    gts9_rpmh_debug.  A token with no handler stays in this list.
journalctl -b 0 -k --no-pager | grep -a 'Unknown kernel command line parameters'
#    `csdlock_debug` must NOT appear there.

# 4. the instrument is not merely enabled but live
cat /sys/module/smp/parameters/csd_lock_timeout    # expect 5000 (ms)
cat /sys/module/smp/parameters/panic_on_ipistall   # expect 0
```

If (1) is empty or (3) lists `csdlock_debug`, **stop**: the instrument is not
running and any wedge would produce no output for a reason that has nothing to do
with CSD. Per the plan's Case D that is a profile failure, not a result.

## 6. Running it

The host has no COM17/COM19, so use the ssh runner built in round 33:

```sh
GTS9_ALLOW_POWER=1 scripts/wedge-ssh.sh baseline 10     # only to confirm the rig
GTS9_ALLOW_POWER=1 scripts/wedge-ssh.sh csd-lock 10
```

Note: `wedge-ssh.sh` currently recognises `cpuidle-off` and `baseline` as
profiles. Its arming gate will need the CSD checks above added for a `csd-lock`
run, or the gate run by hand from §5 first — **do not skip §5.**

Recovery is unchanged and needs no intervention: `softlockup_panic=1` →
`panic=10` → automatic reboot. An unattended series cannot strand the tablet.

## 7. Expected CSD output, and what each shape means

The first report is this line, and it is the whole point of the round:

```
csd: Detected non-responsive CSD lock (#N) on CPU#<waiter>, waiting <ns> for CPU#<target> <func>(<info>).
```

followed immediately by **one** of:

| second line | meaning | next step (plan §4) |
|---|---|---|
| `\tcsd: CSD lock (#N) handling prior <g>(<j>) request.` | target is inside an IPI handler and not returning | **Case A** — read `g`; nested/circular CSD or a handler that blocks |
| `\tcsd: CSD lock (#N) handling this request.` | target started *this* handler and has not finished | the handler is the object; read `<func>` |
| `\tcsd: CSD lock (#N) unresponsive.` | target is **not** in an IPI handler at all | **Case B** — IRQ masking, GIC/SGI delivery, exception state, arch timer, firmware |

plus, when the target is unreachable:

```
csd: Re-sending CSD lock (#N) IPI from CPU#<waiter> to CPU#<target>
```

**`Re-sending` is a distinct and important fact**: it appears only when
`cpu_cur_csd` is NULL, i.e. the target never *started* the handler. That
separates "started and did not finish" from "never started" — the discriminator
the brief's decision tree keys on.

A `dump_cpu_task()` stack for the target may also appear; it is best-effort,
because it needs the target to take another IPI. **A missing target stack is not
evidence of anything** and must not be reported as such.

Later reports repeat as `Continued` at an increasing interval; the **first** is
the one carrying the state.

## 8. Evidence to preserve the moment a wedge appears

A wedged kernel cannot be interrogated, so capture after the automatic reboot:

| what | where |
|---|---|
| the CSD report itself | `journalctl -b -1 -k -o short-monotonic` — it is `pr_alert`, so it is in the ring |
| the panicked console | `/var/lib/systemd/pstore/console-ramoops-0` (survives the reboot) |
| the whole ring | `journalctl -b -1 -k` |
| per-CPU interrupt and softirq counts | cannot be read from a wedged boot — **do not design a test that needs them** |
| profile identity | `/proc/cmdline`, `/sys/module/smp/parameters/`, the config hash |

Save all of it into a new `reference/boot-tests/test-228-*/` directory, hash it,
and commit. Do not overwrite test-227.

**Onset arithmetic, as always:** RCU stall at `t=5256` jiffies ÷ 250 Hz = 21.02 s,
so subtract that from the RCU report time; the CSD report at 5 s is *earlier*
than that and should appear first.

## 9. If the wedge produces no CSD output at all (Case D)

**Do not write "CSD is not involved."** Confirm, in this order:

1. `CONFIG_CSD_LOCK_WAIT_DEBUG=y` in the running kernel's config;
2. the static key live — §5 checks (1) and (3) both passed;
3. the waiter really is in `smp_call_function*()` with `SCF_WAIT`, as every
   recorded wedge is;
4. the wedge lasted longer than `csd_lock_timeout` (5 s) — every recorded one
   lasted tens of seconds.

Only with all four confirmed may the round move to targeted ftrace
(`docs/CSD_IPI_WEDGE_PLAN.md` §5), and the finding is then "the instrumented wait
was not the one that blocked", not "CSD is uninvolved".

## 10. Rollback

Two partitions to restore, from the hashes in §4:

```sh
dd if=<71e194a5 image> of=/dev/disk/by-partlabel/boot        bs=1M && sync
dd if=<49ae21b3 image> of=/dev/disk/by-partlabel/vendor_boot bs=1M && sync
sha256sum /dev/disk/by-partlabel/boot /dev/disk/by-partlabel/vendor_boot
```

`out/boot-bundle-opp/boot.img` and `out/boot-bundle-opp/vendor_boot.img` are those
images, and a byte-exact copy of the device's own `vendor_boot` is held at
`.work/test-227/vendor_boot-device-before.img`.

Nothing else was written, so no recovery boot, no `vbmeta` write and no
repartition is ever required to revert this.

## Related

* `docs/CSD_IPI_WEDGE_PLAN.md` — the pre-registered rule and the instrument's argument
* `kernel/config/gts9wifi-csd-lock.fragment` — the diagnostic configuration
* `reference/boot-tests/test-227-cpuidle-off-run/` — the result that opened this branch
* `docs/BUILD_REPRODUCIBILITY.md` — why `Image.gz` hashes are build-specific
