# Test 226 — the `cpuidle.off=1` gate: artifacts, flash plan, verdict rule

**Status: prepared, not flashed.** Nothing in this repository has touched the
tablet. This directory holds the identity of the candidate and the exact
procedure for the on-device run; the run itself has not happened, so this file
contains no result and must not be cited as one.

Read this together with `docs/CPU_IDLE_WEDGE_PLAN.md`, which holds the
pre-registered decision rule. That rule was committed *before* this candidate
existed and must not be adjusted now.

## 1. What this test asks

One question: **is the cpuidle framework necessary for the CPU wedge?**

If a single genuine wedge occurs with `cpuidle.off=1`, the answer is no, and the
whole PSCI-idle direction is downgraded. If the profile runs clean, the answer
is *not* yes — it is only `not reproduced in N boots`, because zero of ten
clean boots would happen 71% of the time even if nothing had changed.

## 2. Identity of the candidate

| field | value |
|---|---|
| repo commit | see `source-commit.txt` |
| upstream kernel | `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (v7.2-rc3) |
| `kernel.release` | `7.2.0-rc3-gts9wifi-dirty` |
| profile | `cpuidle-off` — `boot/cmdline.stall-ab-cpuidle-off.example.txt` |
| reboot kind | **warm** (`systemctl reboot`), per the harness |

### Artifact hashes

```
Image.gz          f74728727418cc83d051dea18af1ec3763f5619785486a9106426ea50d2e0c66
board DTB         eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0
kernel config     42e37409887a1614467454f3a47c17a586b9fb67ef7f0d5003943803627889e9
```

Bundle (`out/boot-bundle-cpuidle-off/`, also in `bundle-SHA256SUMS`):

```
boot.img          71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d
vendor_boot.img   1245bb39be1a6cfd65e381e44d19ce4ab29ca295f976f0c78067e4bfecc5b18a
init_boot.img     1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0
dtbo.img          c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
vbmeta.img        b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4
```

`BOOT BUNDLE VALIDATION PASSED` with
`--cmdline boot/cmdline.stall-ab-cpuidle-off.example.txt`.

## 3. Flash scope: `vendor_boot` only

This is a **one-partition** delta, and that is worth verifying rather than
trusting. Four of the five images are byte-identical to what the tablet is
already running:

| partition | candidate | on the tablet now | identical? |
|---|---|---|---|
| `boot.img` | `71e194a5…` | `71e194a5…` | **yes** |
| `dtbo.img` | `c17418be…` | `c17418be…` | **yes** |
| `init_boot.img` | `1a8c7148…` | `1a8c7148…` | **yes** |
| `vbmeta.img` | `b95e5ef9…` | — | not written by this test |
| `vendor_boot.img` | `1245bb39…` | `49ae21b3…` | **no — this is the delta** |

The tablet's current state is taken from the committed records of test-214
(`boot`, `vendor_boot`, `dtbo`: the prime-OPP deployment) and test-216
(`init_boot`: the RTC-offset deployment), which are the last flashes that
touched these partitions. `sm8250`-style assumptions do not apply here: the
`init_boot` on the tablet is **newer** than the one inside the older
`boot-bundle-opp`, and reusing that older one would have introduced a second
variable (it predates the RTC fix). The candidate therefore carries the
device's own ramdisk forward byte-for-byte.

**Flash `vendor_boot` and nothing else.** Writing `vbmeta` is unnecessary and
must not be done; the existing device `vbmeta` is kept, as the validator's own
warning says.

## 4. Verification commands, in order

Run all of these from the Debian userspace over ssh after the flash. The first
two are the arming gate and they must be read **before** any round is counted —
`scripts/stall-ab.sh` refuses to run otherwise.

```bash
# 1. the token is really on the command line
grep -o 'cpuidle\.off=1' /proc/cmdline

# 2. the framework is really off -- and NOTE THE DIRECTION
test -d /sys/devices/system/cpu/cpuidle && echo "RUNNING (bad)" || echo "ABSENT (good)"
cat /sys/devices/system/cpu/cpuidle/current_driver    # expected: No such file

# 3. the governor never registered, on the boot under test
journalctl -b -1 -k --no-pager | grep -c 'cpuidle: using governor'   # expected: 0
journalctl -b  0 -k --no-pager | grep -c 'cpuidle: using governor'   # expected: 0

# 4. no CPU suspend is happening, and no state entry is being refused
cat /sys/kernel/debug/psci
cat /sys/kernel/debug/pm_genpd/power-domain-cluster/idle_states
```

**Why step 2 is checked by absence and not by content.** Under `cpuidle.off=1`
the file `/sys/devices/system/cpu/cpuidle/current_driver` **does not exist**:
`cpuidle_init()` is a `core_initcall` that returns `-ENODEV` before
`cpuidle_add_interface()` runs. A check written as
`cat .../current_driver` would therefore report a failure on a perfectly armed
profile. Its *absence* is the positive signal.

The run itself:

```bash
GTS9_ALLOW_POWER=1 scripts/stall-ab.sh cpuidle-off 10
```

The harness prints the arming gate verdict before round 1 and refuses to
continue if it does not pass. Treat a gate failure as **no data**, not as a
result: fix the profile and re-run, and do not count those boots.

The probe now also records, for every round, the per-CPU
`state*/usage` and `state*/rejected` counters and the cluster domain states
with their `Rejected` column. Those are mandatory evidence, not decoration —
a failed PSCI `CPU_SUSPEND` prints nothing at all, so the counters are the only
signal it happened.

## 5. Expected results

| observation | meaning |
|---|---|
| `cpuidle_sysfs=ABSENT`, `cpuidle_gov_boot=0`, `cpuidle_driver=NONE` | **armed.** Any other combination is a profile failure, not a result |
| `psci_caps` shows `OSI is supported` and `Extended StateID format` | expected; the domain topology is still created, only the idle entry is removed |
| `psci_domain_idle_enter` tracepoint shows **no entries** | confirms no `CPU_SUSPEND` was issued. Only meaningful if a trace run is done; the counter check above is sufficient for this profile |
| `state1/usage` frozen, or the path absent | expected |
| a `state*/rejected` count that keeps rising | a state entry is being refused — record it, it is a finding about the *other* profiles too |

## 6. How a wedge is judged

**Unchanged from the existing harness, and deliberately not relaxed.**
`docs/CPU_WEDGE_EVIDENCE.md` and test-194 established the rule:

* **`WEDGE`** requires a wedge-class marker bound to the round's own boot —
  `rcu detected stall`, `soft lockup`, `BUG: workqueue lockup`, an
  unanswered-backtrace line, or `Kernel panic` — **or** an unrequested restart
  (a second USB-presence outage in the round's console capture).
* **`SUSPECT`, never `WEDGE`**: a lone `frame done timeout`, a lone `mmc1:
  Timeout`, a lone `AMC RPMH` timeout, console silence, a stale framebuffer, a
  failed ssh, a transient ping loss. Test-194 had all five at once and was a
  healthy boot.
* **`encoder is disabled`** fires once on every healthy boot. It is never an
  anomaly.
* **`unattributed`** — no identity binding, or a failed probe — counts in
  neither direction and does not advance `n`.

On a wedge, preserve immediately from the tablet: `/var/lib/systemd/pstore/`
(`console-ramoops-0`), `journalctl -b -1 -o short-monotonic`, the console
capture, `/proc/interrupts`, `/proc/softirqs`, and the cpuidle snapshot from
§4. Do not overwrite an older test directory.

## 7. Recovery

* **No wedge:** the harness issues only `systemctl reboot`. To return the tablet
  to the pre-test state, flash back the previous `vendor_boot.img`
  (`49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9`). Nothing
  else was changed.
* **Wedge:** the hardware itself is fine — the tablet is alive, userspace is
  frozen. Hold the power key, which the PMIC answers (demonstrated on the
  test-219 wedge). With this profile `panic=10` and `softlockup_panic=1` are
  present, so a soft-lockup wedge is detected and reboots itself; that is the
  profile's own recovery mechanism and is expected to fire about 30 s after the
  onset.
* **The tablet does not come back:** it has not been repartitioned and
  `vbmeta`/`recovery`/`userdata` were never touched, so a normal ABL boot or a
  TWRP boot is unaffected. Restore `vendor_boot` from the hash above.

## 8. Decision rule — see `docs/CPU_IDLE_WEDGE_PLAN.md` §5, do not re-derive it

In one line each:

* **any `k ≥ 1`** with CPU-level evidence → `the full cpuidle framework is not
  necessary for the wedge`; **stop this direction**, do not run the cluster
  profiles, go to the plan's §7.
* `n = 10, k = 0` → `not reproduced in 10 boots`. Extend to 30. Ten clean boots
  are **no evidence at all**: 0 of 10 has a 71% probability under the existing
  3.4% rate.
* `n = 60, k = 0` → `not reproduced in 60 boots`, a bound and **not** a fix.
  Only the restore experiment in the plan's §6 could make it `necessary`.

**Forbidden at every sample size:** `fixed`, `solved`, `root cause confirmed`.

## 9. What must be committed afterwards

Per `AGENT.md`, whatever happens — including a wedge, a failed flash or an
aborted run — gets a committed directory with the raw logs, the flash
read-back transcript, the artifact hashes, the source commit and an
observation README. A series that produced `unattributed` rounds must say so
rather than showing a table that looks clean.

## Related

* `docs/CPU_IDLE_WEDGE_PLAN.md` — the rule, the profiles, the open questions
* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — what each state is, and why the
  per-CPU ablation cannot be built
* `docs/X710_X910_CPUIDLE_DIFF.md` — the config diff
* `reference/boot-tests/test-214-galaxy-prime-opp/` — the `boot`/`vendor_boot`
  state this test starts from
* `reference/boot-tests/test-216-rtc-offset-flash/` — the `init_boot` state
