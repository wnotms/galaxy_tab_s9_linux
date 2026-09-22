# test-155 — the panel is an interactive tty1 shell: the goal is met

The decisive evidence is not a log line but the panel's own screen buffer.  `/dev/vcs1` is
the character content of tty1, i.e. exactly what the AMSA10FA01 panel is displaying:

```
GTS9 mainline
Linux 7.2.0-rc3-gts9wifi-dirty
Local shell: tty1
Kernel log: dmesg
USB shell: /dev/ttyGS0
BusyBox v1.36.1 (Ubuntu 1:1.36.1-6ubuntu3.1) built-in shell (ash)
Enter 'help' for a list of built-in commands.
gts9# gts9#
gts9# ls
bin dev etc init lib proc root run sbin sys tmp
gts9# echo hello
hello
gts9# uname -a
Linux (none) 7.2.0-rc3-gts9wifi-dirty #1 SMP PREEMPT Sun Jul 12 21:16:39 UTC 2026 aarch64 GNU/Linux
gts9# lsbl…
```

Those are commands typed on the EF-DX710 pogo keyboard and their output, on the panel.
No kernel log line appears anywhere in the buffer.

Supporting state at the same moment:

```
$ cat /sys/class/tty/tty0/active          -> tty1
$ ps                                      -> 1 {init} /bin/sh /init
                                             707 /bin/sh -i     (fd 0 -> /dev/ttyGS0, ppid 1)
                                             709 /bin/sh -i     (fd 0 -> /dev/tty1,  ppid 706)
$ ls -l /dev/tty1 /dev/ttyGS0             -> both present (4,1 and 234,0)
$ cat /proc/sys/kernel/printk              -> 1  4  1  7
$ dmesg counts                            -> pogo=12 drm=3 regulator=16
[1.66] gts9-init: console loglevel set to 1: kernel messages stay out of the panel shell
[2.05] gts9-init: panel shell: foreground VT is tty1
[2.05] gts9-init: panel shell started on /dev/tty1 (local bring-up/rescue shell)
```

Against the owner's section 18, all five have to hold, and each now has direct evidence:

| section 18 requirement | evidence |
| --- | --- |
| tty1 is a real interactive terminal | a shell runs with fd 0 on /dev/tty1 (pid 709) and it executed commands |
| pogo keyboard can type | `ls`, `echo hello`, `uname -a` were typed and produced output |
| shell output shows on the framebuffer | that text is in /dev/vcs1, the panel's own buffer |
| USB ACM still works | a second `/bin/sh -i` (pid 707) has fd 0 on /dev/ttyGS0 |
| dmesg log is not lost | pogo, DRM and regulator lines are all still in the ring buffer, and printk is 1 4 1 7 rather than off |

And against section 16: the screen holds `GTS9 mainline` with a `gts9#` prompt, commands
typed on the pogo keyboard produce output immediately, and the kernel log no longer
overwrites it.

## Not evidenced here

Ctrl-C interrupting a foreground command and `exit` restarting the shell were not
exercised - the design covers them (setsid gives the shell tty1 as its controlling terminal;
the shell runs inside a `while :` loop whose parent is the background subshell, with PID 1
untouched) but they are inference, not measurement, and are recorded as such.  The panel
being physically lit is likewise the owner's observation; this record only proves what the
VT buffer contains.
