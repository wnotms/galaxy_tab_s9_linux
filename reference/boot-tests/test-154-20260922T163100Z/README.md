# test-154 — panel shell flashed: every log-side criterion passes

Flashed after the owner's "刷入测试": `vendor_boot.img 219fb0be` (new cmdline) and
`init_boot.img e91f454c` (new initramfs), each written and read back byte for byte;
`boot.img c12590a8` unchanged.  Both cycles took 49 s.

## Read from the device

```
$ cat /sys/class/tty/tty0/active
tty1

[    1.663239] gts9-init: console loglevel set to 1: kernel messages stay out of the panel shell
[    2.046603] gts9-init: panel shell: foreground VT is tty1
[    2.046668] gts9-init: panel shell started on /dev/tty1 (local bring-up/rescue shell)

$ cat /proc/cmdline
console=ttyMSM0,115200n8 ... loglevel=4 ... earlycon ... fbcon=font:TER16x32  <bootloader tail>

$ grep -A4 EF-DX710 /proc/bus/input/devices
N: Name="Book Cover Keyboard Slim (EF-DX710)"
H: Handlers=sysrq kbd leds event0

$ cat /proc/sys/kernel/printk
1       4       1       7

$ echo "i2c=$(dmesg | grep -ac geni_i2c) pogo=$(dmesg | grep -ac 5-002a) drm=$(dmesg | grep -ac msm_dpu) reg=$(dmesg | grep -ac regulator)"
i2c=0 pogo=12 drm=3 reg=16
```

Checklist against section 15, log side:

- §15.5 / §16: the panel shell started and the foreground VT is **tty1**.
- §11: `tty0/active` reads `tty1`, recorded as asked.
- §3: the cmdline has no `console=tty0` and no `ignore_loglevel`; the UART console and
  `earlycon` are still there, and `fbcon=font:TER16x32` is untouched.  (The long tail is
  the bootloader's own append, including its `console=null`, which `ignore_console_null`
  exists for.)
- §7: printk is `1 4 1 7`, not disabled.
- §10: EF-DX710 still carries the `kbd` handler, so pogo input reaches the VT.
- §15.10: the kernel log is intact - pogo (12), DRM (3) and regulator (16) lines are in
  dmesg; no `geni_i2c` line this boot simply means no NACK was logged.
- §15.11: UART debugging is unchanged; the console token is still `console=ttyMSM0,115200n8`.

## Still owed: what only the screen can show

The physical half of section 15: the screen cleared and holds `GTS9 mainline` with a
`gts9#` prompt, pogo keyboard input (`echo hello`, `uname -a`, `lsblk`), Ctrl-C
interrupting a foreground command, `exit` bringing the shell back, and the USB ACM shell
on ttyGS0 still working.  None of those is claimed here.
