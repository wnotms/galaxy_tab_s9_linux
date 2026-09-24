# X710 boot timing and what evidence survives a stall

Two questions answered here from source and existing logs, both raised by
observations on the device this session. Neither proposes a code change; the
first is the explanation for "boot to the login screen is slow", the second is
what makes an unattended stall series possible.

## 1. Why the login screen takes as long as it does

`systemd-analyze` on the device reports:

```
Startup finished in 1.303s (kernel) + 5.458s (userspace) = 6.762s
graphical.target reached after 4.616s in userspace.
```

Kernel init and systemd are both fast. `systemd-analyze` starts its clock at
`/sbin/init`, so **everything before `switch_root` is outside that window** and is
where the extra wall-clock time sits. Two candidate contributors were checked.

### The panel driver is not it

`drivers/gpu/drm/panel/panel-samsung-ana38407.c` delays are small:

| step | delay |
|---|---|
| `ana38407_power_on` | `msleep(20)` between vddio and the other rails |
| `ana38407_reset` (Samsung `<0 10 1 1>`) | 5–6 ms + 10–11 ms + 10–11 ms |
| `POWER_ON_PRE_SETTING` | `mipi_dsi_msleep(50)` |
| pre-`POWER_ON_POST_SETTING` | `mipi_dsi_msleep(20)` |

Total ≈ 116 ms. The driver cannot account for seconds.

### The initramfs panel-recovery ladder is it

`boot/bringup-init.sh`'s `display_recover()` runs unconditionally at boot and has
a worst case of roughly **13–23 s**:

```sh
# wait for the panel driver's own first read before cycling anything
i=0
while [ "$i" -lt 10 ] && ! dmesg | grep -q 'ana38407 panel id: 00 00 00'; do
    sleep 1
    i=$((i + 1))
done            # <-- up to 10 s
...
i=0
while [ "$i" -lt 3 ]; do
    i=$((i + 1))
    if timeout 5 sh -c 'echo 1 > /sys/class/graphics/fb0/blank' &&
       timeout 5 sh -c 'echo 0 > /sys/class/graphics/fb0/blank'; then
        ... if dmesg | grep -q 'ana38407 panel id: 80 00 04'; then return 0; fi
    fi
    sleep 1     # <-- up to 3 iterations, plus the blank/unblank cost
done
```

* the first loop waits up to **10 s** for the zero-ID line;
* the second runs up to **3** blank/unblank cycles, each followed by `sleep 1`,
  and each cycle is itself a full panel teardown and re-prepare.

So a cold boot where the panel needs the full ladder pays roughly 10 s + 3 ×
(cycle + 1 s) before `switch_root`. A boot where the panel comes up on the first
ID check pays almost none. That variance is what makes the boot feel
inconsistent, and the ladder's own comments record why it exists and why it
retries (tests 041–043 needed the full teardown, not a partial one).

**This is not proposed for change.** `docs/DISPLAY_X710_OFFICIAL_V1.md` and the
retry comments explain that the ladder is what makes a cold boot display at all,
and the brief puts DPU/panel work out of scope.

### Why it matters to the stall investigation

`docs/GPU_GMU_RPMH_STALL_PLAN.md` §4.2 established that the deferred-probe burst
fires 10 s after the **last `driver_register()` that found the work pending**, not
at a fixed offset from late_initcall. Anything that delays the initramfs — such as
this ladder — therefore *moves the burst*. That is the most likely explanation for
the observed spread: 13.3–14.3 s in the four recorded stalls, 35.8 s in the clean
live boot.

It is a hypothesis, not a measurement: no run has yet recorded both the ladder's
duration and the burst timestamp on the same boot. A one-line `record_boot_stage`
with a timestamp before and after `display_recover` would settle it, and that is a
diagnostic-only change to the initramfs, not to the display path.

## 2. What evidence survives a stall

The stall's whole difficulty is that the machine stops being able to tell anyone
what happened. On this port most of the obvious channels are already known to
fail, and one works.

| channel | status | evidence |
|---|---|---|
| **pstore / ramoops** | **does not survive reboot** | `kernel/dts/sm8550-samsung-gts9wifi.dts` records it: the backend registers and the console attaches, but a userspace pmsg record *and* a real sysrq panic both left `/sys/fs/pstore` empty on the next boot, the latter after `pstore: zlib_inflate() failed, ret = -3!`. Stock agrees — its own ramoops node is `status = "disabled"`. **Do not treat `/sys/fs/pstore` as an evidence source.** |
| `sec_log` ring | overwritten by ABL | `AGENT.md`: the bootloader's own log spans 2,096,187 of 2,097,136 bytes, so mainline writes are gone before recovery can read them |
| serial console on the host | only while the host is attached | fine for a live command, useless for an unattended reboot series |
| **`gts9-prev-boot-evidence`** | **works, per boot** | see below |

### The mechanism that does work

`rootfs-overlay/usr/libexec/gts9-prev-boot-evidence` runs every boot and archives
the *previous* boot into `/var/log/gts9-boot-evidence/<utc>-<bootid8>/`. For the
stall series the important fields are in `verdict.txt`:

```
previous_boot_end=clean-shutdown | panic | hard-reset-or-incomplete | unknown
marker_panic=  marker_soft_lockup=  marker_hard_lockup=
marker_hung_task=  marker_rcu_stall=  marker_dpu_timeout=  marker_mmc_timeout=
```

`previous_boot_end` is computed from the previous boot's journal
(`systemd-shutdown` present → clean; a panic marker → panic; otherwise
`hard-reset-or-incomplete`). **That last value is how an unattended reboot is
detected**, and it is exactly the signal the failed series in
`on-device/STALL-SERIES-ATTEMPT.md` was missing when the device rebooted by itself
at ~18:40 and nothing noticed.

Because the collector archives the previous boot's *journal* as well
(`prev-kernel.log`, `prev-all.log`), a stall that panics into `panic=10` leaves its
own report on the microSD for the next boot to preserve — with no host, no
console, and no pstore.

### What this means for the next series

The series does not need the console to survive each round. It needs to:

1. issue a reboot and record the `boot_id` it expects to be replaced;
2. on the next boot, read the newest evidence directory's `verdict.txt` and the
   new `boot_id`;
3. treat `previous_boot_end=hard-reset-or-incomplete` or any non-zero `marker_*`
   as a **captured stall**, and keep that directory;
4. treat a `boot_id` that did not change as `stale-boot` and stop, as
   `reboot-rounds.sh` already does.

That reduces the console's role to "issue the reboot", which is a single short
command — the operation that has been reliable — instead of depending on it
recovering in time to do the collection too.
