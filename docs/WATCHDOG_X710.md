# X710 watchdog audit and the unattended stall-recovery loop

Status: **Phase 1 (software watchdogs) implemented, flashed and validated.**
Hardware watchdog (Phase 2) is audited below and deliberately not enabled.

This document is the record for `reference/boot-tests/test-183-20260924T082600Z/`.
It answers, with evidence, what watchdog hardware and software actually exist on
this port, what was changed, how a stall is turned into an unattended reboot,
and where the evidence of each round lands.

---

## 1. The problem

Five stalls have been recorded on this port (see `docs/DPU_TRACE.md`). They share
one shape:

| symptom | observation |
|---|---|
| when | 13-36 s after boot, repeatedly, over ~10 boots |
| what | one CPU spins in kernel at 100 % system; the stuck worker varies (`pogo_watch_work`, `pm_runtime_work`, `fqdir_free_fn`, `toggle_allocation_gate`) |
| display | `enc35 frame done timeout` repeats, then the panel keeps the last frame |
| storage | `mmc1: Timeout waiting for hardware cmd interrupt` + SDHCI dump |
| RCU | `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks`, `rcu_preempt kthread starved` |
| recovery | none: the tablet never rebooted by itself and needed a ~15-30 s power hold |

Until this round the only evidence was photographs of the tablet's screen,
because the USB console carries userspace output only (§4).

The stall loop in this record fixes the *recovery and evidence* half: a stalled
tablet now panics by itself, reboots by itself, and the next boot collects the
previous round's evidence without a human.

---

## 2. Which watchdogs exist on this port

Measured on the device (`gts9-watchdog-debug status`), not inferred:

| layer | state | evidence |
|---|---|---|
| Linux soft-lockup detector (timer/scheduler) | **available**, disabled at boot by ABL, re-armed by this profile | `/proc/sys/kernel/watchdog` 0→1, `softlockup_panic` 0→1; the detector already produced `watchdog: BUG: soft lockup - CPU#5 stuck for 361s! [kworker/u32:18:174]` on 2026-09-24 08:03 |
| Linux hung-task detector | **available**, sysctl-only in this kernel | `kernel.hung_task_panic`, `kernel.hung_task_timeout_secs` |
| workqueue stall watchdog | **available** | `/sys/module/workqueue/parameters/{watchdog_thresh,panic_on_stall,panic_on_stall_time}` |
| RCU stall panic | **available**, and used by stock | `/proc/sys/kernel/panic_on_rcu_stall`; stock bootargs ship `kernel.panic_on_rcu_stall=1` |
| Linux hard-lockup / NMI detector | **not available** | `# CONFIG_HARDLOCKUP_DETECTOR is not set`; `watchdog_hardlockup_probe()` returns `-ENODEV`, so `kernel/watchdog.c` prints `watchdog: NMI not fully supported` + `watchdog: Hard watchdog permanently disabled` |
| `qcom_wdt` platform watchdog | **no device** | `CONFIG_QCOM_WDT=y`, but `arch/arm64/boot/dts/qcom/sm8550.dtsi` has no watchdog node and `/dev/watchdog0` does not exist; `/sys/class/watchdog/` is empty |
| `softdog` | **not built** | `# CONFIG_SOFT_WATCHDOG is not set` — the vendor's `softdog.soft_panic=1` command-line parameter has no driver to attach to |
| systemd runtime watchdog | **not armable** | `RuntimeWatchdogUSec=0`, no `/dev/watchdog0`; `RebootWatchdogUSec=10min` is unrelated |
| pstore backend | **registered but not persistent** (measured, §5) | `ramoops: using 0x200000@0x880900000`, `pstore: Registered ramoops as persistent store backend` — yet records do not survive a reboot |

The vendor command line, read back from the running kernel, ends with

```
... msm_rtb.enable=0 nowatchdog sec-battery.sales_code=CHN ...
```

`nowatchdog` is **Samsung's**, not this repository's: the same string is in the
owner-supplied live X710 device tree (`reference/stock`, decompiled live DTS
sha256 `7bf40be5a9ededd23bf3c1725252fc28973be9b18b68e25fc5019502e03d723c`), whose
`bootargs` also carry `watchdog.stop_on_reboot=0 softdog.soft_panic=1
kernel.panic_on_rcu_stall=1`. No profile in this repository adds `nowatchdog`,
and none can remove it: ABL appends its own tail after the values built here,
and the kernel only offers off switches (`nowatchdog`, `nosoftlockup`).

### Why stock has no platform watchdog either

The owner's stock config (reconstructed from `reference/stock/config`, sha256
`80693a069d406fbdafe01b73e65e8f1e15b681451bbb53b9d05fde7a93220112`) says

```
# CONFIG_QCOM_WDT is not set
# CONFIG_SOFT_WATCHDOG is not set
```

and the stock device tree's watchdog consumer is a *hypervisor* one:

```
sec,qcom-wdt_core_dev_name = "hypervisor:qcom,gh-watchdog";
qcom,gh-watchdog { compatible = "qcom,gh-watchdog"; };
```

mainline's `drivers/watchdog/qcom-wdt.c` matches only
`qcom,apss-wdt-ipq5424`, `qcom,kpss-timer`, `qcom,scss-timer` and
`qcom,kpss-wdt` — **not** `qcom,gh-watchdog`. So enabling a hardware watchdog
here would need a Gunyah/hypervisor watchdog driver plus a device-tree node
that no current evidence describes. Phase 2 stays open; nothing was guessed.

---

## 3. The debug profile (Phase 1)

New files:

| file | role |
|---|---|
| `boot/cmdline.watchdog-debug.example.txt` | the profile's command line: the known-good minimal-rootfs cmdline plus `softlockup_panic=1 workqueue.panic_on_stall_time=45 gts9_watchdog_debug=1`, keeping `panic=10` |
| `rootfs-overlay/usr/libexec/gts9-watchdog-debug` | runtime applier: re-arms the detectors the ABL disabled, sets the hung-task detector, reports every knob's effective value |
| `rootfs-overlay/usr/lib/systemd/system/gts9-watchdog-debug.service` | oneshot, `After=local-fs.target`, `WantedBy=multi-user.target`, best-effort |
| `rootfs-overlay/usr/libexec/gts9-kmsg-console` | mirrors `/dev/kmsg` onto `/dev/ttyGS0` (§4) |
| `rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service` | `Restart=on-failure`, gated on the same flag |
| `rootfs-overlay/usr/libexec/gts9-prev-boot-evidence` | previous-boot evidence collector (§6) |
| `rootfs-overlay/usr/lib/systemd/system/gts9-prev-boot-evidence.service` | runs at every boot, `Before=gts9-dpu-flight.service` so the trace files are copied before they rotate |

Two knobs are command-line early parameters and two are not, which is why the
profile needs both halves:

* `softlockup_panic=` and `workqueue.panic_on_stall_time=` are registered early
  parameters in this kernel (`kernel/watchdog.c`, `kernel/workqueue.c`), so they
  live on the command line.
* `hung_task_panic` / `hung_task_timeout_secs` have **no** early parameter in
  this kernel (`kernel/hung_task.c` registers none) and
  `softlockup_all_cpu_backtrace` has none either, so the applier writes them at
  runtime. Putting them on a command line would look authoritative in a record
  and do nothing.

The runtime re-arm is the part that cannot be expressed as a parameter at all:

```
/proc/sys/kernel/watchdog  0 -> 1     (proc_watchdog_common -> proc_watchdog_update)
```

— the equivalent of removing ABL's `nowatchdog`, because the kernel's only
command-line switches are `nowatchdog` and `nosoftlockup`.

### Stall thresholds

Applied and read back on the device:

```
kernel.watchdog:                     requested=1  effective=1  (was 1)
kernel.softlockup_panic:             requested=1  effective=1  (was 0)
kernel.softlockup_all_cpu_backtrace: requested=1  effective=1  (was 0)
kernel.hung_task_timeout_secs:       requested=45 effective=45 (was 120)
kernel.hung_task_panic:              requested=1  effective=1  (was 0)
kernel.hung_task_warnings:           requested=5  effective=5  (was 10)
kernel.hung_task_all_cpu_backtrace:  requested=1  effective=1  (was 0)
workqueue.panic_on_stall:            requested=0  effective=0
workqueue.panic_on_stall_time:       requested=45 effective=45 (was 0)
kernel.panic_on_oops:                requested=1  effective=1
panic_reboot=armed (panic=10)
```

45 s is inside the required 30-60 s window: long enough that boot-time latency
is not mistaken for a stall, short enough to be unattended. `panic_on_stall`
stays **0** on purpose — it is the *cumulative* stall counter
(`kernel/workqueue.c:panic_on_wq_watchdog()` panics when N stall reports have
accumulated), and a hunt must not reboot on transient reports;
`panic_on_stall_time` panics only when one stall lasts 45 s.

### Fail-open by construction

The applier exits 0 for every unsupported knob, the unit is a `oneshot` in
`multi-user.target` with `SuccessExitStatus=` and a `TimeoutStartSec`, and it
has no `Requires=`. A broken profile cannot hold up the boot, and without
`gts9_watchdog_debug=1` on the command line it prints one line and touches
nothing — which is why the known-good boot is unaffected (§7).

---

## 4. Why the host console needed a mirror

The command line is `console=ttyMSM0,115200n8 ... console=tty0`: printk goes to
the SoC UART and the local VT. The USB ACM gadget (`ttyGS0`, the COM17 the host
sees) is **userspace only**. Every historic capture agrees — no `Booting Linux`,
no `Kernel panic`, no `drm:` line ever arrived over USB.

The 2026-09-24 08:33 sysrq panic proves the consequence: the panic was triggered
at 08:33:43, the USB link dropped at 08:33:55 (10 s later = `panic=10`) and came
back at 08:34:13, and the panic report itself was **never captured**, because
the gadget is a userspace path and panic() schedules no userspace.

`gts9-kmsg-console` closes that gap for everything up to the panic: it follows
`/dev/kmsg` and writes each record to `/dev/ttyGS0`, so the soft-lockup report,
the DPU timeouts, the RPMh warning and its stack, and the RCU stalls land in the
host capture with kernel timestamps. It cannot capture the panic line itself —
that is what pstore was added for — and it does not work on this device yet (§5).

---

## 5. Persisting the panic report — registered, measured, **not usable yet**

The repo's own `kernel/drivers/samsung-gts9wifi-sec-log.c` writes printk into
Samsung's 2 MiB `sec_log_buf` for recovery's `/proc/last_kmsg`, and its header
comment already concludes that the bootloader overwrites the ring on the next
boot and that pstore/ramoops is the replacement once panic persistence is
confirmed. Two facts made that the obvious next step here:

* the panic path *is* confirmed (§4), and
* the stock device tree names the region to use.

The live X710 tree reserves exactly one 2 MiB "persistent message" carve-out and
binds its durable-log consumer to it:

```
sec_pmsg_region@880900000 {
	compatible = "samsung,carve-out";
	reg = <0x08 0x80900000 0x00 0x200000>;
	phandle = <0x583>;
};
samsung,pstore_pmsg { memory-region = <0x583>; };
```

and stock ships a `ramoops` node with `pmsg-size = <0x200000>`. The board DTS
already reserved that address (`sec_pmsg_mem`), so the change is a conversion,
not a new claim:

```dts
ramoops_mem: ramoops@880900000 {
	compatible = "ramoops";
	reg = <0x8 0x80900000 0x0 0x200000>;
	record-size  = <0x20000>;   /*  128 KiB oops/panic dumps */
	console-size = <0xe0000>;   /*  896 KiB printk */
	pmsg-size    = <0x100000>;  /*    1 MiB userspace pmsg, as stock */
	no-map;
};
```

**Measured result: the backend registers, but records do not survive a reboot.**

```
[    0.000000] OF: reserved mem: 0x0000000880900000..0x0000000880afffff (2048 KiB) nomap non-reusable ramoops@880900000
[    0.137824] pstore: Using crash dump compression: deflate
[    0.137828] printk: legacy console [ramoops-1] enabled
[    0.138043] pstore: Registered ramoops as persistent store backend
[    0.138045] ramoops: using 0x200000@0x880900000, ecc: 0
[    2.376102] pstore: zlib_inflate() failed, ret = -3!
```

Two independent tests, both negative:

| test | action | observed on the next boot |
|---|---|---|
| pmsg round-trip | `echo gts9-pmsg-persistence-… > /dev/pmsg0`, then `systemctl reboot` | `/sys/fs/pstore` empty |
| panic round-trip | `echo c > /proc/sysrq-trigger` with the profile armed (the same panic as §7.4) | `/sys/fs/pstore` empty, `pstore_panic_lines=0` |

Stock's own tree explains it: its `ramoops_region` node is
`status = "disabled"`, and this device's live persistent-log path is
`sec_log_buf` (read by recovery as `/proc/last_kmsg`) plus the bootloader-facing
`sec_pmsg` carve-out. The boot chain writes between our write and our read, and
what is left fails to inflate.

Consequences, and what the loop uses instead:

* `/sys/fs/pstore` is **not** an evidence source on this port. The collector
  still copies anything it finds there (one line, no cost, and the natural place
  to re-test), but no claim rests on it.
* Live kernel evidence comes from the **kmsg mirror** (§4) — that is what
  captured the RPMh warning and its stack during the first unattended stall.
* Per-round evidence comes from `gts9-prev-boot-evidence` (§6) and the host
  capture.
* The node stays enabled because it is the correct mainline binding for the
  carve-out and the honest place to retry once a genuinely persistent region is
  identified. `pstore.compress` is `0444`, so compression cannot even be turned
  off at runtime to isolate the inflate failure.

No address was invented: every number comes from the stock tree recorded in
`reference/stock/MANIFEST.md`.

---

## 6. Evidence pipeline

| source | survives a stall? | used for |
|---|---|---|
| `/sys/fs/pstore/*` | **no** (measured, §5) | nothing: records do not survive the reboot |
| host serial capture (`scripts/console-watch.ps1`) | yes | live kernel messages via the kmsg mirror, the boot banner, the USB-gap timing |
| `/var/log/gts9-boot-evidence/<utc>-<boot_id8>/` | yes | previous-boot journal, marker counts, verdict, trace tails, pstore copies |
| `/var/log/gts9-dpu-stream.txt{,.prev,.1.prev}` | partly | the ftrace stream up to the wedge (dies with the microSD path) |
| `journalctl -b -1` | partly | kernel log until journald loses the microSD |
| `sec_log_buf` ring | no | overwritten by ABL on the next boot; kept as bring-up infrastructure |

`gts9-prev-boot-evidence` writes, per boot:

```
verdict.txt              previous_boot_end=panic|clean-shutdown|hard-reset-or-incomplete
                         marker_panic / _soft_lockup / _hung_task / _rcu_stall / _dpu_timeout / _mmc_timeout
                         pstore_records, pstore_panic_lines, pstore_lockup_lines
prev-kernel.log          journalctl -b -1 -k -o short-monotonic
prev-all.log             journalctl -b -1 -o short-monotonic
prev-signatures.txt      the interesting lines, bounded to 120
pstore/*                 copies of every /sys/fs/pstore record
stream/stream-prev-tail.txt, stream-prev1-tail.txt
watchdog.txt             every knob at this boot + the profile report
cmdline.txt, dmesg-watchdog.txt, boot-id.txt, uptime.txt
```

The newest 8 directories are kept.

---

## 7. Validation record

### 7.1 The profile does not touch the known-good boot

`tests/test_watchdog_debug_profile.py` (10 checks) pins the four existing
command-line profiles by SHA-256, asserts that neither they nor any other
profile mention `nowatchdog` or a watchdog parameter, that the DTS gains no
watchdog node, that no unit enables or pets `/dev/watchdog*`, and that a profile
failure cannot block the boot. Run with:

```sh
python3 -m unittest tests.test_watchdog_debug_profile
```

### 7.2 Reproducible images

The known-good vendor_boot was rebuilt byte-for-byte before anything was
flashed:

```
$ KERNEL_OUT_DIR=.work/build/kout-power-trace ... scripts/build-boot-bundle.sh \
    --cmdline reference/boot-tests/test-179-.../cmdline-power-trace.txt ... --out .work/rebuild-check
3c88b36b7b3f1703ccd751b77522fa6d16596650e627893e3131848c96731dec  vendor_boot.img   # == flashed image
```

The watchdog-debug bundle differs from it only in `vendor_boot` and only by the
three new parameters (`bundle-compare.txt` records the diff, taken from the
cmdline strings inside both images):

```
18a19,21
> softlockup_panic=1
> workqueue.panic_on_stall_time=45
> gts9_watchdog_debug=1
```

### 7.3 Flash record

Every write used backup → SHA256 → flash → readback → SHA256:

| step | partition | before | after | verify |
|---|---|---|---|---|
| watchdog-debug cmdline | vendor_boot | `3c88b36b…` | `3d65d076…` | device-side and readback SHA256 matched |
| ramoops DTB | boot | `822ca9dc…` | `dfbe70f4…` | readback matched |
| ramoops DTB | vendor_boot | `3d65d076…` | `eb8f2b21…` | readback matched |

`flash-write-readback.txt` and `flash-ramoops-write-readback.txt` hold the raw
logs; `sha256sum` values are in `SHA256SUMS`.

### 7.4 Panic → reboot, measured

```
08:33:43.451  SENT  echo c > /proc/sysrq-trigger
08:33:55.447  PRESENCE usb0525:a4a7=False      # panic=10 elapsed
08:34:13.143  PRESENCE usb0525:a4a7=True       # tablet back
08:34:16.562  RECV   gts9 login: root (automatic login)
```

So `panic=10` really reboots this tablet, unattended.

### 7.5 First unattended stall recovery

The first boot with the profile armed (08:41:45) stalled 14 s in, and this time
the tablet recovered by itself:

```
08:41:59  K kern :warn : [ +14.273790] [T57] WARNING: .../drivers/soc/qcom/rpmh.c:386
                                             at rpmh_write_batch+0x1b4/0x25c, CPU#6: kworker/6:0/57
08:41:59  K kern :warn : [  +0.000003] [T57] Workqueue: events pogo_watch_work
...       (console silent; the host probe gave up after 300 s)
08:42:41  uptime=342 s on the next boot -> the tablet rebooted ~60-75 s after the stall
```

`rpmh.c:386` is `WARN_ON(1)` on the `RPMH_TIMEOUT_MS` expiry of an
**active-only RPMh transaction** — the RSC stopped acknowledging. Every later
RPMh client (power domains in `pm_runtime_work`, the pogo keyboard's I2C
runtime-PM votes, interconnect, SDHCI) then stalls too, which is exactly the
observed family of stuck workers, and the SD/DPU timeouts follow. Before this
round the same wedge needed a physical power hold; now the tablet is back on its
own inside ~1 minute with the round's evidence on disk.

---

## 8. The unattended loop

```sh
reference/boot-tests/test-183-20260924T082600Z/gts9-stall-loop.sh [rounds] [window-seconds]
```

Each round listens on COM17 for `window` seconds (no command is ever sent, so a
stalled tablet is not touched), classifies the capture, then reads the tablet's
own evidence directory over the console and writes
`rounds/round-N.txt` + `rounds/round-N-device.txt`. A round that never comes
back is reported as `NO AUTO-REBOOT` and stops the loop, because that is the one
condition only a human can clear.

## 9. Still open

* **pstore**: registered on the stock carve-out and measured negative (§5). Next
  candidate is a region the boot chain does not write, or a read path for
  `sec_log_buf` so recovery's `/proc/last_kmsg` mechanism can be used from Linux.
* **Root cause**: the RPMh active-only timeout is the first symptom, not
  necessarily the cause. Next step is to find what leaves the RSC unresponsive
  in the first 15 s — the pogo keyboard poll (5 s cadence, I2C runtime-PM) is
  the visible trigger, and `pogo_watch_work` also appears in earlier stalls.
* **Phase 2 (hardware watchdog)**: needs a `qcom,gh-watchdog` (Gunyah) driver
  and evidence for its device tree node; mainline `qcom_wdt` has no match for
  it and SM8550's dtsi has no watchdog node.
* **RCU stall panic**: `panic_on_rcu_stall=1` is in stock's bootargs and would
  turn the observed RCU stalls into a panic even earlier. It is not enabled in
  this profile yet (it is a candidate for the next revision, not an untested
  addition to this one).
* **`gts9-dpu-flight.service`**: still installed and enabled as the stall bait;
  it writes to the microSD whenever the tablet boots in this debug profile.
