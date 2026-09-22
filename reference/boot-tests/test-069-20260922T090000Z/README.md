# test-069 — flash record for the A/B boot (vendor port): bookkeeping entry

- started: 2026-09-22T09:00:00Z
- source commit: `453fae5` ("samsung-pogo: the A/B kernel builds with the vendor port")
- hypothesis, change and predictions: `source.txt`, written before the flash
- images: `boot.img 39ff3c2f…`, `vendor_boot.img 4d496064…`, `init_boot 12b77d17…`,
  `dtbo c17418be…` unchanged

This directory holds only the raw evidence of the flash itself, which was taken
while the round was still in progress and was not turned into a README at the
time. It is recorded here for completeness, with no result of its own:

```
D:\android\gts9-test069\boot.img: 1 file pushed ... (100663296 bytes)
100663296 bytes (100 M) copied, 0.333592 s, 288 M/s
boot read-back 39ff3c2f5bff173ee3dedd0322fb1f7eb6d010cf8f6652d5612595cc17a10770 /dev/block/by-name/boot
expected      39ff3c2f5bff173ee3dedd0322fb1f7eb6d010cf8f6652d5612595cc17a10770
bcb-cleared
```

The read-back hash equals the pushed image, so the boot partition in this A/B
cycle held the vendor-port kernel, and the BCB was cleared so the next boot would
go to system rather than back to recovery.

**The outcome of this A/B belongs to test 070**, which is the run of this image:
Samsung's own `stm32_pogo_v3` ported into the tree reaches its probe, switches its
own rail, enables its interrupt and then reads `0x2a` no better than the mainline
port — see `../test-070-20260922T090500Z/README.md`.
