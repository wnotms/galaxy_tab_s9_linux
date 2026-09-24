# test-183 — answers

Every answer below is a measurement on this tablet, or a file in this record
that holds the measurement. Where something was tried and failed, it says so.

## 1. Watchdog Kconfig (`CONFIG_*`), resolved for the flashed kernel

```
CONFIG_WATCHDOG=y                     CONFIG_WATCHDOG_CORE=y
# CONFIG_WATCHDOG_SYSFS is not set     # CONFIG_WATCHDOG_NOWAYOUT is not set
CONFIG_QCOM_WDT=y                     # CONFIG_SOFT_WATCHDOG is not set
CONFIG_LOCKUP_DETECTOR=y              CONFIG_SOFTLOCKUP_DETECTOR=y
CONFIG_SOFTLOCKUP_DETECTOR_INTR_STORM=y
# CONFIG_HARDLOCKUP_DETECTOR is not set
CONFIG_DETECT_HUNG_TASK=y             CONFIG_DETECT_HUNG_TASK_BLOCKER=y
CONFIG_WQ_WATCHDOG=y                  CONFIG_BOOTPARAM_WQ_STALL_PANIC=0
CONFIG_MAGIC_SYSRQ=y                  CONFIG_PANIC_TIMEOUT=0
CONFIG_PSTORE=y CONFIG_PSTORE_RAM=y CONFIG_PSTORE_CONSOLE=y CONFIG_PSTORE_PMSG=y
CONFIG_PSTORE_COMPRESS=y              # CONFIG_PSTORE_BLK is not set
```

## 2. Where `nowatchdog` comes from, and how the profile undoes it

It is **Samsung's**, appended by ABL after the command line this repository
builds:

```
[    0.000000] Kernel command line: console=ttyMSM0,115200n8 msm.separate_gpu_kms=1 panic=10
  ... gts9_poweroff_trace=1  msm_drm.dsi_display0=GTS9_ANA38407_AMSA10FA01: ...
  watchdog.stop_on_reboot=0 softdog.soft_panic=1 ... msm_rtb.enable=0 nowatchdog ...
```

The same four parameters are in the owner's live X710 device tree's `bootargs`
(`reference/stock`, live DTS sha256 `7bf40be5…`), so they are the vendor's
intent, not a local experiment. The kernel has no parameter that re-enables the
detectors (`nowatchdog`, `nosoftlockup` only go off), so the profile writes

```
/proc/sys/kernel/watchdog = 1        # proc_watchdog_common -> proc_watchdog_update
```

at boot. No repository command-line profile contains `nowatchdog`
(`tests/test_watchdog_debug_profile.py`).

## 3. Sysctls and parameters applied by the profile

Read back on the device (`/var/log/gts9-watchdog-debug.txt`):

```
kernel.watchdog                     0 -> 1
kernel.softlockup_panic             0 -> 1
kernel.softlockup_all_cpu_backtrace 0 -> 1
kernel.hung_task_timeout_secs     120 -> 45
kernel.hung_task_panic              0 -> 1
kernel.hung_task_warnings          10 -> 5
kernel.hung_task_all_cpu_backtrace  0 -> 1
workqueue.panic_on_stall              0  (deliberately off: cumulative counter)
workqueue.panic_on_stall_time       0 -> 45
kernel.panic_on_oops                  -> 1
panic_reboot=armed (panic=10)
```

`softlockup_panic=` and `workqueue.panic_on_stall_time=` are also on the
profile's command line (both are registered early parameters). The hung-task
pair and `softlockup_all_cpu_backtrace` are **not** — `kernel/hung_task.c`
registers no early parameter for them in this kernel — so they are applied at
runtime and never written onto a command line where they would do nothing.

## 4. Is the soft-lockup detector running?

Yes, and it has produced evidence: `watchdog: BUG: soft lockup - CPU#5 stuck for
361s! [kworker/u32:18:174]` (photographed on 2026-09-24 08:03 during the fifth
stall), plus `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks`,
`enc35 frame done timeout` and `mmc1: Timeout waiting for hardware cmd
interrupt` in the same report. `/proc/sys/kernel/watchdog` reads 0 on a
known-good boot (ABL's `nowatchdog`) and 1 with the profile armed.

## 5. Workqueue watchdog and panic-on-stall

Supported in this kernel (`kernel/workqueue.c`):

* `watchdog_thresh` (seconds, default 30) — `module_param_cb`,
* `panic_on_stall` (unsigned int) — panics when N stall *reports* have
  accumulated (`panic_on_wq_watchdog()`),
* `panic_on_stall_time` (unsigned int, 0 = disabled) — panics when one stall
  lasts that many seconds; message `workqueue: stall lasted %us, ...`.

The profile sets `panic_on_stall_time=45` and leaves `panic_on_stall=0`, because
a hunt must not reboot on the first transient report.

## 6. Does a panic actually reboot the tablet?

Yes, measured twice:

```
08:33:43.451  SENT  echo c > /proc/sysrq-trigger
08:33:55.447  PRESENCE usb0525:a4a7=False     # 12 s later: panic=10 elapsed
08:34:13.143  PRESENCE usb0525:a4a7=True
```

and again at 09:26:29 → gone 09:26:40 → back 09:26:56.

## 7. Where does each round's evidence land?

* host: `rounds/round-N-console.log` (the whole listen-only capture, including
  the kmsg mirror) and `rounds/round-N.txt` (classification),
* host: `rounds/round-N-device.txt` (the tablet-side probe),
* tablet: `/var/log/gts9-boot-evidence/<utc>-<boot_id8>/` — `verdict.txt`,
  `prev-kernel.log`, `prev-signatures.txt`, `pstore/`, `stream/*-tail.txt`,
  `watchdog.txt`,
* tablet: `/var/log/gts9-dpu-stream.txt{,.prev,.1.prev}` (ftrace, dies with the
  microSD path),
* tablet: `/var/log/gts9-watchdog-debug.txt` (profile report).

## 8. How long from stall to watchdog?

Observed on the first unattended recovery: the RPMh warning appears 14.27 s
after boot, the console goes silent immediately after, and the next boot's
uptime shows the tablet reset itself 60-75 s later. The thresholds bound it:
workqueue stall detection at 30 s (`watchdog_thresh`) + 45 s
(`panic_on_stall_time`) or hung-task 45 s, then `panic=10`.

## 9. pstore backend

**Registered but not usable — measured, not assumed.** `ramoops` binds to the
stock `sec_pmsg` carve-out (`ramoops: using 0x200000@0x880900000`,
`pstore: Registered ramoops as persistent store backend`,
`printk: legacy console [ramoops-1] enabled`), but a pmsg record written to
`/dev/pmsg0` and a real sysrq panic both left `/sys/fs/pstore` **empty** on the
next boot, the latter after `pstore: zlib_inflate() failed, ret = -3!`. Stock
agrees — its own ramoops node is `status = "disabled"`. The node is kept with
that result written into it; no claim rests on pstore.

## 10-11. `/dev/watchdog0` and why `qcom_wdt` does not probe

`/dev/watchdog0` does not exist and `/sys/class/watchdog/` is empty.
`CONFIG_QCOM_WDT=y`, and `drivers/watchdog/qcom-wdt.c` matches
`qcom,apss-wdt-ipq5424`, `qcom,kpss-timer`, `qcom,scss-timer`, `qcom,kpss-wdt` —
but `arch/arm64/boot/dts/qcom/sm8550.dtsi` has **no watchdog node at all**, so
there is no device to probe. Nothing was guessed to work around that.

## 12. What the stock X710 says about its watchdog

From the owner's live tree (`reference/stock`):

```
sec,qcom_wdt_core_dev_name = "hypervisor:qcom,gh-watchdog";
qcom,gh-watchdog { compatible = "qcom,gh-watchdog"; };
```

and from the reconstructed stock config (`80693a06…`, the recorded hash):

```
# CONFIG_QCOM_WDT is not set
# CONFIG_SOFT_WATCHDOG is not set
kernel.panic_on_rcu_stall=1        (in bootargs)
```

So stock runs a Gunyah/hypervisor watchdog, not the APSS one mainline supports,
and relies on panic-on-RCU-stall rather than a hardware watchdog for the kind of
wedge seen here.

## 13. Provenance of the device-tree changes in this round

One node, and every number in it comes from the live stock tree: `ramoops` at
`0x8_80900000` for 2 MiB, the region stock reserves as `sec_pmsg_region` and
binds `samsung,pstore_pmsg` to. Sizes: 128 KiB record + 896 KiB console +
1 MiB pmsg = exactly 2 MiB. No watchdog node was added.

## 14. `wdctl`

util-linux's `wdctl` is present but has nothing to talk to on this port
(`/dev/watchdog0` absent); its output is recorded in the round probes.
`RuntimeWatchdogUSec=0` and `RebootWatchdogUSec=10min` are systemd's defaults
here; nothing in this repository arms a runtime watchdog.

## 15. Is `RuntimeWatchdogSec` enabled by default?

No, and it must not be until a watchdog device exists:
`tests/test_watchdog_debug_profile.py` fails if any overlay unit mentions
`RuntimeWatchdogSec`/`RebootWatchdogSec` or writes to `/dev/watchdog*`.

## 16. Automatic recoveries observed this round

| # | trigger | detector | outcome |
|---|---|---|---|
| 1 | real DPU/RPMh stall, 08:41:59Z | soft lockup + RPMh timeout | rebooted itself 60-75 s later (first time on this device) |
| 2 | `echo c > /proc/sysrq-trigger`, 08:33:43Z | - | panic=10 reboot, USB gap 12 s |
| 3 | `echo c > /proc/sysrq-trigger`, 09:26:29Z | - | panic=10 reboot, USB gap 11 s |
| 4 | injected hung task (60 s) | hung task, report on the host | panic, reboot |
| 5-7 | injected soft lockup (30 s) x3 | soft lockup | panic, reboot - 3/3 |

Ten further instrumented boots (the 10-round hunt) stayed clean, so the real
race did not reproduce under the mirror; that is stated rather than hidden.

## 17. Commits for this round

```
99f496d debug: add an X710 watchdog stall-test profile
889ccd9 tests: keep the previous boot's evidence on the X710
181a636 docs: audit the X710 watchdog paths and the stall-recovery loop
65b9123 arm64: dts: qcom: add an X710 ramoops backend on the sec_pmsg carve-out
c3ae8b6 tests: fix the X710 evidence verdict and the stall-loop bookkeeping
```

(plus this directory's record commit.)

(plus the record commit for this directory, and the pre-existing test-181/182
record updates).

## 18. Run identifiers

* boot_ids seen: `e47744c5…` (pre-loop), `8b3ed921…`, `925c4a76…`, `05037404…`,
  `a9a3baee…`; per-round ids are in `rounds/round-N-device.txt`.
* panic runs: 2026-09-24T08:33:4xZ and 2026-09-24T09:26:2xZ.
* first unattended stall recovery: stall at 2026-09-24T08:41:59Z, next boot
  08:42:41Z.

## 19. Known-good image hashes

```
boot.img         822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86
init_boot.img    7d934eac278f9818132764215110b7c58226a31831ca7a7f86ffdc0a7244b24c
vendor_boot.img  3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec
dtb              f49b373462a278fcafb858fa9f59dac174d88b4f14810ad2638509d9c2e9e9be
dtbo.img         c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
vbmeta.img       b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4
```

Flashed during this round: `vendor_boot` `3d65d076…` (profile command line) then
`boot` `dfbe70f4…` + `vendor_boot` `eb8f2b21…` (ramoops).

## 20. Rollback

`rollback.sh` writes the known-good pair back with the same
backup → SHA256 → flash → readback → SHA256 chain, using the images pulled off
the tablet during this round (`boot-ramoops-before.img` = `822ca9dc…`,
`vendor_boot-before.img` = `3c88b36b…`). The three new units are inert without
`gts9_watchdog_debug=1`; `systemctl disable --now gts9-kmsg-console
gts9-watchdog-debug gts9-prev-boot-evidence` removes them entirely.

## 21. Does the profile change the known-good boot?

No. `tests/test_watchdog_debug_profile.py` (14 checks) pins the four existing
command lines by SHA-256, keeps every watchdog parameter out of them, keeps the
runtime-only knobs off the command line, forbids a watchdog device-tree node and
any unit that pets `/dev/watchdog*`, and requires the applier to be inert
without the flag and unable to block the boot.
