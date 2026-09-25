# test-192 — make the console able to see the project's own wedge marker

**Status: bundle assembled and validated. NOT flashed.** No partition was written.

## The finding this exists for

`docs/CPU_WEDGE_EVIDENCE.md` defines the failure by one line:

```
After 10 seconds, these CPUS still haven't responded to the NMI: N
```

That line is `pr_warn`, level 4. Every command-line profile in this repository
carries **`loglevel=4`**, which prints only levels 0-3. So on the *console* that
marker has never been visible - and the console is the only instrument that survives
a wedge.

Measured on the failure recovered in round 22
(`reference/boot-tests/test-191-*/wedge-rate-pre-test191-capture/failed-boot-pstore/`):

| source | occurrences of the marker |
|---|---|
| the pstore console record of the failed boot | **0** |
| a journal capture of a wedged boot (`test-178/rcu-stall-backtrace.log`) | 4 |

The journal is unfiltered, which is why the 88-boot survey could count the marker at
all. But a boot that wedges early **leaves no journal** - that is exactly what the
failed boot did - and then the console record is the only evidence there is, and it
is blind to the marker by construction. Every console capture this project has ever
taken has been unable to see the thing it was hunting.

## The change: one command-line token

`boot/cmdline.diag-loglevel.example.txt` is `cmdline.stall-ab-baseline.example.txt`
with `loglevel=4` -> `loglevel=7`. Nothing else: `diff` over the token lists reports
one changed line. The kernel is **not** modified, so this is a `vendor_boot`-only
delta.

**Why 7 and not 5.** Level 5 would already capture the `pr_warn` marker and the
`NMI backtrace for cpu N` headers. Level 7 additionally captures the `pr_info`
`Sending NMI from CPU x to CPUs y:` line, which names the *target* CPU - and the
target is what the cluster-asymmetry finding is made of
(`docs/CPU_WEDGE_EVIDENCE.md`: 13 of 14 targets in big+prime). The usual objection
to level 7 is a `pr_debug` flood, and it does not apply here: `CONFIG_DYNAMIC_DEBUG`
is **not set** (`out/kernel-gts9wifi/config:8581`), so `pr_debug` compiles away
unless someone turns it on with dyndbg. The added output is level-6 `dev_info` probe
traffic, and the ramoops console region is 512 KiB.

**Observer effect, stated rather than glossed.** More console output is not free:
test-184 showed that `/dev/console -> tty0 -> fbcon -> DRM` backlog can itself make
a boot look stalled. So this profile must not be used for A/B stall counting - it is
a *capture* profile. `gts9_kmsg_mirror` and `gts9_dpu_flight` stay off, as before.

## A success criterion that does not need a failure

The ring's first line is bounded by the level filter. The failed boot's record
begins at monotonic **4.435 s** - the first level-3 message - even though the kernel
started at 0. With `loglevel=7`:

* **pass**: the console record begins near monotonic 0 and contains level-6 lines,
  for example the sec-log driver's own
  `gts9wifi-sec-log: persistent console at 0x… (2097152 bytes, boot N, early_initcall)`
  and `Calibrating delay loop …` from the very start of the boot;
* **fail**: the record still begins mid-boot with only level 0-3 lines. Then the
  token did not take, and the reason is a command-line problem, not a kernel one.

`verify-loglevel.sh` checks `console_loglevel` directly and reports which of those
two it sees.

## Files

| file | purpose |
|---|---|
| `candidate.txt` | hashes, flash plan, expected observations, success/failure, rollback |
| `verify-loglevel.sh` | read-only probe: is `console_loglevel` 7, and does the record now carry level-6 lines? |

The flash itself reuses round 20's verified script:

```sh
GTS9_BUNDLE=out/boot-bundle-test192-loglevel \
  reference/boot-tests/test-191-*/flash-profile.sh
```

## Honest limits

* the bundle is `compiled` and `packaged`, not `booted`;
* a `vendor_boot`-only change is one variable *against test-191*, not against the
  image on the tablet today. Flash test-191 first, then this;
* it makes evidence visible. It is not a fix and it does not claim to be one.
