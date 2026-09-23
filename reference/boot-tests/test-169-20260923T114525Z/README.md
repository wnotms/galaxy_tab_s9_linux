# Test 169 — poweroff with Type-C removed, then VBUS-triggered boot

**Result:** the owner observed the tablet remain off after Type-C was removed;
a short power-key press with Type-C disconnected did not start it. Reconnecting
Type-C started the tablet automatically. That strongly supports Type-C/VBUS as
the trigger for the prior automatic restart, while battery-only startup remains
unresolved.

The controlled `sudo -n systemctl poweroff` command was sent over COM17 at
2026-09-23 11:38:33 UTC. The serial observation window ended at 11:39:33 UTC
without another prompt. The owner then reported: “拔线后关机，短按电源无反应，
插入typec后自动开机,但卡在此界面” (it stayed off after unplugging Type-C;
short-pressing power did nothing; inserting Type-C started it automatically,
but it stopped at the pictured screen).

## Boot-state evidence after Type-C reconnect

The owner-provided photo, captured at 2026-09-23 11:41:06 UTC, shows only:

```text
GTS9 mainline: early display console ready
GTS9 mainline: console on the AMSA10FA01 panel (2560x1600)
```

This proves the mainline kernel and panel console were active. It does not prove
that the microSD root was found, mounted, or handed to Debian. A read-only COM17
probe did not receive a Debian login prompt or shell. The photo was not copied
into the repository; its local SHA-256 was
`f2547dd836213efeb159b1b6f35ffe1d77a4809e9fb652e067591c85aed3a80e`.
The host serial capture is kept outside the repository at
`/mnt/d/android/gts9-flash/test169-poweroff-console.log`.

## Interpretation

The off state with VBUS removed, followed by automatic startup when VBUS was
reconnected, is consistent with the poweroff path reaching a real off state and
the PMIC treating VBUS insertion as a boot event. It is strong physical
evidence, but there was no battery-current measurement or direct PSCI call
trace, so this does not prove which low-level handler completed the transition.

The post-reconnect screen is an early initramfs marker. Because the interactive
rescue shell did not appear and COM17 had no Debian prompt, this boot has not
yet demonstrated rootfs handoff. The exact stopping point remains unknown: the
diagnostic initramfs candidate has not been flashed, and the current boot did
not expose its initramfs report over COM17. No SD regulator, Type-C, PMIC, USB,
display, or poweroff code was changed.

The owner later reconfirmed that the display was still showing the same two
markers. The opt-in tty0 report trace was then added to a separate host-built
candidate; it has not been installed on the device.

The next useful diagnostic is to boot the already-built stage-instrumented
initramfs and retrieve `/var/log/gts9-last-boot-stage` after the rootfs mounts,
or use an initramfs console/report channel if it fails earlier. Do not infer a
microSD or regulator fault from this screen alone.
