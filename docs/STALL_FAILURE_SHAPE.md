# The shape of the stall, from a capture that already existed

A live, second-resolution host capture of a *confirmed* failure has been sitting
in this repository since test-184 and was never recognised as one. Reading it
settles the question `test-187/on-device/EVIDENCE-HISTORY.md` left open, and it
also exposes a misattribution in how the evidence archives are cited.

## 1. The capture

`reference/boot-tests/test-184-20260924T140000Z/rounds/console-A-5-watch.txt` is
the COM19 (kernel console) watch held across round A-5 of test-184. Round A-5 was
issued with `systemctl reboot` — `observer-ab.sh:72`,
`console-watch.ps1 -Command 'systemctl reboot' -CommandAtSeconds 6`, no `-f`, no
power button.

The failing boot, host wall-clock, in full:

| time (UTC) | event |
|---|---|
| 13:47:59.389 | watch starts, listen-only |
| 13:48:02.598 | `Reached target multi-user.target` |
| 13:48:08.503 | `Stopping session-1.scope - Session 1 of User root...` — shutdown begins |
| 13:48:09.331 | **`Stopped gts9-prev-boot-evidence.service`** — last line for 28.9 s |
| 13:48:38.234 | `read failed … 端口已关闭` |
| 13:48:39.677 | `PRESENCE usb0525:a4a7=False` — the tablet is gone from the bus |
| 13:48:57.804 | `PRESENCE usb0525:a4a7=True` — a **new** boot enumerates |

Measured from it:

* the shutdown ran **23 lines in 0.828 s**, then stopped dead;
* **28.903 s of total silence** on a console that had been printing ~28 lines/s;
* **31.174 s** from the first `Stopping` to the device leaving the bus;
* **zero** `systemd-shutdown` lines, where a clean shutdown prints them 17 times
  (test-187 `shutdown-1-verdict.txt`: `systemd_shutdown_seen=17`);
* zero `Connection terminated`, zero panic, zero lockup banner.

## 2. It is the same boot as the archived failure

The boot immediately after this one ran the evidence collector at 13:48:58.895
and reported:

```
gts9-prev-boot-evidence: /var/log/gts9-boot-evidence/20260413T193807Z-8d7db274
    previous_boot=present end=hard-reset-or-incomplete panic=0 lockup=0 hung=0 rcu=0 dpu=0 mmc=0
```

so the boot the capture watched is the one archived as `…-8d7db274`. The archived
journal's last three lines confirm it line for line — the console capture's final
message is the same message:

```
[   70.506420] systemd[1]: Stopping gts9-power-key.service ...
[   70.506685] systemd[1]: gts9-prev-boot-evidence.service: Deactivated successfully.
[   70.506895] systemd[1]: Stopped gts9-prev-boot-evidence.service ...
```

`EVIDENCE-HISTORY.md` quotes exactly this tail and stops there, because the
journal stops there. The console capture carries on for another 28.9 s and shows
what happened next: nothing, and then a reset.

## 3. What that settles

`EVIDENCE-HISTORY.md` listed three explanations it could not separate. The
capture separates them:

| explanation | verdict |
|---|---|
| (1) "a genuine hang whose journal simply stops" | **confirmed**, and it lasted 28.9 s before the reset |
| (2) "an orderly but *fast* shutdown where journald stopped before flushing the `systemd-shutdown` lines" | **refuted.** Nothing was shutting down during those 28.9 s: the console was silent, so the messages were not being produced, not merely unflushed |
| (3) "a reset issued by something other than `systemctl reboot` (for example `reboot -f`)" | **refuted.** The reboot was `systemctl reboot`, and the console shows an ordinary systemd shutdown start |

It also confirms the live signature in
`test-187/on-device/STALL-SIGNATURE.md` from a *different* episode: kernel alive
(`usb0525:a4a7` stayed on the bus for the whole 28.9 s — the gadget was never torn
down), userspace stopped, then a reset.

**Which agent resets the machine is only partly established.** The capture alone
does not say who reset it at ~monotonic 99 s — the console is silent and there is
no panic. §4 argues the kernel's own paths out of contention from source and
config, which leaves an out-of-kernel source; naming *that* source is still open
(§8).

## 4. Who resets it — and what demonstrably did not

The 28.9 s hang ends with a reset. **Nothing in mainline reset it.** That is not a
new finding — `docs/WATCHDOG_X710.md` §"layers" and
`test-183/ANSWERS.md` §10-11 already established it from source, config and the
device — but it had not been connected to the failure:

* **No watchdog device exists on this board.** `CONFIG_QCOM_WDT=y`, but
  `arch/arm64/boot/dts/qcom/sm8550.dtsi` has **no `wdt` or `watchdog` node at
  all** (a grep for either word over the whole file returns nothing at the pinned
  revision), and `drivers/watchdog/qcom-wdt.c:369-372` matches only
  `qcom,apss-wdt-ipq5424`, `qcom,kpss-timer`, `qcom,scss-timer` and
  `qcom,kpss-wdt`. `/dev/watchdog0` does not exist and `/sys/class/watchdog/` is
  empty.
* **`softdog` is not built** (`CONFIG_SOFTDOG` unset), so the
  `softdog.soft_panic=1` ABL injects is inert; `CONFIG_ARM_SMC_WATCHDOG` and
  `CONFIG_PMIC_WATCHDOG` are unset, and systemd's runtime watchdog is not armable
  (`RuntimeWatchdogUSec=0`).
* **`panic=10` did not fire.** A panic prints at `KERN_EMERG`, bypassing the
  profile's `loglevel=4`, and the console was silent for the whole 28.9 s.

So the reset came from outside mainline's software stack. The one concrete
candidate the project already has on record is the vendor's own watchdog: the
stock X710 DTS declares

```
sec,qcom_wdt_core_dev_name = "hypervisor:qcom,gh-watchdog";
qcom,gh-watchdog { compatible = "qcom,gh-watchdog"; };
```

i.e. on stock firmware the watchdog is a **Gunyah hypervisor** device, chosen
deliberately over the APSS one. Mainline has neither a node nor a driver for it,
and this round's scope explicitly excludes writing one. It is therefore the
leading candidate for the reset — and it stays a candidate: **no measurement in
the capture identifies it**, and nothing here shows it is even armed during a
mainline boot. What is established is the narrower, firmer claim that the reset
was not a kernel watchdog and not `panic=`.

What the armed detectors did *not* report also narrows the failure. The failing
boot armed them itself, and said so at 4.76 s:

```
gts9-watchdog-debug: armed=1 softlockup=1 hung_task=1 wq=45 panic=10 pstore=ramoops-registered records=0
```

`armed` is `/proc/sys/kernel/watchdog`, which the helper sets to 1 at runtime to
undo the ABL's `nowatchdog`, so the soft-lockup detector really was running.

| detector | threshold in this profile | could it have fired in 28.9 s? |
|---|---|---|
| soft lockup (`softlockup_panic=1`) | `watchdog_thresh` 10 ⇒ 20 s (`kernel/watchdog.c:50`, `get_softlockup_thresh()`) | **yes, and it did not** |
| hung task (`hung_task_panic=1`) | 45 s, applied at runtime by `gts9-watchdog-debug` | no — 28.9 s is inside it, so its silence proves nothing |
| workqueue stall (`panic_on_stall_time=45`) | 45 s | no — same |

The soft-lockup row is the informative one: a CPU stuck in kernel mode for 20 s
would have produced a report and, with `softlockup_panic=1`, a panic banner. There
was neither. That supports the live signature — **kernel healthy, userspace
stopped** — rather than a kernel lockup. It is an inference from silence, so it
holds only if printk could still emit during the hang; the USB gadget stayed
enumerated throughout, but that alone does not prove the console path was alive.
The inference is therefore offered as the best reading of the evidence, not as a
measurement.

## 5. Where in the shutdown it stops

The capture gives more than a duration: it says which stop jobs were outstanding
when everything went quiet. Comparing the failing sequence with a clean one
(`test-187/shutdown-1-console.log`, same profile) lines the two up exactly — the
failing run's last line is a line the clean run also prints, one step before it
carries on:

```
                       FAILING (A-5)                     CLEAN (test-187 r1)
Stopping session-1.scope         13:48:08.503      Stopping session-1.scope
Stopping cron.service            13:48:09.314      Stopping cron.service
Stopping gts9-acm-getty.service  13:48:09.316      Stopping gts9-acm-getty.service
Stopping getty@tty1.service      13:48:09.325      Stopping getty@tty1.service
Stopping gts9-power-key.service  13:48:09.327      Stopping gts9-power-key.service
Stopped  gts9-prev-boot-evidence 13:48:09.331      Stopped  gts9-prev-boot-evidence
        <28.9 s of silence>                        Stopped  gts9-watchdog-debug
        <reset>                                    Stopping ssh.service
                                                   Stopping systemd-random-seed.service
                                                   ... and on to systemd-shutdown
```

So the shutdown stalled with **five stop jobs outstanding, none of which ever
reached `Stopped`**:

* `session-1.scope`
* `cron.service`
* `gts9-acm-getty.service` — owns `ttyGS0`, the USB ACM console
* `getty@tty1.service`
* `gts9-power-key.service` — a daemon that only toggles the panel backlight

That is the narrowest localisation of the failure obtained so far, and it is the
list to inspect first if the stall recurs.

It also explains why nothing in the kernel reported. A systemd stop job waiting on
a process is invisible to `softlockup`, `hung_task` and the workqueue watchdog
until their thresholds expire, and systemd's own escape hatch —
`DefaultTimeoutStopSec`, 90 s — had not expired either. **The external reset at
28.9 s arrived before systemd could give up on those jobs and continue.** That is
consistent with never seeing a `job timed out` line, and it means the 28.9 s is a
property of the reset source, not of the hang.

Two cautions: the clean captures are from the **post-fix** kernel and this one is
pre-fix, so the unit sets differ slightly; and the clean captures come from
test-187's `shutdown-capture.sh`, which raises the console loglevel. What the
argument uses is the *sequence of stop jobs*, which is userspace output and
unaffected by the kernel loglevel.

## 6. Why it was missed for five rounds

`observer-ab.sh:93` scored this capture with:

```sh
console_stall_markers=$(count 'soft lockup|hung_task|workqueue: stall|Kernel panic|rpmh_write_batch|frame done timeout' "$klog")
```

Every one of those patterns is a *banner*, and the failure produces no banner at
all. The classifier looked for text that the failure does not emit, so the round
was recorded as `console_stall_markers=0` and passed over. The signature that
does identify it — **a shutdown that starts and never reaches
`systemd-shutdown`** — was only named two rounds later, in round 7.

The lesson generalises to every future round: **the absence of a line is the
signal.** A capture with `sd_shutting_down != 0` and `systemd_shutdown_seen == 0`
is a captured failure, and no amount of banner-scanning will ever see it. Both
`test-187/shutdown-capture.sh` and `test-188/shutdown-series.sh` classify that
way; the earlier harnesses did not.

## 7. What the archive name does and does not identify

Reading this capture required resolving which boot the archive describes, and the
answer is not what the documents assume.

`rootfs-overlay/usr/libexec/gts9-prev-boot-evidence` creates:

```sh
boot_id=$(cat /proc/sys/kernel/random/boot_id)     # THIS boot
stamp=$(date -u +%Y%m%dT%H%M%SZ)                   # this boot's clock
dir=$DEST_ROOT/$stamp-$short_id                    # ... naming THIS boot
```

while `prev-kernel.log`, `prev-all.log` and every `marker_*` /
`previous_boot_end=` field inside describe the **previous** boot. So:

* the directory `…-8d7db274/` was created **by** boot `8d7db274`, and its contents
  are the boot **before** it;
* `verdict.txt:boot_id=` is the collecting boot, which is why the round-A-5 probe
  read `boot_id=8d7db274` *after* the failure — `8d7db274` is the survivor;
* **the failing boot's own id was recorded nowhere.**

Consequences for existing text:

* `EVIDENCE-HISTORY.md` and `SHUTDOWN-SERIES-RESULT.md` refer to
  "`176925b2`, `8d7db274`" as the failures. They are the two boots that
  *followed* the failures. The data they quote is right; the labels name the
  wrong boot.
* `STALL-SIGNATURE.md` says "`/var/log/gts9-boot-evidence/…-8d7db274/` records the
  boot that ended this way". The file it then quotes is the failing boot's log, so
  the substance holds — but `8d7db274` is the collector's id, not the failure's.

Two fixes follow, both applied:

1. the collector now records `previous_boot_id=` in `verdict.txt`, taken from the
   same `journalctl -b -1` selection that produced `prev-kernel.log`, so an
   archive can finally name the boot it describes;
2. the harnesses that picked "the newest archive" with
   `ls -1d /var/log/gts9-boot-evidence/*/ | tail -1` now use
   `ls -1dt … | head -1`. The device has no RTC: **eight archives share only two
   distinct `<utc>` stamps**, so name order is not age order, and the tie between
   same-stamp directories was being broken by a random `boot_id8`. The
   collector's own `KEEP=8` pruning already used `ls -1dt`, which is the
   acknowledgement that only mtime is trustworthy here.

## 8. What is still open

* **whether the Gunyah hypervisor watchdog is what resets the machine ~29 s in.**
  §4 shows the reset is not a kernel watchdog and not `panic=`, and identifies
  `qcom,gh-watchdog` - the watchdog stock firmware deliberately uses - as the
  leading candidate. Nothing measures it, and arming or driving it is out of scope
  for this round.
* **whether this failure is the one the current kernel no longer produces.** The
  capture is from the pre-fix kernel. 16 clean cycles on the AOSS-QMP + IPCC
  kernel and the test-188 series on the current one bound its rate; they do not
  identify it.
* **whether the two archived failures are the same phenomenon as each other.**
  `…-176925b2`'s predecessor ended at 344.7 s with a root login on ttyGS0 and no
  shutdown at all, which is a different last line from this one. Only one of the
  two now has an independent live capture.
