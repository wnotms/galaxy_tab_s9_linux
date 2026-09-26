# Round 33 candidate manifest — three flashable profiles, all verified

**Status: built and verified, not flashed. The tablet is not connected** (see
`test-226-cpuidle-off-gate/STATUS-no-physical-run.md` for the probes behind that
statement). This file exists so the physical test is turnkey the moment the
tablet is attached: every hash, every write scope and every verification command
is fixed in advance, and nothing has to be rebuilt or re-derived.

## 1. The three candidates

All three share **one kernel**: `Image.gz` is
`f74728727418cc83d051dea18af1ec3763f5619785486a9106426ea50d2e0c66` in every
bundle, byte-identical to what the tablet already runs. The A/B is therefore
purely about the device tree and the command line, and no profile can be
confused by a kernel difference.

| profile | what it removes | cmdline | DTB |
|---|---|---|---|
| `cpuidle-off` | **everything above WFI** — no `PSCI CPU_SUSPEND` at all | `cpuidle.off=1` added | unchanged (`eecc98b8`) |
| `no-llcc-off` | the deeper cluster idle state (`0x4100c344`) | identical to baseline | `b5ce5277` |
| `no-cluster-idle` | the cluster's suspend param entirely | identical to baseline | `5843147e` |

Read the ladder in `docs/CPU_IDLE_WEDGE_PLAN.md` §3 before choosing an order.
`cpuidle-off` runs first because it is the gate: one wedge there downgrades the
whole PSCI-idle direction, and the two cluster profiles then need not be run.

## 2. What the tablet has now, and therefore what each write changes

Device state from the committed records of test-214 (`boot`, `vendor_boot`,
`dtbo`) and test-216 (`init_boot`), which are the last flashes that touched
these partitions:

```
boot.img         71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d
vendor_boot.img  49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9
init_boot.img    1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0
dtbo.img         c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
```

**Do not confuse the partitions.** The two DTB profiles and the cmdline profile
write *different* sets, and writing the wrong one puts two variables in a round:

| profile | write | `boot.img` | `vendor_boot.img` | `init_boot` / `dtbo` / `vbmeta` |
|---|---|---|---|---|
| `cpuidle-off` | **`vendor_boot` only** | `71e194a5` *(same)* | `1245bb39` | **do not write** |
| `no-llcc-off` | **`boot` + `vendor_boot`** | `80aa010f` | `e237a98e` | **do not write** |
| `no-cluster-idle` | **`boot` + `vendor_boot`** | `e6c20edc` | `81088377` | **do not write** |

An idle ablation changes **two** partitions because
`scripts/build-boot-bundle.sh` appends the DTB to `boot.img`'s payload *and*
passes the same file to `vendor_boot.img`. Writing only one would leave the
bootloader and the kernel holding different device trees. This was measured, not
assumed; see `docs/CPU_IDLE_WEDGE_PLAN.md` §3.0.

Never write `vbmeta`, `recovery`, `misc`/BCB, `userdata` or the partition table.

## 3. Full artifact hashes

Each block below is the bundle's own `SHA256SUMS`, reproduced verbatim so a
reader can run `sha256sum -c` against the images they are about to write.

Every bundle names the **same** `image_gz_sha256`, which is the property that
makes these three profiles a controlled A/B rather than three experiments.

### `out/boot-bundle-cpuidle-off`

`kernel_release=7.2.0-rc3-gts9wifi-dirty`, `image_gz_sha256=f74728727418cc83d051dea18af1ec3763f5619785486a9106426ea50d2e0c66`, `dtb_sha256=eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0`

Verbatim `SHA256SUMS`, so it can be checked directly with
`sha256sum -c`:

```
71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d  boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0  init_boot.img
b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4  vbmeta.img
1245bb39be1a6cfd65e381e44d19ce4ab29ca295f976f0c78067e4bfecc5b18a  vendor_boot.img
```

### `out/boot-bundle-abl-no-llcc-off`

`kernel_release=7.2.0-rc3-gts9wifi-dirty`, `image_gz_sha256=f74728727418cc83d051dea18af1ec3763f5619785486a9106426ea50d2e0c66`, `dtb_sha256=b5ce5277c3713645da1d4b48153d1db178e966b83e06a54ec570f5074558ac98`

Verbatim `SHA256SUMS`, so it can be checked directly with
`sha256sum -c`:

```
80aa010f4070c69c80ca15ed31ea7825a5af4a5f22878f9fe4fa990bd053f8e5  boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0  init_boot.img
b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4  vbmeta.img
e237a98e67635589cb5154b19b76b2faf93b618743b478402a6ebca1aa2b821d  vendor_boot.img
```

### `out/boot-bundle-abl-no-cluster-idle`

`kernel_release=7.2.0-rc3-gts9wifi-dirty`, `image_gz_sha256=f74728727418cc83d051dea18af1ec3763f5619785486a9106426ea50d2e0c66`, `dtb_sha256=5843147e2a9c617c7c6c81816b64b856aa90bb1a612ad267770484a8a9ce684e`

Verbatim `SHA256SUMS`, so it can be checked directly with
`sha256sum -c`:

```
e6c20edc6757909a41f224bac9830ad8bea20fbccd52cb676148122dec4b82a8  boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0  init_boot.img
b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4  vbmeta.img
810883778ed8f798e6f14639f891c0d17ac838166254b48e608bd4b3abfc6620  vendor_boot.img
```
## 4. What was verified before parking these — and how

| check | result |
|---|---|
| `BOOT BUNDLE VALIDATION PASSED` for all three | yes, each with its own `--cmdline` |
| each parked bundle verified against **itself** | `scripts/verify-parked-bundle.sh`, all three exit 0 |
| the ablation DTB verified **before** bundling | `no-llcc-off` and `no-cluster-idle` both PASSED |
| the DTB **inside each bundle** re-extracted and verified | all three pass as their own profile |
| `boot.img` DTB vs `vendor_boot` DTB, per bundle | **identical** in all three |
| the kernel is the same in all three | `Image.gz = f7472872` throughout |
| the device's ramdisk carried forward | `init_boot.img = 1a8c7148` in all three |

**Check a parked bundle with `scripts/verify-parked-bundle.sh`, not with
`validate-boot-bundle.sh`.** The validator compares a bundle against whatever is
currently in `out/`, so it can only pass for the profile built most recently —
with three parked candidates, two of them always look broken, which is how a set
like this rots unnoticed. The parked-bundle verifier instead checks what must
hold for *any* candidate:

```sh
scripts/verify-parked-bundle.sh out/boot-bundle-cpuidle-off       cpuidle-off
scripts/verify-parked-bundle.sh out/boot-bundle-abl-no-llcc-off   no-llcc-off
scripts/verify-parked-bundle.sh out/boot-bundle-abl-no-cluster-idle no-cluster-idle
```

It confirms the bundle's own `SHA256SUMS`, that `BUNDLE_INFO` describes the
images present, that `boot.img` and `vendor_boot` carry the **same** device tree,
and that the tree verifies as the intended profile.

Note that `cpuidle-off` changes only the command line, so its device tree **is**
the unablated baseline — a tool that asked it for an idle ablation would fail a
correct bundle.

The ablation was verified on the **compiled DTB** at two points — after the
kernel build and again after extraction from the bundle — because the brief
requires exactly that and because a silently-no-op ablation would produce a
clean series that appears to prove the opposite of what it shows.

Reproduce any of them with:

```sh
GTS9_IDLE_ABLATION=no-llcc-off BUILD_MODULES=0 ./scripts/build-kernel.sh
./scripts/verify-idle-ablation.sh out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb no-llcc-off
MKBOOTIMG=$PWD/.work/tools/mkbootimg.py AVBTOOL=$PWD/.work/tools/avbtool.py \
  BUNDLE_OUT_DIR=$PWD/out/boot-bundle-abl-no-llcc-off \
  ./scripts/build-boot-bundle.sh \
    --initramfs <the device's ramdisk> \
    --cmdline boot/cmdline.stall-ab-no-llcc-off.example.txt \
    --bootconfig boot/bootconfig.example.txt
```

## 5. Arming checks, per profile

Run these on the tablet after the flash and **before** counting any round. The
harness enforces all of them and refuses to run otherwise.

**`cpuidle-off`** — decides on the sysfs group being absent:

```sh
grep -o 'cpuidle\.off=1' /proc/cmdline
test -d /sys/devices/system/cpu/cpuidle && echo "RUNNING (bad)" || echo "ABSENT (good)"
journalctl -b -1 -k --no-pager | grep -c 'cpuidle: using governor'   # expect 0
```

**`no-llcc-off` / `no-cluster-idle`** — no cmdline token exists, so the device
tree is the only authority:

```sh
wc -w < /proc/device-tree/psci/power-domain-cluster/domain-idle-states | tr -d ' ' | awk '{print $1/4" states"}'
#   no-llcc-off:      1 state
#   no-cluster-idle:  0
#   unablated:        2

od -An -tx4 -v /proc/device-tree/psci/power-domain-cluster/domain-idle-states
#   the FDT is BIG-endian, so these words are byte-reversed:
#   no-llcc-off:      44000041              == 0x41000044  (cluster_sleep_0)
#   unablated:        44000041 44c30041     == 0x41000044, 0x4100c344
```

The **count** is the check to trust first: it is endian-independent and it is what
distinguishes the profiles. The byte values are byte-reversed because
`/proc/device-tree` exposes the raw big-endian FDT (verified in
`drivers/of/kobj.c`, where `of_node_property_read()` copies `pp->value` with no
conversion) and `od` reads native little-endian words. The harness's own probe
byte-swaps before comparing, and a test asserts that it does — an earlier version
did not, and would have read `0x40000004` as `0x04000040` and rejected a
perfectly good DTB.

and the per-CPU states must still be intact in both — three
`arm,psci-suspend-param` properties, all `0x40000004`. The harness checks this
automatically and refuses the round if a CPU state is missing, because that would
mean the profile had silently become `cpuidle.off=1` and the result would be
misattributed to the cluster layer.

## 6. Running it

```sh
GTS9_ALLOW_POWER=1 scripts/stall-ab.sh cpuidle-off 10
GTS9_ALLOW_POWER=1 scripts/stall-ab.sh no-llcc-off 10        # only if needed
GTS9_ALLOW_POWER=1 scripts/stall-ab.sh no-cluster-idle 10    # only if needed
```

The decision rule is pre-registered in `docs/CPU_IDLE_WEDGE_PLAN.md` §5 and must
not be adjusted after seeing a count. In one line: **a single wedge with
CPU-level evidence means the layer is not necessary and stops that direction**;
`0/10` is `not reproduced in 10 boots` and is *no evidence at all* — 0 of 10 has
a 71% probability even if nothing changed.

## 7. Recovery

Each profile is reverted by writing back the partition hashes in §2. Nothing else
on the tablet is touched, `vbmeta` and `recovery` are never written, so a normal
ABL boot and a TWRP boot both remain available regardless of what a profile does.

## Related

* `docs/CPU_IDLE_WEDGE_PLAN.md` — the rule, the ladder, the corrected artifact table
* `docs/SM8550_IDLE_STATE_ANALYSIS.md` — the five states and what deleting one does
* `reference/boot-tests/test-226-cpuidle-off-gate/` — the `cpuidle.off=1` run procedure
* `reference/boot-tests/test-226-cpuidle-off-gate/STATUS-no-physical-run.md` — why no run has happened
