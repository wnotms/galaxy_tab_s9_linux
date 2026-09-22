# test-153 — the artifacts to be flashed verify at image level

Rebuilt from the current `test` HEAD after the earlier bundle turned out to be stale, and
then checked *inside the images* rather than in the staging directory.

```
boot.img        c12590a8…   (kernel unchanged by this work)
init_boot.img   e91f454c…   (the new initramfs)
vendor_boot.img 219fb0be…   (the new cmdline)
```

`init_boot.img` is an Android boot image whose ramdisk is LZ4 compressed (legacy frame,
magic 02 21 4C 18).  Extracted, decompressed with `lz4 -dc` and searched as a cpio stream:

| string | count |
| --- | --- |
| `start_panel_shell` | 2 (definition and call) |
| `GTS9 mainline` | 4 (the banner) |
| `USB shell: /dev/ttyGS0` | 1 |
| `unavailable after 10 s` | 1 (the bounded wait for tty1) |
| `gts9_rootfs=` | 2 (the future-rootfs guard) |
| `chvt 1` | 1 |
| `cat /dev/kmsg > /dev/tty1` | **0** |

`vendor_boot.img` carries exactly one console token, `console=ttyMSM0,115200n8`, plus
`loglevel=4`, and neither `console=tty0` nor `ignore_loglevel`.

Why this mattered: the first bundle (`out/boot-bundle-test150`) was built before the bounded
wait was added, so its ramdisk contained `start_panel_shell` and the banner but not the wait
- an artifact lag that a staging-directory check cannot see.  That is what prompted the
image-level check, and the bundle has been rebuilt from HEAD.

Host gate at this point: `python3 -m unittest discover -s tests` -> OK (10 original plus 9
spec checks).

## Owed

The physical checklist of section 15, which needs the owner's go-ahead to flash: panel lit,
screen cleared, `GTS9 mainline` and a `gts9#` prompt, pogo keyboard input (`echo hello`,
`uname -a`, `lsblk`), Ctrl-C, `exit` restarting the shell, the USB ACM shell still alive,
`dmesg` intact, UART intact, and `cat /sys/class/tty/tty0/active` recorded.
