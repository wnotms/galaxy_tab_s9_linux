# Round 33 candidate set — status, and why no physical test has run

**Nothing has been flashed. The tablet is not connected to this host.** This file
exists so that the absent result is recorded as an absent result, rather than
leaving a reader to infer from a prepared bundle that a run happened.

## The device is unreachable, checked rather than assumed

| probe | result |
|---|---|
| `adb devices` (host path and Windows path) | *List of devices attached* — **empty** |
| `ping 169.254.42.2` (the USB-NCM address) | **100% packet loss** |
| `Get-PnpDevice -Class Ports` | no COM17, **no COM19** |
| `lsusb` | no Samsung / `04e8` device |

COM17 (shell) and COM19 (console) are the two ports `scripts/stall-ab.sh`
requires; the FTDI adapter that provides them is not enumerated. No Samsung USB
device is present at all, so there is nothing to talk to over adb, NCM or serial.

**Consequence: the on-device halves of round 33 cannot run.** They are
blocked on the tablet being attached — not on anything in this repository.

## What *is* verified, and therefore what is ready

Everything that can be established without the device has been, and the
artifacts that would be written are verified as artifacts:

| check | result |
|---|---|
| `out/boot-bundle-cpuidle-off` bundle validation | **PASSED** |
| `cpuidle.off=1` present in the built `vendor_boot.img` cmdline | confirmed |
| the candidate's `boot.img` appended DTB | `eecc98b8…`, matches `BUNDLE_INFO` |
| the candidate's `vendor_boot` DTB | `eecc98b8…`, **identical to boot.img's** |
| that DTB verified as `baseline` | **PASSED** |
| that DTB rejected as `no-llcc-off` and `no-cluster-idle` | rejected, correctly |
| default build byte-identical to the flashed state | `Image.gz f7472872`, DTB `eecc98b8` |
| host test suite | 886 tests pass |

The DTB check is new: until this session the verifier had only ever been run
against `out/kernel-gts9wifi/*.dtb` and against ablation builds under `.work/`.
Neither is what a flash writes. The flashed tree is the one appended to
`boot.img` and mirrored into `vendor_boot`, and that is now extracted from the
candidate bundle itself, verified, and required to agree between the two
partitions.

## A correction this session produced, which would have broken a real test

The plan's artifact table claimed the cluster ablations change **only**
`boot.img`. **That was wrong, and it was measured.**

`scripts/build-boot-bundle.sh` appends the DTB to `boot.img`'s payload *and*
passes the same file as `--dtb` to `vendor_boot.img`. A real
`GTS9_IDLE_ABLATION=no-llcc-off` build therefore moves two partitions:

```
boot.img         71e194a5 -> 80aa010f
vendor_boot.img  1245bb39 -> e237a98e
dtbo / init_boot / vbmeta                    unchanged
```

Writing only `boot.img` — which the wrong table invited — would have produced a
tablet whose two device trees disagree about the cluster idle states: the
bootloader hands over one, the kernel is built against the other, and the round
is uninterpretable rather than merely mis-flashed. The table is corrected, the
measurement is quoted in `docs/CPU_IDLE_WEDGE_PLAN.md`, and a test now asserts
both copies exist in the build script so a future edit cannot silently drop one.

## Two things the next session should know before flashing

1. **Profiles I and J write two partitions.** Not one. See above.
2. **`cpuidle.off=1` writes one, and it is `vendor_boot`, not `boot`** — the
   opposite partition from the ablations. Getting this backwards is the single
   most likely way to introduce a second variable into this round.

The arming gate catches it either way: `cpuidle-off` decides on the sysfs group
being absent plus the governor never having registered, and the two ablations
decide on `/proc/device-tree`, which reads back the tree the kernel actually
booted. A half-written flash fails the gate instead of producing a round.

## Related

* `reference/boot-tests/test-226-cpuidle-off-gate/README.md` — the full run
  procedure for `cpuidle.off=1`: hashes, verification commands, wedge criteria
  and recovery
* `docs/CPU_IDLE_WEDGE_PLAN.md` — the pre-registered rule; §3 for the ladder and
  the corrected artifact table
* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — what each state is
