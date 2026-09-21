# Boot test 3 — proof-of-life marker (2026-09-21)

Third physical attempt, carrying the `parse_early_param()` proof-of-life marker
and `nokaslr`. It answers the question boot tests 1 and 2 could not.

## Artifacts flashed

Only the two partitions whose images changed were rewritten; `init_boot` and
`dtbo` were already byte-identical from boot test 2.

| Partition | SHA-256 written (= read back) |
|---|---|
| `boot` | `1c53094773989b3f85faec6f3310eabc184d38450635cb472ba4831e3617d35a` |
| `vendor_boot` | `b9f0cfd1e16013a36d66c57f1dcb71ca9afdea91abd1d30fae0665df2758a8d1` |
| `init_boot` (unchanged) | `26dd7517e1dbe65155a866d6fdb50c08f71268de6d009563a6edf23a8d179522` |
| `dtbo` (unchanged) | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |

Kernel: `Image.gz`
`b2db31dbd4164352b773c598375be95cb0f953709724be71570fda71a9805f6e`, board DTB
`1c105090a0c087334435e19fb9f99047ac32865994baf372511846a0a367083c`, built from
commit `311b64d`. `vbmeta` untouched.

The vendor cmdline now carries `nokaslr` alongside `gts9_sec_log=`; ABL echoes
that exact command line in its log, so it is confirmed to reach the kernel.

## Result: the marker is absent

Ring captured by `scripts/capture-last-kmsg.sh` the moment TWRP reappeared
(`last_kmsg-test3-20260921T113542Z.txt`, 2,097,136 bytes, SHA-256
`e30e7682e1f9773b33edb0bfb55e469aa818f2794d045071f2d634075bafd7f7`):

```text
GTS9-EARLY-MARKER                 0     <-- the decisive line
Linux version                     0
gts9wifi-sec-log                  0
GTS9 MAINLINE INITRAMFS REACHED   0
nokaslr                          13     (ABL's echo of our cmdline)
```

The marker is written from `parse_early_param()` inside `setup_arch()`, after
`early_ioremap_init()` and before `paging_init()`, memory init, device-tree
unflattening and every console. Its absence means **the kernel never got that
far** — so the failure is not in a driver, not in the initramfs, and not in
anything the port has written so far. `nokaslr` also rules KASLR relocation out
as the cause.

## What is left, and the leading candidate

Between "ABL jumps to the image" and "`parse_early_param()` runs", the kernel
does very little: EFI stub or direct entry, `head.S` (MMU, stack), and
`setup_machine_fdt()` — which scans the device tree and, if the FDT pointer is
unusable, does not return an error but **spins forever**:

```c
	if (!dt_virt || !early_init_dt_scan(dt_virt)) {
		pr_crit("Error: invalid device tree blob at physical address %pa ...");
		while (true)
			cpu_relax();
	}
```

and `fixmap_remap_fdt()` rejects the pointer if it is not 8-byte aligned or the
blob exceeds 2 MiB. A spin there, on a tablet whose bootloader watchdog is
armed, is indistinguishable from our symptom: silent boot loop, nothing in the
ring.

That points at the appended DTB. This repository appends the board DTB to
`Image.gz` inside `boot.img`, the layout the SM-X910 port validates. The
appended blob starts at offset `len(Image.gz)` = **21,805,353 bytes**, which is
not 8-byte aligned (21,805,353 mod 8 = 1). If the SM-X710 bootloader detects
that appended blob and passes `payload + kernel_size` as the FDT pointer — the
classic appended-DTB convention — arm64 rejects it and spins.

Supporting facts:

- the stock SM-X710 `boot.img` carries a **raw kernel with no appended DTB**
  (kernel_size 38,377,984, no trailing blob), and its DTB comes from
  `vendor_boot` — exactly the layout that works on this tablet;
- boot test 2 already proved ABL selects our DTB out of `vendor_boot`
  (`Best match DTB tags ... size 0x2AD1B` = 175,387 bytes = our board DTB), so
  the appended copy is not needed for ABL to find a tree;
- `arch/arm64` has no appended-DTB support at all, so the kernel would never
  read the appended blob itself.

## Next step

Boot test 4 removes exactly that variable: `APPEND_DTB=0`, i.e. `boot.img`
carries pure `Image.gz` and the DTB comes from `vendor_boot` as it does for the
stock tablet. The bundle also records its layout in `BUNDLE_INFO`, and the
validator now checks the board selectors on the `vendor_boot` tree in both
layouts.

If the marker appears in boot test 4, the appended DTB was the cause and the
remaining failure is inside the kernel; if it is still absent, the fault is
earlier still (entry or `head.S`) and the next step is instrumentation in the
arm64 entry path rather than anything in this port.
