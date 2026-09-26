# The missing Galaxy prime OPP: CPU7 at 3.36 GHz

Every boot on this tablet prints two lines that look like a power fault:

```
cpu cpu7: Voltage update failed freq=3360000
cpu cpu7: failed to update OPP for freq=3360000
```

They are not a supply failure. They are a device-tree description that stops one
operating point short of what the hardware advertises, and the fix is to describe
the missing point.

## What the hardware offers and what the DT described

| | |
|---|---|
| SoC | SM8550-AC, "Snapdragon 8 Gen 2 for Galaxy" |
| the frequency in question | **3.36 GHz** (3360000 kHz), the Galaxy prime-core bin |
| generic `sm8550.dtsi` `cpu7_opp_table` top entry | **3187200000** (3.1872 GHz) |
| `3360000000` anywhere in the generic SM8550 DTS | **absent** |
| board DT override before this change | **none** |

The frequency list comes from the *hardware* LUT that ABL programs, not from the
device tree. The DT's job is only to describe the points so the driver can attach
metadata to them, which is why an entry the hardware has and the DT lacks is a
software gap rather than a hardware one.

On this tablet, boot `8cac4aba-0f40-4338-9c70-59d609614d1d`:

```
[    0.393699] cpu cpu7: Voltage update failed freq=3360000
[    0.393720] cpu cpu7: failed to update OPP for freq=3360000
```

## The mechanism, from the driver source

`drivers/cpufreq/qcom-cpufreq-hw.c`, `qcom_cpufreq_hw_read_lut()`:

1. it walks the hardware LUT, reading a frequency, a voltage and a core count per
   row;
2. for each distinct frequency it calls `qcom_cpufreq_update_opp()`;
3. when interconnect scaling is in use, that function is:

   ```c
   ret = dev_pm_opp_adjust_voltage(cpu_dev, freq_hz, volt, volt, volt);
   if (ret) {
           dev_err(cpu_dev, "Voltage update failed freq=%ld\n", freq_khz);
           return ret;
   }
   return dev_pm_opp_enable(cpu_dev, freq_hz);
   ```

4. `dev_pm_opp_adjust_voltage()` needs the OPP to **exist** - it searches the
   table for a matching frequency and returns `-ENOENT` when there is none.

So the 3.36 GHz LUT row has no OPP to be written into, the `dev_err` fires, the
caller adds its own `dev_warn` ("failed to update OPP for freq=…") and marks that
LUT entry `CPUFREQ_ENTRY_INVALID`. The frequency is dropped from the policy.

**The message names the wrong thing.** "Voltage update failed" is the failure of
an OPP *lookup* that happens to live in a function whose job includes voltage
adjustment. Nothing about the rail failed, and no voltage was rejected.

## The fix

One node in the board device tree, `kernel/dts/sm8550-samsung-gts9wifi.dts`:

```dts
&cpu7_opp_table {
	opp-3360000000 {
		opp-hz = /bits/ 64 <3360000000>;
		opp-peak-kBps = <(933000 * 16) (3686000 * 4) (1689600 * 32)>;
	};
};
```

### Why there is no `opp-microvolt`

Voltage comes from the hardware LUT: the driver reads the per-row voltage and
writes it into the OPP it finds. A voltage declared here would be a rail value
this port has not measured, and `dev_pm_opp_adjust_voltage()` overwrites it at
probe anyway. The generic `cpu7_opp_table` declares no `opp-microvolt` either, so
adding one would also make this point inconsistent with its neighbours.

### Why there is no `turbo-mode`

Boost classification comes from the LUT's core-count field:
`qcom_cpufreq_hw_read_lut()` sets `CPUFREQ_BOOST_FREQ` for the last
`LUT_TURBO_IND` entry itself, and the driver never reads `turbo-mode` from the
device tree. A board-level `turbo-mode` would be an unreferenced claim about a
decision the hardware LUT already makes.

### Why the bandwidth votes are the generic top-end ones

`<(933000 * 16) (3686000 * 4) (1689600 * 32)>` is what the three highest generic
prime OPPs already use:

| OPP | `opp-peak-kBps` |
|---|---|
| 2841600000 | `<… (1689600 * 32)>` |
| 2956800000 | `<… (1689600 * 32)>` |
| 3187200000 | `<… (1689600 * 32)>` |
| **3360000000 (new)** | **`<… (1689600 * 32)>`** |

That is LLCC 14928000, DDR 14744000 and L3 54067200 kBps. The new point
**continues** the top-end votes; it does not measure new ones. This port has no
independent bandwidth measurement at 3.36 GHz, and the S8 Gen 2 for Galaxy prime
rail is the same LLCC/DDR/L3 client at the top of its range.

## Relationship to the sibling X910 port

The same OPP is declared in the sibling Galaxy Tab S9 Ultra port
(`agcarbajo/ubuntu-galaxy-tab-s9-ultra`, `kernel/dts/sm8550-samsung-gts9uwifi.dts`),
with a byte-identical node and the same reasoning in its comment. That is useful
corroboration for the *shape* of the fix and it is why this node matches it
property for property.

It is **not** the evidence this change rests on, because X910 is not X710. The
evidence is local and independent, and it was already in this repository:

1. this tablet's own `qcom-cpufreq-hw` output, `Voltage update failed
   freq=3360000`, on every boot - the hardware LUT advertising the frequency;
2. the pinned generic `sm8550.dtsi`, which stops at 3.1872 GHz;
3. `docs/X710_X910_GPU_RPMH_DIFF.md` §12.4, which identified the mismatch and the
   X910 recipe before this change was made, and flagged it as needing X710
   confirmation.

That cross-port audit also carried a factual error worth noting, because it made
the gap look smaller than it is: it said X710's table tops out at 2.9568 GHz. The
pinned source ends at **3.1872 GHz**. Corrected in place.

Nothing else was copied from X910: not its GPU OPP table, not WCN7850, not its
camera or PMIC configuration, not its performance overlay or any driver patch.
The single node above is the entire change.

## Verified in the compiled artifact, not just the source

`dtc` and `fdtget` against the DTB this repository actually builds and bundles:

```
$ fdtget -l out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb /opp-table-cpu7
opp-3187200000
opp-3360000000                       <- present, and the old top OPP survives

$ fdtget -t x …/opp-table-cpu7/opp-3360000000 opp-hz
0 c8458800                           <- 0x00000000c8458800 = 3360000000

$ fdtget -t x …/opp-table-cpu7/opp-3360000000 opp-peak-kBps
e3c880 e0f9c0 3390000                <- identical to opp-3187200000

$ fdtget -t x …/opp-table-cpu7/opp-3360000000 opp-microvolt
Error at 'opp-microvolt': FDT_ERR_NOTFOUND
$ fdtget -t x …/opp-table-cpu7/opp-3360000000 turbo-mode
Error at 'turbo-mode': FDT_ERR_NOTFOUND
```

The same DTB is carried in **two** places, because the tablet's boot chain
consumes both. Both were extracted from the built bundle and checked:

| artifact | DTB | `opp-3360000000` |
|---|---|---|
| `boot.img` (appended after the gzip stream) | `d00dfeed`, 177595 bytes | present, `c8458800` |
| `vendor_boot.img` (`dtb` entry) | identical bytes | present, `c8458800` |

`cmp` confirms the appended DTB, the vendor_boot DTB and the built
`sm8550-samsung-gts9wifi.dtb` are the **same bytes**, so there is no build path
that silently drops the node.

## Hashes

| artifact | sha256 |
|---|---|
| `kernel/dts/sm8550-samsung-gts9wifi.dts` | `b0dfc6f6947bff0249546109ff4fc05797dcd75be26b0b11fe27893d5d4c7cd2` |
| `out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb` | `eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0` |
| `out/kernel-gts9wifi/Image.gz` | `f74728727418cc83d051dea18af1ec3763f5619785486a9106426ea50d2e0c66` — **unchanged** |
| `boot.img` | `71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d` |
| `vendor_boot.img` | `49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9` |
| `init_boot.img` | `1e98bea223cf8e6ee58a4a0e8378f9c916d02e3a9c4bde7aa431e5472cbe6175` — **unchanged** |
| `dtbo.img` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` — **unchanged** |

`Image.gz` is unchanged because the change is device-tree only: no driver source,
no config, no patch. The kernel binary on the tablet is the same one it has been
running.

## Deploying and checking it by hand

Only two partitions carry the DTB, and both must be written:

```
boot.img          (DTB appended to the kernel payload)
vendor_boot.img   (DTB entry)
```

`init_boot.img` and `dtbo.img` do **not** change and do not need rewriting.

Nothing here is flashed automatically. After a manual deploy:

```sh
uname -a
cat /proc/device-tree/model

# The two lines this removes:
dmesg -T | grep -E 'Voltage update failed|failed to update OPP'

# And the frequency should now be visible to cpufreq:
for p in /sys/devices/system/cpu/cpufreq/policy*; do
    echo "=== $p ==="
    cat "$p/affected_cpus" 2>/dev/null
    cat "$p/scaling_available_frequencies" 2>/dev/null
    cat "$p/scaling_boost_frequencies" 2>/dev/null
    cat "$p/cpuinfo_max_freq" 2>/dev/null
    cat "$p/scaling_max_freq" 2>/dev/null
done
```

`policy7` is the one that matters: **3360000** should appear in its available or
boost frequency list.

Do **not** pin the frequency (`echo 3360000 > scaling_min_freq`) to prove it. A
read-only look at `scaling_cur_freq` under an ordinary short load is fine, but
observing the frequency is **not** the criterion for this fix: thermal limits,
current limits, the scheduler and the boost state can all legitimately keep a
short test below the top bin. The hard criteria are the three below.

## Success criteria

1. the compiled live DT contains the 3.36 GHz OPP;
2. the cpufreq policy registers the frequency;
3. `cpu cpu7: Voltage update failed freq=3360000` no longer appears.

## What this does NOT claim

**This does not fix the CPU wedge, and no number of successful boots would make
it do so.** The wedge is a separate, pre-existing failure documented in
`docs/CPU_WEDGE_EVIDENCE.md`, with a measured rate of 1 in 29 boots after the ACD
fix, and establishing any causal link between this OPP and that stall would need
a pre-registered A/B experiment of its own. A run of clean boots after this
change is equally consistent with the 3.4 % base rate and with the change having
no effect on the stall at all.

The claim this change supports is narrow and complete: the board device tree now
describes the operating point the hardware LUT already had, and the
`Voltage update failed` warning goes away.

## Scope boundaries

Unchanged by this work, and asserted by `tests/test_galaxy_prime_opp.py`:

- the generic `sm8550.dtsi` CPU7 table, and the 3.1872 GHz OPP in particular;
- every other OPP table (CPU0–6, GPU), idle states, and all regulator voltage;
- `cpufreq` driver source and the governor or boost policy;
- the production command line, including `panic=0`;
- the seven debug command lines and their `softlockup_panic=1` / `panic=10`;
- the initramfs, USB, networking and firmware.
