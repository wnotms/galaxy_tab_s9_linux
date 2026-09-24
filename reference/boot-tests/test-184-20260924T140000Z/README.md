# test-184 — the 4.7 s → 125 s gap: forensics, fixes, and the observer effect

Object of this round: the watchdog debug profile looked like it stalled the
system for ~120 s on a cold boot, and the stall hunt's own instrumentation may
have been changing the thing it measures. Both are measured here.

## 1. Verdict: output backlog, not a system stall

Recorded from the affected boot (`journalctl -b -2 -o short-monotonic`):

| evidence | value |
|---|---|
| journal timestamps of all 28 watchdog report lines | `[4.646574]` — one instant |
| `ExecMainStartTimestampMonotonic` | `4310086` (4.31 s) |
| `ExecMainExitTimestampMonotonic` | `155868809` (155.87 s) |
| journal entries during the "gap" | 1 at 31 s, 8 at 68 s, 15 at 69 s, 35 at 171 s, 146 at 172 s, then a steady 4-5 every ~15 s |

journald received the entire report at 4.65 s, so **no sysctl was slow**. The
process was blocked for ~151 s writing the same bytes to `/dev/console` →
tty0 → fbcon → DRM, and the console caught up ~150 s later — which is exactly
what appeared on screen as "4.7 s ... 125 s". The journal has real entries
throughout, so the system kept running: `console/fbcon output stalled`, not
`system-wide stall`.

The service's own timing agrees: with `StandardOutput=journal+console` the unit
lived 151 s; with `StandardOutput=journal` the same work takes **325 ms**
(restart on a running system) and **515 ms** on a cold boot
(`ExecMainStart=4204600`, `ExecMainExit=4720307`).

## 2. Fixes in this round

| what | why |
|---|---|
| `gts9-watchdog-debug.service`: `StandardOutput=journal` | the console copy was the 151 s block |
| applier: no `cat "$REPORT"`; one summary line | the full report stays in `/var/log/gts9-watchdog-debug.txt`, `gts9-watchdog-debug status` prints it for a human |
| per-step trace with real monotonic timing | `/run/gts9-watchdog-debug.trace` (tmpfs), copied once to `/var/log/…` after the run: `BEGIN/END <step>`, `start_ms`, `end_ms`, `duration_ms`, `before`, `requested`, `effective`, `result` |
| three independent instrumentation switches | `gts9_watchdog_debug=1` (detectors), `gts9_kmsg_mirror=1` (USB mirror), `gts9_dpu_flight=1` (ftrace stream) — previously one flag switched everything on |
| `pstore_backend` / `pstore_records` reported separately | `/sys/fs/pstore` being empty was reported as "no backend" even though ramoops was registered and printk attached |
| `gts9-acm-getty.service` replaces the generic `serial-getty@ttyGS0` | the generic instance waits for `dev-ttyGS0.device`, which times out when the gadget is created a moment later |
| `serial-getty@ttyMSM0.service` masked | getty-generator creates it from `console=ttyMSM0`; the SoC UART stays a *kernel* console (`console=ttyMSM0`, `earlycon` untouched) |
| stale `/etc/systemd/system/gts9-dpu-flight.service` removed | it shadowed the repository's unit, so the new flag did not apply and the ftrace stream still started (megabytes/s onto the microSD) |

Measured trace, one cold boot (every step is at the 10 ms resolution of
`/proc/uptime`, i.e. nothing is slow):

```
step=kernel.watchdog path=/proc/sys/kernel/watchdog start_ms=1005210 end_ms=1005220 duration_ms=10 before=1 requested=1 effective=1 result=ok
step=kernel.softlockup_panic … duration_ms=10
step=kernel.softlockup_all_cpu_backtrace … duration_ms=10
step=kernel.hung_task_timeout_secs … duration_ms=10
step=kernel.hung_task_panic … duration_ms=10
step=kernel.hung_task_warnings … duration_ms=10
step=kernel.hung_task_all_cpu_backtrace … duration_ms=10
step=workqueue.panic_on_stall … duration_ms=10
step=workqueue.panic_on_stall_time … duration_ms=10
step=kernel.panic_on_oops … duration_ms=10
```

Cold-boot summary line in the journal (one line, by design):

```
gts9-watchdog-debug: armed=1 softlockup=1 hung_task=1 wq=45 panic=10 pstore=ramoops-registered records=0 steps_slow=none total_ms=515
```

## 3. ttyMSM0 and ttyGS0

* `/dev/ttyMSM0` **does exist** (`crw-rw---- root dialout 236,0`) once the GENI
  serial driver has probed. The getty instance came from two places:
  `systemd-getty-generator` (because of `console=ttyMSM0`) and a manual
  enablement link from an earlier install. With nothing attached to that UART
  the getty is useless, and while the node is missing systemd waits for
  `dev-ttyMSM0.device` (90 s timeout). Only that instance is masked; the kernel
  console and `earlycon` stay.
* `/dev/ttyGS0` is the wanted USB console. Its generic getty waits for
  `dev-ttyGS0.device`; the gadget is created by `gts9-usb-acm.service` a moment
  later, so that device unit timed out and the getty failed — after which host
  writes time out too, because nobody has the tty open and the gadget has no OUT
  requests. `gts9-acm-getty.service` (`After=gts9-usb-acm.service`, agetty
  `--autologin root` on ttyGS0) removes the device dependency; the first cold
  boot with it came up with the shell automatically and `systemctl --failed`
  reported 0.

## 4. Observer A/B

`observer-ab.sh [rounds] [profile]` reboots the tablet and records, per round:
the helper's real start→exit time, the ACM getty state, kernel stall markers in
the journal, and the kernel-console capture. Warm resets are labelled as such —
a true cold boot needs the operator, and the early-deferred-probe window is not
the same thing.

* profile A (`gts9_watchdog_debug=1` only, 5 warm rounds):
  `observer-ab-A-summary.txt` — 0 getty timeouts, 0 console stall markers, 0
  failed units, ACM getty active by itself every round, helper 564-593 ms
  (`observer-ab.txt`, `rounds/round-A-*.txt`). Round 4's probe lost the shell
  once and is recorded without a boot_id.
* profile D (all three switches, 3 warm rounds): `observer-ab-D-summary.txt` —
  same result as A. Helper 544-588 ms, ACM getty active, ttyMSM0 masked, 0
  failed units, 0 getty timeouts, 0 console stall markers.
* profile B and C were not run separately (time), and both A and D saw **zero**
  stalls in 8 instrumented boots, so nothing here supports a claim that the
  mirror or the ftrace stream changes the reproduction rate in either
  direction. That is the honest state: the switches are independent and
  measured to take effect (`flight=inactive mirror=inactive` on A,
  `active/active` on D), the rate difference is unmeasured.
* The first flash attempt was interrupted because the *recovery* boot hung at a
  blinking cursor and the Windows adb server had gone stale; after the operator
  force-reset the tablet, TWRP came up, `adb devices` showed `recovery
  product:twrp_gts9wifi`, and the flash completed with `vendor_boot`
  `123f35f2…` → `f1f4ccf7…` verified by readback. Nothing was written during
  the failed attempt.

## 4b. Controlled-stall regression after lowering the instrumentation

Test-183's injector was run again on the new profile (`inject-rounds.sh 1 spin
30`, 30 s with interrupts disabled on one CPU):

```
14:24:36  insmod /root/gts9_stall_test.ko mode=1 seconds=30
14:25:14  PRESENCE usb0525:a4a7=False     # panic -> panic=10
14:25:33  PRESENCE usb0525:a4a7=True      # tablet back
```

Same USB-gap signature as the three 3/3 successes recorded in test-183, on the
same module and the same profile flags. This round's automatic boot_id
comparison came back inconclusive (the harness probe read the pre-round id, and
a follow-up console probe was garbled because profile D keeps the ftrace stream
writing to the microSD), so the verified 3/3 from test-183 stands and this round
adds one observed signature rather than a new confirmed count.

## 5. Still open

* The kernel console on the second ACM port (`CONFIG_U_SERIAL_CONSOLE=y`,
  `console=ttyGS1`) delivers the live kernel log, but its write path is a
  workqueue: at panic time no worker runs, so the panic text itself still does
  not reach the host (measured with a sysrq panic: 26 pre-panic lines captured,
  nothing after).
* `reboot`/`poweroff` can still take minutes: the observed shutdown took ~3.5
  minutes with the ftrace stream writing to the microSD, and the operator saw
  the frozen cursor during it. With `gts9_dpu_flight` off by default that load
  is gone; whether the shutdown still stalls without it is the next measurement.
* pstore: registered, zero records across a reboot — unchanged from test-183.
