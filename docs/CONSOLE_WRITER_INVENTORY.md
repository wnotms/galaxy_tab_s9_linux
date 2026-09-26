# Every userspace console writer in this repository

Inventory of everything in this repository that can write to a console device from
userspace, so each writer can be judged against the two *measured* blocking paths:

* **Path 1 — gadget.** `/dev/console` → `ttyGS1` (host COM19) → `n_tty_write()` waits on
  `tty->write_wait` until the gadget tty has room. With nothing draining COM19 the write
  blocked indefinitely: 60 KiB took the full timeout and completed the instant COM19 was
  opened (`docs/BOOT_CONSOLE_BLOCK.md:59-68`).
* **Path 2 — display.** `/dev/console` → `tty0` → `fbcon` → DRM. `gts9-watchdog-debug`
  spent 151 s of a cold boot on 28 lines written this way while journald had the same
  bytes at the same `[4.646574]` instant
  (`rootfs-overlay/usr/libexec/gts9-watchdog-debug:24-42`, `docs/WATCHDOG_X710.md`).

**The repository changed while this inventory was being written.** The removal of both
serial debug consoles landed mid-task (a large uncommitted change set, on top of
`7e552a6`). This report describes the **current working tree**, and each finding says
what the change did to it. The change set is: all 11 `boot/cmdline*.example.txt`,
`boot/bringup-init.sh`, `boot/minimal-rootfs-init.sh`, `boot/minimal-rootfs-state.sh`,
`kernel/config/gts9wifi-mainline.fragment`, `kernel/patches/README.md`,
`kernel/patches/pending/README.md`, the deletion of
`rootfs-overlay/usr/lib/systemd/system/gts9-acm-getty.service`, and edits to
`rootfs-overlay/usr/libexec/{gts9-enable-units,gts9-kmsg-console,gts9-usb-acm}`,
`rootfs-overlay/usr/lib/systemd/system/{gts9-kmsg-console,gts9-usb-acm}.service`,
`scripts/build-kernel.sh`; plus the new untracked file `rootfs-overlay/etc/gts9-usb-net`.

All line numbers below are against that current state. Hashes of the files this report
depends on are recorded in "Method and scope" so a later reader can tell whether the
report is still describing their tree.

---

## Method and scope

Searched (`.git`, `out/`, `.work/`, `reference/boot-tests/`, `__pycache__` excluded):

| Scope | Depth |
|---|---|
| `boot/*.sh`, `boot/*.c` | read in full: `bringup-init.sh` (1470 lines), `minimal-rootfs-init.sh` (241), `minimal-rootfs-state.sh` (206), `gts9-minimal-pid1.c` (398), `gts9-exec-default.c`, `gts9-reboot-mode.c`, `gts9-to-recovery.sh`, `gts9-debian-to-recovery.sh`; all 11 `cmdline.*.example.txt` + `bootconfig.example.txt` |
| `rootfs-overlay/**` | every file read in full: 15 units, 11 `usr/libexec` helpers, `etc/gts9-usb-net`, 1 logind drop-in |
| `scripts/**` | only what configures the tablet: `install-debian-rootfs.sh`, `install-rootfs-diagnostics.sh` (deployment), `stall-ab.sh`, `gts9-debug-channel.sh`, `gts9-kernel-alive.sh`, `flash-boot.sh`, `screenshot-tablet.sh`, `wifi-*.sh`, `build-kernel.sh` |

Searched for: `/dev/console`, `/dev/tty{0,1,GS0,GS1,MSM0}`, `StandardOutput=`,
`StandardError=`, `StandardInput=`, `TTYPath=`, `journal+console`, `console=` outside the
kernel command line, `>`/`>>` redirections into `/dev/*`, `mesg`, `wall`, `write`, `tty`,
`/dev/kmsg`, `/dev/pmsg0`, `logger`, `systemd-cat`.

**Not read line by line** (declared, not assumed): the 49 files in `docs/`, `tests/**`
(pattern-searched only), `kernel/**` other than the config fragment and patch READMEs
(pattern-searched), `reference/**` (excluded by instruction), and the host-only Windows
PowerShell helpers `scripts/*.ps1` (pattern-searched). The `.ps1` files run on the host
and open the PC's COM port from the host side, so they are not tablet-side writers — but
they are the transport that several `scripts/*.sh` use to reach the tablet, which
matters in section 3 below.

Two kernel facts that shape the classification, read from the vendored tree at
`.work/linux-mainline`:

1. `/dev/console` resolves to the **first entry of `console_list`**:
   `console_device()` iterates `for_each_console_srcu()` and breaks on the first console
   whose `->device()` returns a driver (`kernel/printk/printk.c:3577-3598`), and only the
   console holding `CON_CONSDEV` sits at the head
   (`hlist_add_head_rcu` guarded by `newcon->flags & CON_CONSDEV`,
   `kernel/printk/printk.c:4190-4198`). `CON_CONSDEV` is set by
   `try_enable_preferred_console()` when `i == preferred_console`, and
   `__add_preferred_console()` sets `preferred_console = i` for **each** new entry — so
   the **last** `console=` argument wins, which is the documented cause of
   `/dev/console` being COM19.
2. `console=null` therefore **is** a real console once `CONFIG_NULL_TTY=y`, and it is
   non-blocking: `ttynull_write()` returns `count` without waiting and
   `ttynull_write_room()` returns 65536 (`drivers/tty/ttynull.c:32-41`). Its
   registration order matters: `ttynull_init()` is a `module_init()`
   (`drivers/tty/ttynull.c:106`, i.e. device_initcall level,
   `include/linux/init.h:306`) whereas `vt_console_driver` registers from
   `console_initcall(con_init)` (`drivers/tty/vt/vt.c:3906-3910`), which runs earlier.
   With `try_enable_preferred_console()` setting `CON_CONSDEV` only for
   `i == preferred_console`, the panel VT keeps the head and `console=null` — which ABL
   appends last — does **not** take `/dev/console` away from it. Either way
   `/dev/console` can no longer be a gadget port, and `ttynull_write()` cannot block.

  This is why `CONFIG_NULL_TTY=y` is load-bearing and why
  `scripts/build-kernel.sh:175-180` asserts it, and why the retired kernel patch 0003
  (`ignore_console_null`) is no longer needed
  (`kernel/config/gts9wifi-mainline.fragment:213-229`,
  `kernel/patches/pending/README.md:22-24`).

Classes:

* **(A) BLOCKING RISK** — a direct userspace write to a console device that can block.
* **(B) SAFE** — `/dev/kmsg`, a log file, the journal only, or a tty guaranteed
  non-blocking.
* **(C) CONDITIONAL** — the reader must judge whether it can block.

### Verification hashes (working tree as reported)

```
a0be4a4497eaad28fc0fdf42a217bb43  boot/bringup-init.sh
fed0e7cfe299f2ec19e37d6f09ba720f  boot/minimal-rootfs-init.sh
a40db7d207c11b911887523e9bf8fe32  boot/minimal-rootfs-state.sh
3b11ff6b3ced44e1956868629f8e7599  boot/gts9-minimal-pid1.c
ce304e24a34a63d4fa5c0f3db8523a11  rootfs-overlay/usr/libexec/gts9-enable-units
4392aeeba8154084e142dbff41bfd922  rootfs-overlay/usr/libexec/gts9-kmsg-console
b6cc393e5963442021cdf982a285277c  rootfs-overlay/usr/libexec/gts9-usb-acm
3f87daef40a1c2e4b546dc016a681194  rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service
8bb8da71f79ac0ea77af40d6d21b5669  rootfs-overlay/etc/gts9-usb-net
```

**One hash above is superseded.** `rootfs-overlay/usr/libexec/gts9-enable-units` changed
again while this report was being finalised: it is now
`2943adba6220b26727face1e2e0cfaf5` (113 lines, up from 83). Question 7 describes that
newer revision. Every other hash was re-checked and still matches.

---

## (A) Blocking risks, one subsection each

### A1 — `boot/bringup-init.sh:1397-1400` — USB marker writes to `/dev/ttyGS0`

```sh
1397:        printf 'GTS9-SERIAL-MARKER ready\n' > /dev/ttyGS0 2>/dev/null
1398:        printf 'GTS9-SERIAL-MARKER uname=%s\n' "$(uname -r 2>/dev/null)" > /dev/ttyGS0 2>/dev/null
1399:        printf 'GTS9-SERIAL-MARKER uptime=%s\n' "$(cat /proc/uptime 2>/dev/null | cut -d' ' -f1)" > /dev/ttyGS0 2>/dev/null
1400:        printf 'GTS9-SERIAL-MARKER end\n' > /dev/ttyGS0 2>/dev/null
```

Gated by `[ -c /dev/ttyGS0 ] && [ "$USB_CONSOLE_MODE" = marker ]` (line 1392), which needs
`gts9_usb_console=marker` on the command line (`USB_CONSOLE_MODE` defaults to `shell`,
line 513). Class **(A)**: `/dev/ttyGS0` is the same gadget device class as the measured
blocker — `gs_write()` behind `n_tty_write()`. Four short lines, so the exposure is small,
but it is a direct write to a gadget tty with no reader guaranteed. **Unaffected by the
2026-09-26 change**: `gts9-usb-acm` still creates `acm.usb0`/`acm.usb1`
(`gts9-usb-acm:237-249`), so `/dev/ttyGS0` still exists — it is simply no longer a
*kernel* console.

### A2 — `boot/bringup-init.sh:1428-1429` and `1430-1433` — interactive shell on `/dev/ttyGS0`

```sh
1427:        log 'handing /dev/ttyGS0 to an interactive shell'
1428:        printf '\nGTS9 bring-up console.  Log: cat /tmp/bringup-report.txt\n' > /dev/ttyGS0 2>/dev/null
1429:        printf 'Type gts9-to-recovery to reboot into TWRP.\n\n' > /dev/ttyGS0 2>/dev/null
1430:        while :; do
1431:            PS1='gts9# ' /bin/sh -i </dev/ttyGS0 >/dev/ttyGS0 2>&1
1432:            log 'usb shell ended (host closed the port); reopening'
1433:        done
```

Gated by `[ -c /dev/ttyGS0 ] && [ "$USB_CONSOLE_MODE" != marker ]` (line 1410) — the
**default** `shell` mode, so this is the path a normal `gts9_usb_gadget=acm` boot takes.
Class **(A)**: a gadget tty handed to an interactive shell under an unbounded `while :`
retry loop, which is exactly the shape that blocked on ttyGS1. The code's own comment at
1417-1420 concedes the mechanism for the kernel log — *"`cat /dev/kmsg` on a port nobody
is draining fills the tty buffer and then blocks the shell's own output"* — while leaving
the shell itself on that port. **This is the largest remaining blocking risk in the
repository** after the console removal, and it is in the *initramfs*, where the new NCM/ssh
transport does not exist yet (see section 3).

### A3 — `boot/bringup-init.sh:1424` — `cat /dev/kmsg > /dev/ttyGS0`

```sh
1421:        case "$USB_CONSOLE_MODE" in
1422:            shell+kmsg)
1423:                log 'streaming the kernel log to /dev/ttyGS0 as well'
1424:                ( cat /dev/kmsg > /dev/ttyGS0 2>/dev/null ) &
```

Class **(A)**: a background writer into a gadget tty, opt-in via
`gts9_usb_console=shell+kmsg` (line 1421). If COM19 is unread the background `cat` blocks
in `n_tty_write()` — the behaviour lines 1417-1419 describe.

### A4 — `boot/bringup-init.sh:36,39` — the boot-trace descriptor on `/dev/tty0`

```sh
35:        [ -c /dev/tty0 ] || return 0
36:        exec 3>/dev/tty0 || return 0
37:        BOOT_TRACE_CONSOLE_FD_OPEN=1
38:    fi
39:    printf '\r\n%s\r\n' "$*" >&3 2>/dev/null || true
```

Class **(A)** — this is **path 2**, the 151 s display stall. Opt-in via
`gts9_boot_trace_console=1` (parsed at lines 128-133; carried by
`boot/cmdline.boot-trace.example.txt` and `boot/cmdline.poweroff-trace.example.txt`).
Called from `record_boot_stage()` (line 103) and `record_boot_failure()` (line 110), so it
fires on *every* boot stage transition once armed. The fd is deliberately held open across
the `/dev` move (comment at line 34). **Untouched by the 2026-09-26 change** — this is now
the primary remaining console-blocking mechanism, because `tty0` is the one console left.

### A5 — `boot/bringup-init.sh:228` and `967-968` — unconditional `/dev/tty0` markers

```sh
227: if [ -c /dev/tty0 ]; then
228:     printf '\nGTS9 mainline: early display console ready\n' > /dev/tty0 2>/dev/null
229: fi
```

```sh
967: if [ -c /dev/tty0 ]; then
968:     printf '\nGTS9 mainline: console on the AMSA10FA01 panel (2560x1600)\n' > /dev/tty0 2>/dev/null
969:     log 'display: wrote a marker line to /dev/tty0'
```

Class **(A)**: two unconditional userspace writes to `tty0` (path 2). `2>/dev/null` does
not protect against a *blocking* write, only against errors. Bounded to one write each.
**Untouched by the change**, and now on the only live console.

### A6 — `boot/bringup-init.sh:1238,1252,1260,1262` — the panel shell on `/dev/tty1`

```sh
1237:        while :; do
1238:            printf '\033c' > /dev/tty1 2>/dev/null
...
1251:                printf 'USB shell: /dev/ttyGS0\r\n\r\n'
1252:            } > /dev/tty1 2>/dev/null
...
1260:                setsid /bin/sh -c 'PS1="gts9# " exec /bin/sh -i </dev/tty1 >/dev/tty1 2>&1'
1262:                PS1='gts9# ' /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
```

Class **(A)**: `/dev/tty1` is the same `tty0`→fbcon→DRM display path as A4/A5. The loop
runs in a background subshell (`( … ) &` at 1236/1266), so PID 1 is not held, but the
measured backlog on this path is ~150 s. This is `start_panel_shell` — see question 4.
Line 1251's banner text is now **stale**: it advertises a `/dev/ttyGS0` shell that no
longer exists.

### A7 — `boot/bringup-init.sh:1458-1470` — the PID 1 fallback shell

```sh
1458: while :; do
1459:     if [ -c /dev/tty1 ]; then
1460:         /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
1461:     elif [ -c /dev/console ]; then
1462:         /bin/sh -i </dev/console >/dev/console 2>&1
1463:     else
1464:         log 'no usable console for the PID 1 shell; waiting'
1465:         sleep 5
1466:         continue
1467:     fi
1468:     log 'console shell ended or unavailable; PID 1 remains alive, retrying in 5s'
1469:     sleep 5
1470: done
```

Class **(A)**, but **re-classified from the gadget path to the display path by the
2026-09-26 change**. Before the change this loop was `/bin/sh -i </dev/console
>/dev/console 2>&1` and was the writer `docs/BOOT_CONSOLE_BLOCK.md:43-57` names as the
measured gadget blocker. The comment at lines 1441-1457 is accurate and explicit about
this: `/dev/console` "can only resolve to tty0 or to ttynull, and ttynull_write() returns
without waiting", so the shell is "pinned to `/dev/tty1` anyway rather than left on
`/dev/console`, because the shell must never depend on which console the kernel happened
to prefer".

The net effect is a deliberate trade: the gadget deadlock is gone, and in its place the
shell now uses `tty1` (path 2) as first choice. That is a *bounded* 150 s-class queue
delay on a path that does drain, not an unbounded block — but it is the same display path
the 151 s stall was measured on, so it should be tracked as such rather than considered
closed. The `else` branch (1463-1466) is correct defensive coding: an absent `tty1` no
longer produces an unredirected `sh -i`. Reachability in question 4.

### A8 — `boot/minimal-rootfs-init.sh:31-36` — fallback `minimal_emit()`

```sh
31:    if [ -c /dev/console ]; then
32:        printf '%s\n' "$*" > /dev/console 2>/dev/null || true
33:    fi
34:    if [ -c /dev/tty1 ]; then
35:        printf '%s\n' "$*" > /dev/tty1 2>/dev/null || true
36:    fi
```

Class **(A)** for `/dev/tty1` (path 2); the `/dev/console` half can no longer be a gadget.
This definition is a **fallback only** — it is overwritten by `minimal-rootfs-state.sh`
via `. "$MINIMAL_STATE_LIB"` at lines 50-51, and survives only when
`/minimal-rootfs-state.sh` is missing, in which case line 53 emits the warning. Invoked by
the stage/fail helpers defined at lines 41-48, by `minimal_rescue_shell()` (67-101), and by
the pseudo-mount failure paths (123-142). Question 1 covers the call sites.

### A9 — `boot/minimal-rootfs-init.sh:89-100` — the minimal rescue shell

```sh
89:    while :; do
90:        if [ -c /dev/tty1 ]; then
91:            /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
92:        elif [ -c /dev/console ]; then
93:            /bin/sh -i </dev/console >/dev/console 2>&1
94:        else
95:            minimal_emit 'no usable console for the rescue shell; waiting'
96:            sleep 5
97:            continue
98:        fi
99:        sleep 1
100:    done
```

Class **(A)** for `tty1`. **Same re-classification as A7**, and the comment at lines 82-88
says so: *"Preferring tty1 over /dev/console is deliberate … With the serial consoles
removed it can no longer resolve to ttyGS, but the rescue shell is the last line of
defence and must not depend on that."* Reached only from `minimal_fail()` (lines 103-106)
and the pseudo-mount failure paths. The old `else` branch was a bare `/bin/sh -i` on PID
1's inherited stdio; it is now a bounded sleep, which is an improvement.

### A10 — `boot/minimal-rootfs-state.sh:43-55` — the active `minimal_emit()`

```sh
43: minimal_emit() {
44:     minimal_message=$*
45:     printf '%s\n' "$minimal_message"
46:     if [ -w /dev/kmsg ]; then
47:         printf 'gts9-minimal: %s\n' "$minimal_message" > /dev/kmsg 2>/dev/null || true
48:     fi
49:     if [ -c /dev/console ]; then
50:         printf '%s\n' "$minimal_message" > /dev/console 2>/dev/null || true
51:     fi
52:     if [ -c /dev/tty1 ]; then
53:         printf '%s\n' "$minimal_message" > /dev/tty1 2>/dev/null || true
54:     fi
55: }
```

Class **(A)** for `tty1` (path 2). **This is the version that actually runs** for the
`gts9_minimal_rootfs=1` profile, because `minimal-rootfs-init.sh:50-51` sources this file.
Called on every stage (`minimal_state_stage`, line 126), every failure
(`minimal_state_fail`, line 132) and on persist enable (line 144). The comment at lines
35-42 was updated by the change to state the new reasoning: *"stdout is the panel VT now,
not a serial console … /dev/console is kept because this runs in the initramfs on failure
paths where it is the most likely endpoint to exist at all, and it can no longer be a port
that blocks."* Question 2 covers the call sites.

### A11 — `boot/gts9-minimal-pid1.c:105-110` — static trampoline `emit()`

```c
105: static void emit(const char *message, long length)
106: {
107: 	sys_write(2, message, length);
108: 	write_path("/dev/console", message, length);
109: 	write_path("/dev/tty1", message, length);
110: }
```

`write_path()` (lines 94-103) opens with `O_WRONLY | O_NONBLOCK`. On a tty, `O_NONBLOCK`
at open time makes `n_tty_write()` return `-EAGAIN` rather than sleep — so this **cannot
hang**, but the callers do not retry and the data is **silently discarded** on `-EAGAIN`.
That silent-loss behaviour is not documented at the call site. Class **(A)** for
`/dev/tty1` (path 2), **(B)** for `/dev/console` (non-blocking by construction, and no
longer a gadget). Called only on the exec-failure path: line 388 `emit(failure,…)`, line
389 `emit(rescue,…)`. Question 3 covers the timeline.

### A12 — `boot/gts9-minimal-pid1.c:226-234` — rescue shell on `/dev/console`

```c
226: 			console = sys_call6(SYS_openat, AT_FDCWD,
227: 					    (long)"/dev/console", O_RDWR, 0, 0, 0);
228: 			if (console >= 0) {
229: 				sys_call6(SYS_ioctl, console, TIOCSCTTY, 0, 0, 0, 0);
230: 				sys_call6(SYS_dup3, console, 0, 0, 0, 0, 0);
231: 				sys_call6(SYS_dup3, console, 1, 0, 0, 0, 0);
232: 				sys_call6(SYS_dup3, console, 2, 0, 0, 0, 0);
```

Class **(A)** as written — **no `O_NONBLOCK` here**, and the three `dup3()` calls give the
BusyBox shell's stdout/stderr blocking semantics. **Not changed** by the 2026-09-26
change: this file was not in the change set. It is now **(B)** in practice, because with
no ttyGS console registered `/dev/console` can only be `tty0` or `ttynull`. Reached only
from `rescue_loop()` (lines 201-253), entered only after `execve("/sbin/init")` at line
376 returns (line 390). Unlike A7/A9 this path was **not** switched to prefer `tty1`, so
it is inconsistent with the two shell fallbacks the change did update.

### A13 — `rootfs-overlay/usr/libexec/gts9-kmsg-console:86-97` — mirror to a gadget tty

```sh
86: while :; do
87: 	if [ ! -w "$DEV" ]; then
88: 		sleep 2
89: 		continue
90: 	fi
93: 	dmesg --follow --time-format reltime -x 2>/dev/null |
94: 		while IFS= read -r line; do
95: 			printf 'K %s\n' "$line" >"$DEV" 2>/dev/null || break
96: 		done
97: 	sleep 1
98: done
```

`DEV=${1:-/dev/ttyGS0}` (line 48); the unit now passes `/dev/ttyGS0`
(`gts9-kmsg-console.service:36`, **changed** from `/dev/ttyGS1`). Class **(A)**: a
userspace writer streaming an unbounded log into a gadget tty. The `|| break` on line 95
is the repository's only mitigation attempt for this failure mode — but `n_tty_write()`
**blocks**, it does not return an error, so `break` cannot fire while the port is unread
and nothing is draining it.

**What the change did here, and what it did not.** The old guard at the top of the
function remains, now at lines 65-72:

```sh
65: # If the kernel already has a console on the USB link (console=ttyGS1 in the
66: # command line with CONFIG_U_SERIAL_CONSOLE), this mirror is redundant: printk
69: if grep -qa 'ttyGS' /sys/class/tty/console/active 2>/dev/null; then
70: 	echo "gts9-kmsg-console: ttyGS is already a kernel console; not mirroring"
71: 	exit 0
72: fi
```

Before the change this guard matched (because `console=ttyGS1` put `ttyGS` in
`/sys/class/tty/console/active`) and the mirror stepped aside. **After the change the
guard can no longer match**, so with `gts9_kmsg_mirror=1` the mirror becomes an *active*
writer into `ttyGS0`. The accompanying comment changes
(`gts9-kmsg-console.service:9-14, 25-35` and `gts9-kmsg-console:22-27`) argue this is
acceptable because "it writes to an opened tty from an ordinary userspace process, which
is bounded and reopenable, rather than being wired into printk and /dev/console" and
because it is off by default behind `ConditionKernelCommandLine=gts9_kmsg_mirror=1`
(line 15) and `Restart=on-failure` (line 23) keeps it off the boot's critical path.

That reasoning is **sound about the boot** (a `Type=simple` unit after `local-fs.target`
cannot hold up `multi-user.target`, unlike the `journal+console` case at
`gts9-prev-boot-evidence.service:12-15`) but it is **not sound about the port**: the
helper's own write loop blocks in `n_tty_write()` when COM19 is unread, and `|| break`
cannot rescue it. The unit's own comment concedes the port choice is now arbitrary
("the port choice is no longer about protecting a shell from printk",
`gts9-kmsg-console.service:25-30`). Recorded as an accepted, flagged **opt-in (A)**.

---

## (B) Safe console/log writers

| # | Location | What it writes | Why it is safe |
|---|---|---|---|
| B1 | `boot/bringup-init.sh:26-28` | `echo "gts9-init: $*" > /dev/kmsg` | `/dev/kmsg`; 2000 lines took 46 ms with COM19 closed (`docs/BOOT_CONSOLE_BLOCK.md:78`). `log()` also `echo`es to stdout (line 24); in the initramfs PID 1's stdout **is** the console (now `tty0`), so line 24 is the same display path as A4/A5 — noted, not double-counted. |
| B2 | `boot/minimal-rootfs-init.sh:28-30` | `> /dev/kmsg` | safe |
| B3 | `boot/minimal-rootfs-state.sh:46-48` | `> /dev/kmsg` | safe |
| B4 | `boot/gts9-minimal-pid1.c:143` | `write_path("/dev/kmsg", …)`, `O_WRONLY\|O_NONBLOCK` | safe; the file's own comment at lines 138-142 states the reasoning ("PID 1 must never be stuck behind a log write") |
| B5 | `boot/gts9-minimal-pid1.c:387` | `write_path("/dev/kmsg", kmsg_failure, …)` | safe |
| B6 | `rootfs-overlay/usr/libexec/gts9-record-debian-stage:137` | `printf 'GTS9_DEBIAN_STAGE=%s\n' "$stage"` (stdout → journal) | journal only; no `StandardOutput=` override, so systemd's `DefaultStandardOutput=journal` applies |
| B7 | `rootfs-overlay/usr/libexec/gts9-record-debian-stage:138-140` | `printf … > /dev/kmsg` | safe |
| B8 | `rootfs-overlay/usr/libexec/gts9-panel-recover:55-58` | `echo` (stdout) + `printf … > "$KMSG"` where `KMSG=/dev/kmsg` (line 25) | safe; guarded by `[ -w "$KMSG" ]` |
| B9 | `rootfs-overlay/usr/libexec/gts9-power-key.c:170-179` | `SYS_openat(…, KMSG_PATH, O_WRONLY\|O_NONBLOCK, …)` then `SYS_write` | `/dev/kmsg`, explicitly non-blocking; `KMSG_PATH "/dev/kmsg"` at line 70 |
| B10 | `rootfs-overlay/usr/libexec/gts9-record-boot-stage:11-20` | block redirected to `"$tmp"` (`/var/log/gts9-last-boot-stage.tmp.$$`) | log file only |
| B11 | `rootfs-overlay/usr/libexec/gts9-record-poweroff-stage:6-11` | `> "$tmp"` (`/var/log/gts9-last-poweroff-stage.tmp.$$`) | log file only |
| B12 | `rootfs-overlay/usr/libexec/gts9-watchdog-debug:183-210` | `{ … } >"$REPORT"` where `REPORT=/var/log/gts9-watchdog-debug.txt` (line 60) | log file; the deliberate fix for the 151 s stall (lines 24-42) |
| B13 | `rootfs-overlay/usr/libexec/gts9-watchdog-debug:83-85` | `printf … >>"$TRACE"` (`/run/gts9-watchdog-debug.trace`) | log file |
| B14 | `rootfs-overlay/usr/libexec/gts9-watchdog-debug:214-222, 256-259` | `summary_line()` echoes one line to stdout → journal | journal only; unit sets `StandardOutput=journal` (line 16) |
| B15 | `rootfs-overlay/usr/libexec/gts9-prev-boot-evidence:56-59, 63, 70, 117, 120, 179-212, 216, 224-231, 234-248, 259` | `> "$dir/…"` files, `journalctl` output, one final `echo` | log files + journal; unit sets `StandardOutput=journal` **and** `StandardError=journal` (lines 26-27) |
| B16 | `rootfs-overlay/usr/libexec/gts9-journal-survey:38-48, 79, 83, 86` | `>"$OUT"`, `>>"$TAIL"`, `>"$TMP"` | log files only; header says "Read-only. Writes only its own report file." (line 31) |
| B17 | `rootfs-overlay/usr/libexec/gts9-usb-acm:53, 60-62, 92-93, 97-98, 153, 164, 172, 183, 194, 200, 202, 212, 281, 283` | `echo` to stdout/stderr | systemd default `journal`; the unit sets no `StandardOutput=` (question 5) |
| B18 | `rootfs-overlay/usr/libexec/gts9-enable-units:29, 112` | `echo` to stdout/stderr | runs on the **host** or in TWRP against a mountpoint, not on the running tablet |
| B19 | `boot/gts9-minimal-pid1.c:279-287` | `dump_diagnostics()`: `exec >/var/log/gts9-minimal-dmesg.txt 2>&1` | log file; runs from the `/run` BusyBox after switch_root |
| B20 | `boot/minimal-rootfs-state.sh:164-205` | `{ … } > "$minimal_state_tmp"` then `mv` | log file (atomic replace) |
| B21 | `rootfs-overlay/usr/libexec/gts9-record-debian-stage:157-207` | `{ … } > "$tmp"` then `mv -f` | log file (atomic replace) |
| B22 | `rootfs-overlay/usr/libexec/gts9-panel-recover:134, 137` | `echo 1 > '$FB_BLANK'` / `echo 0 >` (`fb0/blank`) | **not a console write** — a DRM blank/unblank, deliberately distinguished in `60-gts9-power-key.conf:12`. Listed so a later reader does not mistake it for one. |
| B23 | `rootfs-overlay/etc/gts9-usb-net:1-23` | a static configuration file, `ncm 169.254.42.1/16` (line 23) | read-only data; **new in the change set** (see question 6) |

No use of `mesg`, `wall`, `logger` or `systemd-cat` exists anywhere in `boot/`,
`rootfs-overlay/` or `scripts/`. The only textual hit for `write` as a command is a
comment at `boot/gts9-minimal-pid1.c:24`. There is **no** `TTYPath=` anywhere, and
**no** `rootfs-overlay/etc/systemd/system.conf.d/` directory (only
`etc/systemd/logind.conf.d/` exists), so every unit without an explicit directive gets
systemd's built-in `DefaultStandardOutput=journal` / `DefaultStandardError=inherit`.
`tests/test_watchdog_debug_profile.py:163` asserts that absence.

---

## (C) Conditional

| # | Location | Construct | The condition the reader must judge |
|---|---|---|---|
| C1 | `rootfs-overlay/usr/libexec/gts9-kmsg-console:48` | `DEV=${1:-/dev/ttyGS0}` | Safe only if never invoked with no argument. Combined with `gts9-kmsg-console.service:36` it is class (A) (A13). |
| C2 | `rootfs-overlay/usr/libexec/gts9-kmsg-console:69-72` | `grep -qa 'ttyGS' /sys/class/tty/console/active` → `exit 0` | The guard that used to neutralise A13. It **can no longer match** after the console removal, so the mirror has become an active writer. |
| C3 | `rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service:15` | `ConditionKernelCommandLine=gts9_kmsg_mirror=1` | Whether the mirror runs at all; off by default. |
| C4 | `rootfs-overlay/usr/lib/systemd/system/gts9-dpu-flight.service:17` | `ExecStart=/usr/local/sbin/gts9-dpu-stream /var/log/gts9-dpu-stream.txt 2` | The binary is **not in this repository** — no script installs it and `rootfs-overlay` does not contain it. Its fd 2 is the journal by default, so it is not a console writer *as configured here*, but the file is unavailable for inspection and that is stated rather than assumed. Gated by `ConditionKernelCommandLine=gts9_dpu_flight=1` (line 12). |
| C5 | `boot/bringup-init.sh:150-153` | `while :; do /bin/sh -i; sleep 1; done` — no redirection | PID 1's own stdio; reached only when `gts9_minimal_rootfs=1` and `/minimal-rootfs-init` is missing. Whether it blocks depends on PID 1's inherited fds. The only interactive shell in the file with no explicit device. |
| C6 | `rootfs-overlay/etc/systemd/logind.conf.d/60-gts9-power-key.conf:15-16` | `HandlePowerKey=ignore`, `HandlePowerKeyLongPress=ignore` | Not a writer, but it is *why* `gts9-power-key` exists instead of logind's own action; logind's poweroff path would print to the console. Recorded so the suppression is not read as unrelated. |
| C7 | `scripts/stall-ab.sh:179` (remote `-Commands`) | `echo "$MSG" > /dev/kmsg; printf '%s\n' "$MSG" > /dev/pmsg0` | Both targets are **kernel** sinks, not console devices — class (B) for blocking. Listed because it is a tablet-side write issued from a host script. |
| C8 | `scripts/gts9-debug-channel.sh:37-39` | `console-run.sh -Port COM17 -Commands "… >> /root/.ssh/authorized_keys; …"` | The tablet-side write goes to a file, not a console — but the command text is delivered **over a COM port**, and the header (lines 7-8) says the key is installed "over the serial console". The transport is the thing at risk, not the target. |
| C9 | `scripts/gts9-kernel-alive.sh:86-107, 133-141` | `console=blocked`/`console=live`/`console_shell` verdicts from `console-run.sh -Port COM17` | The script's whole purpose (separating "kernel dead" from "console blocked") presupposes a console. A silent console now has a third cause. |
| C10 | `scripts/flash-boot.sh:46-47, 79-81` | `console-run.sh … -Commands 'gts9-to-recovery'` / `'uname -a'`, then a "console heartbeat" wait | Same transport dependency as C9. |
| C11 | `scripts/gts9-kernel-alive.sh:76-78` | `ssh … 'ps -t ttyGS0 -o args= …'` | Reads ttyGS0 process state over SSH. With `gts9-acm-getty` deleted, no shell will exist on `ttyGS0`, so `console_shell` will read `absent` and line 133-141's verdict logic will misreport. |
| C12 | `scripts/wifi-preflight.sh:40` | comment: "open several console sessions: the ttyGS0 getty defect drops commands" | The script is already SSH-based (line 29), but this comment and its rationale are now stale. |

---

## Answers to the specific questions

### 1. `boot/minimal-rootfs-init.sh` — every console write, before or after `switch_root`, failure-only or every boot

The only console writes defined in this file are the two in the **fallback**
`minimal_emit()`:

| Line | Construct | Phase | Path |
|---|---|---|---|
| 32 | `printf '%s\n' "$*" > /dev/console 2>/dev/null \|\| true` | **before** switch_root | fallback only (only if `/minimal-rootfs-state.sh` is missing, lines 50-54) |
| 35 | `printf '%s\n' "$*" > /dev/tty1 2>/dev/null \|\| true` | **before** switch_root | fallback only |

Everything else is a *call* into the sourced library. Call sites and reachability:

| Lines | Calls | Phase | Reachability |
|---|---|---|---|
| 41-48 | `minimal_state_stage()` / `minimal_state_fail()` fallback definitions | before | only used if the library is missing |
| 53 | `minimal_emit "GTS9_MINIMAL_WARN=state-library-missing:…"` | before | **failure only** |
| 68-80 | `minimal_emit …` × 8 inside `minimal_rescue_shell()` | before | **failure only** |
| 91 | `/bin/sh -i </dev/tty1 >/dev/tty1 2>&1` | before | **failure only**, inside the `while :` at 89 |
| 93 | `/bin/sh -i </dev/console >/dev/console 2>&1` | before | **failure only**, the `elif` fallback |
| 95 | `minimal_emit 'no usable console for the rescue shell; waiting'` | before | **failure only** |
| 124-125, 129-130, 134-135, 139-140 | `minimal_emit 'GTS9_MINIMAL_FAIL=pseudo-mount'` + `ERROR: could not mount …` then `minimal_rescue_shell` | before | **failure only** (proc/sysfs/devtmpfs/run mount failure) |
| 145-146 | `minimal_state_stage kernel-userspace` / `waiting-root` → emits | before | **every** minimal boot |
| 154 | `minimal_emit "root device missing: …"` → `minimal_fail root-timeout` | before | failure only |
| 158, 160, 165 | `minimal_state_stage root-found` / `mounting-root` / `root-mounted` | before | every minimal boot |
| 162 | `minimal_emit "could not mount … as ext4"` | before | failure only |
| 172 | `minimal_emit 'missing or non-executable init: …'` | before | failure only |
| 177 | `minimal_emit 'BusyBox switch_root applet is unavailable'` | before | failure only |
| 188 | `minimal_emit 'could not stage the minimal PID 1 rescue helper'` | before | failure only |
| 205, 208 | `minimal_emit 'GTS9_MINIMAL_TRAMPOLINE=selftest-ok'/'-failed'` | before | only when `gts9_minimal_init=/run/gts9-minimal-pid1` |
| 210 | `minimal_emit 'falling back to /sbin/init for the handoff'` | before | failure only |
| 218 | `minimal_emit "could not move /$vfs into the Debian root"` | before | failure only |
| 233 | `minimal_emit 'the staged PID 1 helper is not executable in the new root'` | before | failure only |
| 240, 245 | `minimal_state_stage switch-root` / `switch-root-synced` | before | **every** minimal boot |
| 246 | `exec switch_root /newroot "$MINIMAL_INIT"` | the boundary | every minimal boot |
| 250 | `minimal_fail switch-root-returned` | **after** (reachable only if `exec` returns) | failure only |

**Answer: every console write in `minimal-rootfs-init.sh` happens before `switch_root`.**
After line 246 nothing can run except the line-250 failure fallback, which is itself still
pre-new-root. The per-boot (non-failure) emissions are the stage markers at lines 145,
146, 158, 160, 165, 240, 245 — six to eight short lines per boot — routed through
`minimal-rootfs-state.sh`'s `minimal_emit()` (question 2), which writes `/dev/console`
and `/dev/tty1`. The interactive shell at line 91 is strictly a failure path, and as of
the change it prefers `tty1` over `/dev/console` (A9).

### 2. `boot/minimal-rootfs-state.sh` — same question

| Line | Construct | Phase | Path |
|---|---|---|---|
| 45 | `printf '%s\n' "$minimal_message"` (stdout) | both | every emit |
| 47 | `printf 'gts9-minimal: %s\n' "$minimal_message" > /dev/kmsg` | both | every emit — **safe** |
| 50 | `printf '%s\n' "$minimal_message" > /dev/console 2>/dev/null \|\| true` | both | every emit |
| 53 | `printf '%s\n' "$minimal_message" > /dev/tty1 2>/dev/null \|\| true` | both | every emit |

Call sites: `minimal_state_stage()` line 131, `minimal_state_fail()` lines 137-138,
`minimal_state_persist_enable()` line 149, `minimal_state_write()` lines 159, 191, 201.

**Before or after `switch_root`:** this file is sourced *by* `minimal-rootfs-init.sh`
(its lines 50-51), so it is in force for that entire lifetime. **All** of its executions
therefore happen before `switch_root` — including the writes triggered by
`minimal_state_stage switch-root` (init line 240) and `switch-root-synced` (init line
245), the last ones to run. `exec switch_root` at init line 246 replaces the process
image; nothing from this file can run after it.

**Failure-only or every boot:** the stage markers are on **every** minimal boot. The
failure-only ones are `minimal_state_fail()` (lines 135-140) and the three warning emits
inside `minimal_state_write()` (lines 159, 191, 201 — state-directory-unavailable,
state-write-failed, state-rename-failed). The whole `> "$minimal_state_tmp"` block (lines
164-205) is a **file** write and is safe; it is only enabled once
`minimal_state_persist_enable` sets `GTS9_MINIMAL_PERSIST=1` (line 147), which the init
calls at its line 169, after the root mount.

The header comment (lines 35-42) was **rewritten by the change** and is now accurate for
the new command line: *"stdout is the panel VT now, not a serial console: the command line
has carried nothing but `console=tty0` since 2026-09-26. /dev/console is kept because this
runs in the initramfs on failure paths where it is the most likely endpoint to exist at
all, and it can no longer be a port that blocks."*

### 3. `boot/gts9-minimal-pid1.c` — what it writes to, and when

| Line | Target | When |
|---|---|---|
| 107 | fd 2 (inherited) | `emit()` — exec-failure path only |
| 108 | `/dev/console`, `O_WRONLY\|O_NONBLOCK` via `write_path()` (94-103) | `emit()` — exec-failure path only |
| 109 | `/dev/tty1`, same flags | `emit()` — exec-failure path only |
| 128 | `record_fd` = `/var/log/gts9-minimal-last-boot` (`O_WRONLY\|O_APPEND\|O_CREAT`, opened 121-122) | `record_write()`, any marker, plus `sync` (136) |
| 143 | `/dev/kmsg`, `O_WRONLY\|O_NONBLOCK` | `record_write()`, best-effort second copy |
| 227-232 | `/dev/console` opened `O_RDWR` **without** `O_NONBLOCK`, then `TIOCSCTTY` + `dup3` to 0/1/2 | `rescue_loop()`, exec-failure path |
| 387 | `/dev/kmsg` | exec returned — `GTS9_MINIMAL_FAIL=switch-root-returned` |
| 388-389 | `emit(failure)` then `emit(rescue)` → fd 2, `/dev/console`, `/dev/tty1` | immediately after the failed `execve` at 376 |

**When, in lifecycle terms.** Three modes, all selected inside `gts9_start()` (line 338):

* **`selftest`** (argv[1] == "selftest", lines 358-362): `record_open_at(argv[2])`,
  `record_write("trampoline=selftest-ok\n")`, `exit_now(0)`. Run by
  `minimal-rootfs-init.sh:195` under `timeout 5`, **before** `switch_root`. Writes the
  record file and `/dev/kmsg` only — **no console write**.
* **Normal PID 1** (line 364 onward): opens the record, writes `trampoline=entered` (365),
  forks the watchdog (368-372), writes `trampoline=exec-init /sbin/init` (374), then
  `execve("/sbin/init")` (376-381). **No console write on this path.** The watchdog child
  runs `watchdog_loop()` (307-329): `trampoline=watchdog-started` (311), then at 30 s
  `record_alive(30)`, at 45 s `dump_diagnostics()` (redirected to
  `/var/log/gts9-minimal-dmesg.txt`, line 280), at 90 s `record_alive(90)`. All record
  file + `/dev/kmsg`.
* **exec failed** (376 returns): `trampoline=exec-failed errno=` (383-386), `/dev/kmsg`
  (387), then the two console writes via `emit()` (388-389), then `rescue_loop()` (390),
  which opens `/dev/console` blocking and runs `/run/busybox sh -i` on it forever.

**Summary: the only console writes in this file are on the failed-handoff path.** `emit()`
writes two lines once and cannot sleep (but silently discards on `-EAGAIN`);
`rescue_loop()` then hands the console to an interactive shell with **fully blocking**
semantics at line 227. This file was **not** part of the 2026-09-26 change, so unlike
`bringup-init.sh:1458-1470` and `minimal-rootfs-init.sh:89-100` its rescue shell was *not*
switched to prefer `tty1` — the one remaining inconsistency among the three shell
fallbacks.

### 4. `boot/bringup-init.sh` — the fallback shell, its reachability, and `start_panel_shell`

The PID 1 fallback loop at the end of the file:

```sh
1438: # PID 1 must survive EOF, an unavailable UART and a user's "exit". Replacing
1439: # init with a shell makes all of those cases panic (Attempted to kill init!).
1440: #
1441: # This used to reopen /dev/console, which is the writer docs/BOOT_CONSOLE_BLOCK.md
1442: # describes: with console=ttyGS1 on the command line /dev/console was the USB ACM
1443: # port, and n_tty_write() to a gadget serial port blocks in wait_woken() until
1444: # that port has room - so a PID 1 shell whose output nobody drained stopped the
1445: # whole boot.  Since 2026-09-26 there is no ttyGS console at all
1446: # (CONFIG_U_SERIAL_CONSOLE is unset) and the remaining console is the panel VT, so
1447: # /dev/console can only resolve to tty0 or to ttynull, and ttynull_write() returns
1448: # without waiting.
1449: #
1450: # It is pinned to /dev/tty1 anyway rather than left on /dev/console, because the
1451: # shell must never depend on which console the kernel happened to prefer - that
1452: # preference is exactly what the removed `console=` arguments used to change
1453: # underneath it.
1454: #
1455: # /dev/tty1 may legitimately be absent (no DRM, no fbcon), and a rescue path that
1456: # blocks on a missing device is the same failure in a new place, so the shell
1457: # falls back to /dev/console and finally to a bounded sleep if nothing is usable.
1458: while :; do
1459:     if [ -c /dev/tty1 ]; then
1460:         /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
1461:     elif [ -c /dev/console ]; then
1462:         /bin/sh -i </dev/console >/dev/console 2>&1
1463:     else
1464:         log 'no usable console for the PID 1 shell; waiting'
1465:         sleep 5
1466:         continue
1467:     fi
1468:     log 'console shell ended or unavailable; PID 1 remains alive, retrying in 5s'
1469:     sleep 5
1470: done
```

**Which boot paths reach it.** There is no `exit` and no `exec` between line 1458 and the
top of the script other than those below, so line 1458 is reached by **every** boot of
this `/init` that does not terminate earlier:

| Line | Termination | Reaches 1458? |
|---|---|---|
| 146 | `exec /minimal-rootfs-init` (when `gts9_minimal_rootfs=1` and the helper exists) | **no** — image replaced |
| 150-153 | `while :; do /bin/sh -i; sleep 1; done` when `gts9_minimal_rootfs=1` but `/minimal-rootfs-init` is missing | **no** — that loop never exits |
| 861, 867 | `exit 0` inside the `userspace proof` background subshell `( … ) &` (856-908) | no — background; PID 1 continues |
| 1362 | `exec switch_root /newroot /sbin/init 3>&-` (successful handoff) | **no** |
| 1273-1277 | early `reboot_to_recovery` when `gts9_reboot_after=1` and proof action is `recovery-bcb` | **no** — reboots first |

Reached on: (a) any boot with **no** `gts9_rootfs=` token — the classic bring-up boot
(`boot/cmdline.example.txt`, `boot/cmdline.boot-trace.example.txt`); (b) any boot with
`gts9_rootfs=` where `boot_rootfs()` **returned 1** — `mmc-timeout` (1303-1308),
`root-mount` (1315-1320), `missing-init` (1327-1333), `missing-switch-root` (1340-1346)
or `switch-root-returned` (1363-1366); (c) a `gts9_minimal_rootfs=1` boot where
`/minimal-rootfs-init` exists but `exec` fails (not reachable in practice — an `exec`
failure on a present executable would fall through to line 148 instead).

Note `3>&-` on line 1362 deliberately closes the boot-trace fd 3 (A4) across the handoff —
the one place the file anticipates that descriptor.

**`start_panel_shell` (lines 1199-1270).** Defined at 1199, called unconditionally at line
**1375**, i.e. after the rootfs handoff block (1369-1373) and **before** the
gadget/`ttyGS0` block (1377-1436). Device and writes:

| Line | Construct | Device |
|---|---|---|
| 1210-1213 | `while [ "$i" -lt 10 ] && [ ! -c /dev/tty1 ]; do sleep 1; …` | waits for `/dev/tty1` |
| 1214-1217 | `if [ ! -c /dev/tty1 ]; then log 'WARN: /dev/tty1 unavailable after 10 s; panel shell not started'; return 0; fi` | bail-out |
| 1221-1223 | `echo 0 > /sys/class/graphics/fb0/blank` | fb0, not a console |
| 1224-1226 | `chvt 1 >/dev/null 2>&1` | switches the active VT to 1 |
| 1227 | `log "panel shell: foreground VT is $(cat /sys/class/tty/tty0/active …)"` | reads tty0 state |
| 1238 | `printf '\033c' > /dev/tty1 2>/dev/null` | **`/dev/tty1`** — clears the screen |
| 1239-1252 | `{ … } > /dev/tty1 2>/dev/null`, incl. `printf 'USB shell: /dev/ttyGS0\r\n\r\n'` at 1251 | **`/dev/tty1`** |
| 1260 | `setsid /bin/sh -c 'PS1="gts9# " exec /bin/sh -i </dev/tty1 >/dev/tty1 2>&1'` | **`/dev/tty1`** |
| 1262 | `PS1='gts9# ' /bin/sh -i </dev/tty1 >/dev/tty1 2>&1` (fallback if no `setsid`) | **`/dev/tty1`** |

**Answer: `start_panel_shell` uses `/dev/tty1`** — the panel VT, i.e. blocking path 2
(`tty1` → `tty0` → fbcon → DRM), not the gadget. The body runs in a background subshell
(`( … ) &` at 1236/1266) inside `while :` (1237-1265), so PID 1 is never held, but ~150 s
of output backlog is the measured behaviour of this path. The header comment (1190-1198)
explains the design (tty1 is the local rescue shell; `ttyGS0` is "untouched"). Line 1251
now advertises a `/dev/ttyGS0` shell that no longer exists.

### 5. Which `rootfs-overlay/usr/lib/systemd/system/` units set `StandardOutput=`/`StandardError=`, and to what

Exactly **three directives in two units**. Nothing else in the directory sets either key:

| Unit | Line | Directive | Value |
|---|---|---|---|
| `gts9-prev-boot-evidence.service` | 26 | `StandardOutput=` | **`journal`** |
| `gts9-prev-boot-evidence.service` | 27 | `StandardError=` | **`journal`** |
| `gts9-watchdog-debug.service` | 16 | `StandardOutput=` | **`journal`** |

`gts9-watchdog-debug.service` sets **no** `StandardError=`, so stderr keeps
`DefaultStandardError=inherit`, which with `StandardOutput=journal` also lands in the
journal. Neither unit uses `journal+console`; both carry a comment explaining why
(`gts9-prev-boot-evidence.service:10-25`, `gts9-watchdog-debug.service:10-15`).

The other **13** units set neither key and inherit `DefaultStandardOutput=journal`:

`gts9-adbd.service`, `gts9-boot-stage.service`, `gts9-debian-basic-stage.service`,
`gts9-debian-entered.service`, `gts9-debian-getty-stage.service`,
`gts9-debian-multi-user-stage.service`, `gts9-dpu-flight.service`,
`gts9-getty-stage.service`, `gts9-kmsg-console.service`, `gts9-panel-recover.service`,
`gts9-power-key.service`, `gts9-poweroff-stage.service`, `gts9-usb-acm.service`.

(The count is 13 now, not 14: **`gts9-acm-getty.service` was deleted by the change set.**
`git status` shows `D  rootfs-overlay/usr/lib/systemd/system/gts9-acm-getty.service`.)

No `StandardInput=`, no `TTYPath=`, and no `rootfs-overlay/etc/systemd/system.conf.d/`
exists, so no unit redirects its own stdout to a tty. The bare-`console` forms
(`StandardOutput=console`, `StandardError=console`) do **not** occur; the only `console`
strings in a `Standard*=` context are the `journal+console` mentions inside comments
(`gts9-prev-boot-evidence.service:12`, `gts9-watchdog-debug.service:10`,
`gts9-watchdog-debug:26`).

### 6. Where is `/etc/gts9-usb-net` created?

**It is now created — as a file shipped in the overlay. This answers the question
differently than it would have before the mid-task change, and the change is the point.**

* **`rootfs-overlay/etc/gts9-usb-net`** (new, untracked, 23 lines) — the canonical
  location. Line 23 is the payload:
  ```
  ncm 169.254.42.1/16
  ```
  Lines 1-22 are a header comment explaining the format, the APIPA address choice and
  *why the file ships rather than being created by hand*: *"This file ships in the overlay
  rather than being created by hand, because it is what makes a freshly installed rootfs
  reachable at all. Without it the gadget comes up with no network function and the tablet
  has no way in - it used to be acceptable to rely on the serial console as the fallback,
  and that fallback is gone."*
* **How it reaches a rootfs:** `scripts/install-debian-rootfs.sh:78-85` (`copy_overlay`)
  does `cp -a "$overlay"/. "$dest"/`, and `install_tree()` calls it at line **235**. So
  the file is installed as a side effect of the overlay copy — there is **no dedicated
  step** and **no reference to `gts9-usb-net` anywhere in `install-debian-rootfs.sh`**
  (verified by grep; the only lines matching `etc/` in that file are unrelated). The same
  is true of `scripts/install-rootfs-diagnostics.sh` (28 lines, installs only the logind
  drop-in, the `gts9-*.service` units and the `gts9-*` libexec helpers).
* **The consumer** parses it correctly, including the header comment. `gts9-usb-acm:133-158`
  was extended by the change to skip blank and `#` lines before reading the first
  significant line — the comment at lines 135-138 states exactly why: *"The file ships in
  the overlay, so it carries a header explaining the format and the address choice; a
  plain `read < file` would take the first comment line as the function name and fail the
  whole file as unknown."* The parser accepts only `ncm` or `ecm` (line 151) and rejects
  anything else (lines 152-156). `NET_CONF=${GTS9_USB_NET_CONF:-/etc/gts9-usb-net}` at
  line 128.
* **Failure is contained:** `net_drop()` (160-166) and the retry at lines 264-273 mean a
  bad line costs the network function but not the USB link — the gadget still binds with
  its ACM ports.

**Residual risk worth flagging (not a blocking-console issue).** Because the file is
installed only via `cp -a` of the overlay, an **upgrade** of an existing rootfs does get
it (the copy is unconditional), but any deployment path that installs *individual* files
rather than the whole overlay — `scripts/install-rootfs-diagnostics.sh` is exactly such a
path — will **not** install it. A rootfs provisioned only by
`install-rootfs-diagnostics.sh` would still have no SSH transport. If that script is meant
to be a complete "make this rootfs debuggable" entry point, it needs a line for this file.

Also stale-by-one-step: `docs/FAST_DEBUG_CHANNEL.md:159` still documents the old manual
recipe (`printf 'ncm 169.254.42.1/16\n' > /etc/gts9-usb-net`), and
`scripts/gts9-debug-channel.sh:50` still tells the operator *"the gadget needs
/etc/gts9-usb-net and a re-run of gts9-usb-acm"*.

### 7. `rootfs-overlay/usr/libexec/gts9-enable-units` — exactly what it masks or removes links for

The script first creates enablement links from each unit's own `WantedBy=` (lines 55-61),
then performs **three** cleanups (the section added by the change, lines 63-110). Each
cleanup does the same pair of things: **remove the enable link**, then **mask the unit
name** with `ln -sfn /dev/null`.

```sh
76: rm -f "$etc_dir/getty.target.wants/serial-getty@ttyGS0.service" 2>/dev/null || true
77: if [ -d "$etc_dir" ]; then
78: 	ln -sfn /dev/null "$etc_dir/serial-getty@ttyGS0.service" 2>/dev/null || true
79: fi
```

```sh
87: rm -f "$etc_dir/multi-user.target.wants/gts9-acm-getty.service" 2>/dev/null || true
...
95: if [ -d "$etc_dir" ]; then
96: 	ln -sfn /dev/null "$etc_dir/gts9-acm-getty.service" 2>/dev/null || true
97: fi
```

```sh
104: rm -f "$etc_dir/getty.target.wants/serial-getty@ttyMSM0.service" 2>/dev/null || true
105: if [ -d "$etc_dir" ]; then
106: 	ln -sfn /dev/null "$etc_dir/serial-getty@ttyMSM0.service" 2>/dev/null || true
107: fi
```

| # | Lines | Enable link removed | Unit name masked |
|---|---|---|---|
| 1 | 76, 78 | `getty.target.wants/serial-getty@ttyGS0.service` | `serial-getty@ttyGS0.service` |
| 2 | 87, 96 | `multi-user.target.wants/gts9-acm-getty.service` | `gts9-acm-getty.service` |
| 3 | 104, 106 | `getty.target.wants/serial-getty@ttyMSM0.service` | `serial-getty@ttyMSM0.service` |

**So exactly three systemd instances are masked** —
`serial-getty@ttyGS0.service`, `gts9-acm-getty.service` and
`serial-getty@ttyMSM0.service` — and three enable links are removed, one per instance.

Note the deliberate change of masking idiom: the masks use **`ln -sfn` with no
`[ ! -e … ]` guard** (lines 78, 96, 106). The file's own comment at lines 88-94 explains
why, and it is the more correct choice: *"Mask the name outright with `ln -sfn`: it
replaces whatever is there (including a regular file) with /dev/null, which is what
`systemctl mask` does and is the only thing that reliably stops the unit starting. A
guard like `[ ! -e ... ]` would leave the stale copy in charge."* An earlier revision of
this file used the guarded form; the unguarded `-sfn` form supersedes it, so
`serial-getty@ttyMSM0.service` is now masked unconditionally rather than only when absent.
This makes the helper **not strictly idempotent in the overwrite sense** — a deliberate
operator override of one of these three names in `/etc` is destroyed on every run — but it
is idempotent in the sense that matters (running it twice leaves the same state), and the
header's idempotence claim (lines 17-20) still holds.

Line 109-110 records the deliberate exclusion: *"tty1 is deliberately untouched: it is the
panel VT, the only console left, and the local getty on it is how the tablet is used
without a cable."* `gts9-acm-getty.service` is no longer picked up by the generic
`WantedBy=` loop at 55-61 because the unit file was deleted.

Every `rm`, `ln` and `ln -sfn` is `|| true`-guarded, so a failure here cannot fail the
install.

### 8. What else in the repository references `ttyGS1`, `ttyGS0`, `ttyMSM0` or `earlycon`?

Excluding the cmdline files themselves and `docs/`, `reference/boot-tests/`, `out/`,
`.work/`:

**`ttyGS1`** — after the change this survives in **comments and tests only**; the one
functional reference (`ExecStart=… /dev/ttyGS1`) is gone.

| file:line | Context |
|---|---|
| `rootfs-overlay/usr/libexec/gts9-kmsg-console:65` | comment: *"console=ttyGS1 in the command line with CONFIG_U_SERIAL_CONSOLE"* — the guard's rationale, now unreachable |
| `rootfs-overlay/usr/libexec/gts9-usb-acm:79, 83` | comments describing the old handover (`console=ttyGS1`, now removed) |
| `rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service:11, 25` | comments: *"console=ttyGS1 is gone"*, *"This used to be /dev/ttyGS1"* |
| `rootfs-overlay/usr/lib/systemd/system/gts9-prev-boot-evidence.service:13` | comment: *"on this board resolves to ttyGS1 (COM19)"* — **stale**, `/dev/console` no longer resolves there |
| `scripts/screenshot-tablet.sh:17` | comment: *"ttyGS1 is a serial console, not a display"* |
| `scripts/stall-ab.sh:265` | `grep -q 'console=ttyGS1' "$CMDLINE" \|\| die "every profile keeps the ttyGS1 kernel console"` — **a hard gate that now fails every stall A/B run**, because no `boot/cmdline*.example.txt` carries `console=ttyGS1` any more |
| `scripts/sysrq-over-console.sh:7, 11, 47`; `scripts/sysrq-over-console.ps1:27, 50` | comments on why serial SysRq is unsupported |
| `tests/test_watchdog_observer_effect.py:94`; `tests/test_rpmh_debug_patch.py:47`; `tests/test_gpu_gmu_rpmh_stall.py:121-122, 428, 2605-2616` | test assertions that the string is present |

**`ttyGS0`** — still heavily present; the device still exists (the gadget keeps both ACM
ports), but nothing logs in on it any more.

| file:line | Context |
|---|---|
| `boot/bringup-init.sh:508, 1195, 1251, 1382, 1386, 1389, 1392, 1397-1400, 1404, 1410, 1423, 1424, 1427, 1428, 1429, 1431, 1435` | the whole USB-console block — **A1, A2, A3**; unchanged by the change set |
| `rootfs-overlay/usr/libexec/gts9-kmsg-console:19, 35, 48` | comment, usage, `DEV=${1:-/dev/ttyGS0}` |
| `rootfs-overlay/usr/libexec/gts9-usb-acm:41` | `TTY_DEVICE=${GTS9_USB_TTY:-/dev/ttyGS0}` (used at 276-284 to wait for the node) |
| `rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service:36` | `ExecStart=/usr/libexec/gts9-kmsg-console /dev/ttyGS0` — **retargeted from ttyGS1 by the change** |
| `rootfs-overlay/usr/lib/systemd/system/gts9-usb-acm.service:4` | `Before=serial-getty@ttyGS0.service` |
| `rootfs-overlay/usr/libexec/gts9-enable-units:70-79` | comment + `rm -f …/serial-getty@ttyGS0.service` (question 7) |
| `rootfs-overlay/usr/libexec/gts9-power-key.c:7`; `rootfs-overlay/etc/systemd/logind.conf.d/60-gts9-power-key.conf:5` | comments |
| `scripts/gts9-kernel-alive.sh:22, 71, 77, 134, 138, 141` | comments + `ps -t ttyGS0 -o args=` (C11) |
| `scripts/wifi-preflight.sh:40`; `scripts/stall-ab.sh:433`; `scripts/sysrq-over-console.ps1:50` | comments |
| tests: `test_panel_shell.py:32`; `test_debian_usb_acm.py:62, 194`; `test_debian_rootfs_installer.py:54, 86, 92, 100`; `test_debian_ttygs0_console.py:1, 4, 28, 39, 73`; `test_watchdog_observer_effect.py:115-124`; `test_debian_panel_recover.py:179`; `test_gpu_gmu_rpmh_stall.py:1495, 1499, 1571, 1600, 1646, 3205` | assertions |

**`ttyMSM0`** — **no non-test, non-comment code writes to it anywhere.** The only
functional references are the mask/removal in `gts9-enable-units`.

| file:line | Context |
|---|---|
| `rootfs-overlay/usr/libexec/gts9-enable-units:99-107` | comment + link removal + mask (question 7) |
| `tests/test_watchdog_observer_effect.py:109, 119, 129`; `test_debian_rootfs_installer.py:101-103, 140, 169-171`; `test_debian_ttygs0_console.py:81`; `test_debian_panel_recover.py:26, 49, 145`; `test_debian_boot_stages.py:22`; `test_twrp_debian_recovery.py:21`; `test_debian_usb_acm.py:31`; `test_panel_shell.py:72`; `test_rootfs_boot.py:175`; `test_rpmh_debug_patch.py:52`; `test_gpu_gmu_rpmh_stall.py:124` | test assertions and fixture command lines |

`gts9-kmsg-console:9` no longer quotes a `console=ttyMSM0` command line — the change
rewrote it to `console=tty0`.

**`earlycon`** — after the change it survives **only in tests**:

| file:line | Context |
|---|---|
| `tests/test_watchdog_observer_effect.py:131-132`; `test_panel_shell.py:73`; `test_rootfs_boot.py:176`; `test_rpmh_debug_patch.py:53`; `test_gpu_gmu_rpmh_stall.py:125` | assertions that the cmdline files still contain `earlycon` — **all now failing**, since no `boot/cmdline*.example.txt` carries it |

No production file mentions `earlycon` at all any more. The `gts9-enable-units` comment
that asserted "console=ttyMSM0,115200n8 and earlycon stay on the command line" is gone —
the change rewrote it (now lines 99-103) — so the stale-claim finding it represented is
**resolved**.

---

## What must change when the serial consoles are removed

The removal has largely landed. What follows is what is **still outstanding**, ordered by
severity, with the state of each item at the time of writing.

### 1. Blocking writers that the removal did NOT address

These are the findings that survive the change set, and they are the answer to "what is
left".

| Priority | Location | Why it is outstanding |
|---|---|---|
| **P0** | `boot/bringup-init.sh:1410-1434` (A2) — the interactive `/dev/ttyGS0` shell, default `USB_CONSOLE_MODE=shell` | A gadget tty handed to an interactive shell under `while :`. `gts9-usb-acm` still creates `acm.usb0`, so `/dev/ttyGS0` exists; it is no longer a *kernel* console, but `n_tty_write()` blocking does not depend on being a console — it depends on nobody draining the port. This runs in the **initramfs**, where the new NCM/ssh transport does not yet exist, so it cannot simply be deleted without deciding what the initramfs rescue channel is. |
| **P0** | `boot/bringup-init.sh:1424` (A3) — `cat /dev/kmsg > /dev/ttyGS0` | Same mechanism, opt-in via `gts9_usb_console=shell+kmsg`. |
| **P1** | `boot/bringup-init.sh:1397-1400` (A1) — the four `GTS9-SERIAL-MARKER` writes | Same device, opt-in via `gts9_usb_console=marker`. Bounded to four lines. |
| **P1** | `boot/bringup-init.sh:35-39, 228, 967-968` (A4, A5) | Path 2 — `tty0` → fbcon → DRM. **Untouched by the change**, and now on the *only* console. The `gts9_boot_trace_console=1` profile fires on every boot stage; the two marker lines are unconditional. If the goal was "no console can stall a boot", this is the remaining half. |
| **P1** | `boot/bringup-init.sh:1238, 1252, 1260, 1262` (A6, `start_panel_shell`) | Path 2 again, via `tty1`. Backgrounded, so it cannot hold PID 1, but the measured backlog on this path was ~150 s. |
| **P1** | `boot/bringup-init.sh:1458-1470` (A7), `boot/minimal-rootfs-init.sh:89-100` (A9) | The change moved both shell fallbacks from `/dev/console` to `/dev/tty1` — correct for the gadget, but it substitutes path 2 for path 1. This is a genuine trade, not a free win, and should be recorded as such. Both have correct bounded-`else` branches now. |
| **P2** | `boot/gts9-minimal-pid1.c:226-234` (A12) | **Not updated by the change.** Unlike A7/A9 this rescue shell still opens `/dev/console` blocking with no `O_NONBLOCK`, and does not prefer `tty1`. Harmless today (only `tty0`/`ttynull` can be behind `/dev/console`) but inconsistent with the other two fallbacks, and it silently becomes a gadget-risk again if a `console=` argument is ever reintroduced. |
| **P2** | `boot/gts9-minimal-pid1.c:105-110` (A11) | `O_NONBLOCK` makes it non-hanging but **silently discards** on `-EAGAIN`; the call site does not say so. Worth a comment at minimum. |

### 2. The one change that created a new writer

**`rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service:36`** was retargeted
from `/dev/ttyGS1` to `/dev/ttyGS0`, and the guard that used to keep the mirror dormant
(`gts9-kmsg-console:69-72`, matching `ttyGS` in `/sys/class/tty/console/active`) can no
longer match once `console=ttyGS1` is off the command line. Result: with
`gts9_kmsg_mirror=1` on the command line, `gts9-kmsg-console` becomes an **active**
userspace writer streaming kernel messages into a gadget port nobody may be draining.

Mitigations already in place and **effective for the boot, not for the port**: the unit is
`Type=simple` after `local-fs.target` (so it cannot hold `multi-user.target`), off behind
`ConditionKernelCommandLine=gts9_kmsg_mirror=1` (line 15), and `Restart=on-failure`
(line 23).

Mitigations **not** in place: the write at `gts9-kmsg-console:95` can still block in
`n_tty_write()`, and `|| break` cannot fire because a full tty returns no error — it
sleeps. The unit's comment (lines 32-35) claims "the helper reopens the tty on every write
error and never lets a stuck port stall anything else", which is true only for *errors*.

Options: open `$DEV` with `O_NONBLOCK` (in shell, `stty` is not sufficient — this needs
the fd flag, so the loop would have to tolerate short writes and drop lines), or accept it
as a documented opt-in instrumentation hazard, or drop the unit. Whichever is chosen, the
`|| break` comment should stop implying it handles a blocked port.

### 3. Host-side scripts and harnesses that assume a serial console

| Location | Construct | Action needed |
|---|---|---|
| `scripts/stall-ab.sh:265` | `grep -q 'console=ttyGS1' "$CMDLINE" \|\| die "every profile keeps the ttyGS1 kernel console"` | **Hard failure.** No profile file carries `console=ttyGS1` any more, so every stall A/B run dies at this line. Remove the gate or replace it with the new invariant (e.g. assert no `console=` other than `tty0`). |
| `scripts/stall-ab.sh:38-39, 179, 208, 291, 445, 661, 667` | `CR=…/console-run.sh`, `CW=…/console-watch.sh`; all probes and marks go over COM17/COM19 | The harness loses its transport. Line 445's `-Commands 'systemctl restart gts9-acm-getty.service'` now targets a masked, deleted unit. |
| `scripts/gts9-debug-channel.sh:37-39` (header lines 6-8) | installs the SSH key "over the serial console" | Chicken-and-egg: the key install needs the console the key is meant to replace. This should become part of provisioning (a key baked into the rootfs, or an `install-debian-rootfs.sh` step) rather than a console interaction. `docs/FAST_DEBUG_CHANNEL.md:159` documents the same console-based bootstrap. |
| `scripts/gts9-kernel-alive.sh:76-78, 86-107, 133-141` | `console=blocked`/`live` verdicts from `console-run.sh`; `ps -t ttyGS0` via ssh (line 77) | With no getty on `ttyGS0` (C11) the shell count is always 0, so the verdict logic at 133-141 will misclassify. The ICMP/ARP/SSH probes (lines 41-63) are the part that still works and should become the whole verdict. |
| `scripts/flash-boot.sh:46-47, 79-81` | `console-run.sh -Commands 'gts9-to-recovery'`; "waiting for the mainline shell (console heartbeat)" | Runs in the **initramfs**, before `gts9-usb-acm`/NCM exists — SSH cannot replace it. This is the one place with genuinely no alternative channel, and it is why P0 above cannot simply be deleted. |
| `scripts/screenshot-tablet.sh`, `scripts/wifi-preflight.sh`, `scripts/wifi-cold-boot-capture.sh` | already SSH-based (`SSH=$REPO/scripts/gts9-ssh.sh`) | Unaffected. These are the model the others should follow. |
| `scripts/sysrq-over-console.sh:20`, `scripts/sysrq-over-console.ps1` | `-Port COM19` negative test | Still valid as a negative test, but the port no longer carries a console. |

### 4. Provisioning gap remaining

`rootfs-overlay/etc/gts9-usb-net` now exists and is installed by `install-debian-rootfs.sh`
via `copy_overlay()` (`cp -a "$overlay"/. "$dest"/`, line 84, called from line 235) — so
the main gap identified before the change is **closed**.

Two follow-ups:

1. **`scripts/install-rootfs-diagnostics.sh`** installs files *individually* (the logind
   drop-in at lines 13-15, `gts9-*.service` at 17-19, `gts9-*` libexec helpers at 21-23)
   and therefore does **not** install `etc/gts9-usb-net`. A rootfs fixed up with only that
   script has no SSH transport. Add a line for it, or document that this script is not a
   complete debug-channel installer.
2. **`docs/FAST_DEBUG_CHANNEL.md:159`** and **`scripts/gts9-debug-channel.sh:50`** still
   describe `/etc/gts9-usb-net` as something the operator creates by hand. Both should now
   say it ships in the overlay.

### 5. Documentation that the change made stale

| Location | Statement | Status |
|---|---|---|
| `rootfs-overlay/usr/lib/systemd/system/gts9-prev-boot-evidence.service:12-15` | *"`journal+console` means every line is also written to /dev/console, which on this board resolves to ttyGS1 (COM19)"* | The directive is correctly absent, but the rationale is now historically wrong — `/dev/console` resolves to `tty0`/`ttynull`. Keep the fix, correct the explanation. |
| `boot/bringup-init.sh:1251` | panel banner prints `USB shell: /dev/ttyGS0` | **Stale instruction** — the banner advertises a shell that no longer exists. Should point at ssh (`root@169.254.42.1`). |
| `boot/bringup-init.sh:508-513` | *"What /init does with /dev/ttyGS0: shell — stream the kernel log and hand the port to a shell (the console)"* | The `ttyGS0` block (A1-A3) is untouched, so this remains *accurate code* but contradicts the new "no serial console" policy. Decide whether the initramfs shell stays. |
| `rootfs-overlay/usr/libexec/gts9-usb-acm:73-100` (`split_consoles`) | *"This was the console handover … 0 on the shell port, 1 on the port named by console=ttyGS1"* | The change rewrote this to force **`0` on both ports** (lines 91, 96) with the comment explaining it is now a deliberate no-op kept for older kernels. Correct and self-consistent. `tests/test_debian_usb_acm.py`'s split-console test still pins the old `1` and fails (section 6). |
| `boot/minimal-rootfs-state.sh:8`, `boot/minimal-rootfs-init.sh:7` | *"emitted on /dev/kmsg and /dev/console"* | Still true; the surrounding files' newer comments (state lines 35-42, init lines 82-88) are accurate. No action beyond what the change already did. |
| `boot/gts9-minimal-pid1.c:10-13` | *"the panel may be dark and there may be no USB console at all"* | Accurate. |
| `docs/BOOT_CONSOLE_BLOCK.md:97-115` | "The fix" — lists three items, including "keep the PID 1 fallback shell on a local console (`/dev/tty0` or `/dev/ttyMSM0`) rather than `/dev/console`" | Item 1 is now **done** for `bringup-init.sh` and `minimal-rootfs-init.sh` (moved to `tty1`), **not done** for `gts9-minimal-pid1.c:227`. Items 2 and 3 are done. The doc should record the decision as taken and note the `tty1`-instead-of-`tty0`/`ttyMSM0` choice and why (`ttyMSM0` no longer exists as a console). |
| `docs/FAST_DEBUG_CHANNEL.md:41-45` | *"The serial console is still the only channel that exists before `gts9-usb-acm` runs … **Keep it.**"* | Contradicts the new decision and identifies the real remaining gap (the initramfs window). Needs rewriting to name what replaces that window — which is currently **nothing**, and is exactly why P0 in section 1 is unresolved. |
| `docs/USB_SERIAL_CONSOLE.md:11-21`; `docs/NEXT_STALL_DEBUG_PLAN.md:15-16, 157-187`; `docs/GPU_GMU_RPMH_STALL_PLAN.md:21-22, 677-678`; `docs/SLOW_SHUTDOWN_ANALYSIS.md:94-101`; `docs/WIFI_QCA6490_BRINGUP.md:233-239, 298` | tables and plans built on `ttyGS1` = kernel console, `ttyMSM0` = kernel console + `earlycon`, `ttyGS0` = autologin shell | All stale. `docs/WIFI_QCA6490_BRINGUP.md:298` calls `console=ttyGS1` "the one open design decision" — it is now closed. |

### 6. Tests that fail — measured, not predicted

The suite was **run** rather than reasoned about. On the working tree described above:

```
python3 -m unittest tests.test_rootfs_boot tests.test_panel_shell \
    tests.test_watchdog_observer_effect tests.test_rpmh_debug_patch \
    tests.test_poweroff_trace_profile tests.test_debian_ttygs0_console \
    tests.test_debian_rootfs_installer tests.test_debian_usb_acm \
    tests.test_fast_debug_channel tests.test_watchdog_debug_profile \
    tests.test_minimal_rootfs_stages tests.test_debian_boot_stages
Ran 216 tests in 16.937s
FAILED (failures=10, errors=1)
```

The 11 failures, verbatim:

| Test | Assertion that fails |
|---|---|
| `test_rootfs_boot.RootfsBoot.test_cmdline_profile` | `tests/test_rootfs_boot.py:175-176` — `assertIn('console=ttyMSM0,115200n8')`, `assertIn('earlycon')` |
| `test_watchdog_observer_effect…test_ttymsm0_stays_a_kernel_console` | `tests/test_watchdog_observer_effect.py:131-132` — same two assertions on `boot/cmdline.minimal-rootfs.example.txt` |
| `test_watchdog_observer_effect…test_three_instrumentation_switches_are_independent` | reads the same cmdline file |
| `test_watchdog_observer_effect…test_ttygs0_is_handed_to_a_dedicated_unit_not_masked` | **ERROR** — the unit file it reads (`gts9-acm-getty.service`) was deleted |
| `test_rpmh_debug_patch.RpmhDebugPatchTests.test_the_heavy_instrumentation_is_off_in_the_test_186_profile` | `tests/test_rpmh_debug_patch.py:47` — `assertIn("console=ttyGS1", cmdline)` |
| `test_poweroff_trace_profile…test_diagnostic_cmdline_keeps_serial_as_console_device` | `tests/test_poweroff_trace_profile.py:19` — `consoles == ["console=tty0", "console=ttyMSM0,115200n8"]`, got `['console=tty0']` |
| `test_debian_usb_acm.UsbAcmServiceTests.test_console_split_is_requested_for_the_second_port` | the `split_consoles` behaviour it pins changed (both ports now forced to `0`) |
| `test_watchdog_debug_profile…test_known_good_profiles_are_unchanged` | **4 sub-failures**, one per profile file: `boot/cmdline.example.txt`, `cmdline.minimal-rootfs.example.txt`, `cmdline.poweroff-trace.example.txt`, `cmdline.boot-trace.example.txt` |

Two tests that an earlier draft of this report predicted would fail **pass**, and the
difference is worth recording: `tests/test_panel_shell.py:68-94` was **rewritten by the
change** and now asserts the new invariant —

```python
78:        self.assertIn('console=tty0', tokens)
82:        self.assertEqual(consoles, ['console=tty0'])
87:        for gone in ('console=ttyMSM0,115200n8', 'console=ttyGS1', 'earlycon'):
94:            self.assertFalse(token.startswith(('console=ttyGS', 'console=ttyMSM')),
```

— so it is green and is now the best statement of the intended end state. Likewise
`tests/test_panel_shell.py:31-32` (indexing the unchanged `ttyGS0` block) still passes.

The tests for `tests/test_rootfs_boot.py:175-176`, `test_rpmh_debug_patch.py:47`,
`test_poweroff_trace_profile.py:19`, `test_watchdog_observer_effect.py:126-132` and
`test_watchdog_debug_profile` are the mechanical checklist for the change; each pins a
`console=` line that the change removed. `tests/test_panel_shell.py` is the template for
how to rewrite them (assert the new invariant affirmatively, and assert the removal
explicitly). `test_debian_usb_acm`'s split-console test and
`test_watchdog_observer_effect`'s getty test need the deleted unit and the new `0/0`
console policy respectively.

---

*Read-only analysis. No file in the repository was modified except this report. The
working tree was changing during the analysis: findings were re-verified against the
post-change state, and the verification hashes above identify the revision this report
describes. Head commit `7e552a6` plus the uncommitted change set described at the top.*
