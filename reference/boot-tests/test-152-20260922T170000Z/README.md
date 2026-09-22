# test-152 — panel shell: host-side audit against the specification

Scope of this change: the console / initramfs shell path only.  The pogo keyboard driver,
the display driver, DSI, DRM and the TF/rootfs logic are untouched (verified by
`git show --stat` on the four commits: only `boot/bringup-init.sh`,
`boot/cmdline.example.txt` and `tests/test_panel_shell.py` changed).

| spec | requirement | evidence |
| --- | --- | --- |
| §3 | drop `console=tty0` and `ignore_loglevel`, keep the UART console | `cmdline.example.txt` now has exactly one console token, `console=ttyMSM0,115200n8`; `earlycon` and `fbcon=font:TER16x32` stay; `loglevel=4`.  The built `vendor_boot.img` carries the same and neither removed token. |
| §4 | keep VT / fbcon, do not change config | built config has `CONFIG_VT=y`, `CONFIG_VT_CONSOLE=y`, `CONFIG_FRAMEBUFFER_CONSOLE=y`, `CONFIG_FB=y`, `CONFIG_DRM_FBDEV_EMULATION=y`, `CONFIG_FONTS=y`, `CONFIG_FONT_TER16x32=y`.  No config file was modified. |
| §5 | panel shell function, background, restarting, not PID 1 | `start_panel_shell()` backgrounds its loop with `) &`; `/init` never exec's a shell (checked line by line); the loop restarts the shell after it exits; `/dev/tty1` is waited for up to 10 s. |
| §6 | start after display recovery and before the USB console section | source order is `display_recover` (line 104) -> `start_panel_shell` (1096) -> USB section (1098) -> ttyGS0 shell handoff (1148) -> PID 1 keep-alive loop (1163). |
| §7 | quieten printk without disabling it | `printf '1 4 1 7' > /proc/sys/kernel/printk`, and no `echo off`; the ring buffer is untouched, so `dmesg` keeps everything. |
| §9 | USB ACM shell keeps working, no stdin stealing | the ttyGS0 section is unchanged and still runs after the panel shell; there is no `cat /dev/kmsg > /dev/tty1` anywhere in the script. |
| §10 | pogo keyboard untouched | `kernel/drivers/keyboard-samsung-pogo.c`, the DTS and the rail/IRQ paths are not in this change. |
| §11 | foreground VT | the script logs `/sys/class/tty/tty0/active` and calls `chvt 1` when the applet exists (it does in this initramfs). |
| §12 | only the shell on the panel | the banner is four short lines plus the prompt; no report, no `/proc/interrupts`, no DRM or I2C dump. |
| §13 | future rootfs boot | a `gts9_rootfs=` token in `/proc/cmdline` skips the panel shell entirely, leaving tty1 to the rootfs's own getty. |
| §14 | display recovery unchanged | `gts9_display_recover`, panel reset, DSI, DRM and backlight code are untouched; the only added call sits after them. |

Host gates at this point: `python3 -m unittest discover -s tests` -> OK (10 original plus 9
spec checks), `scripts/build-bringup-initramfs.sh` -> OK, and the staged built init contains
`start_panel_shell`.  `init_boot.img` could not be string-searched directly because it is an
Android boot image with the ramdisk inside; the staging copy is what the bundle packs.

## Not done here, and why

No flash.  The specification's §15 says to finish the host build and test first and not to
flash automatically, so the physical checklist (panel lit, quiet screen, `gts9#` prompt,
pogo keyboard input, Ctrl-C, `exit` restarting the shell, USB ACM shell still alive,
`dmesg` intact, UART intact) is still owed and needs the owner's go-ahead.
