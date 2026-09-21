# Test 031 — the serial console is interactive (2026-09-21T15:26:19Z)

The console fix from test 030's finding: the shell is handed `/dev/ttyGS0`
directly and stays the only reader, the kernel-log flood is off by default, and
the shell prints a banner that says how to get back to TWRP.

Artifacts: `boot ba948a93…`, `init_boot c7e5b360…`, `vendor_boot 5aae758c…`
(the new default command line: mass storage + console, BCB safety net at 1800 s).

## Result: commands run on the tablet and their output comes back

```
SENT  uname -a
RECV  Linux (none) 7.2.0-rc3-gts9wifi-dirty #1 SMP PREEMPT ... aarch64 GNU/Linux
RECV  /dev/mmcblk1p1   /dev/sda /dev/sdb /dev/sdc          (ls /dev/mmcblk1p1 /dev/sd?)
RECV  Filesystem    Size  Used  Available  Use%  Mounted on (df -h)
RECV  tmpfs        5.2G  156.0K      5.2G   0%  /tmp
RECV  [   16.007348] qcom-pcie 1c00000.pcie: host bridge ... (dmesg | tail -4)
```

A live kernel log, the block devices and a prompt (`gts9#`) over USB, with no
TWRP and no owner in the loop.

## The console found its own bug

`gts9-to-recovery` did nothing, and the console said exactly why:

```
cat /tmp/gts9-misc-dev      -> No such file or directory
dd if=/dev/sda10 count=16   -> all zeros      (no BCB had been written)
uptime                      -> 251 s         (the tablet had not rebooted)
```

`publish_misc_device` was called next to its definition, near the top of `/init`,
where `gadget_setup` is still 0 and UFS may not be enumerated yet - so it never
ran, and the helper correctly refused to guess a device.  Fixed in test 032.

The BCB path itself was proved from the console in the same run: a hand-written
`printf 'boot-recovery' | dd of=/dev/sda10 ... ; reboot -f` put the tablet back
in TWRP 20 seconds later.
