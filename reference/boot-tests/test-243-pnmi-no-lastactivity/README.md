# Test 243: remove optional per-IPI/CSD recorder work, retain pseudo-NMI

CPU repair is still open. Test242's 308-second window yielded no natural fault.
Test235 had failures without lastactivity instrumentation. Those uncontrolled
histories do not demonstrate an observer effect, but the source proves the
active recorder adds preemption control, atomic accesses, barriers and clock
reads to six IPI/CSD events. Standard RCU target backtraces can now use the
separately calibrated pseudo-NMI route, so these optional callbacks can be
removed from a capture attempt without losing that route.

Reuse the exact test241/242 kernel/config/DTB/symbols and ECC64. Change only
gts9_lastactivity=1 to 0 in the early command line; calibration stays disabled.
la_init returns before UUID creation and all seven probe registrations when
not requested. Verify the actual kernel notes/six relocation anchors, both
disable flags, empty lastactivity capture ID, helper enable=N/started=0,
runtime pseudo-NMI priority masking, ECC64, watchdog 1/1/1/10 and printk 5/4.
No lastactivity cells or automatic recorder snapshot will be available; do not
interpret their absence as an absence of CPU activity or fault.

After verified identity, write one priority-0 /dev/kmsg attribution marker
GTS9_PNMI_TARGET containing the immutable target boot ID and kernel-notes hash.
This is one userspace log write, not a backtrace/CPU injection or recurring
callback. Preserve its live source record and source timestamp. It replaces
the disabled recorder's UUID for attribution if pstore is later needed.

Budget: one candidate boot up to 300 seconds of its own uptime, no manual
backtrace, artificial stall, hotplug, frequency/power change, workload or
forced panic. Follow the immutable boot's kernel journal as JSON with -n all,
preserving kernel source clocks instead of relying on rendered receipt time.
Use bounded 15-second identity checks and stop on first CPU/RCU/workqueue
failure, suspect timeout, identity/profile loss or stream failure. On a
positive failure allow 20 seconds for the target backtrace to finish, retain
partial output, and review before further action. No additional target under
this plan. A clean window does not prove repair or a changed failure rate.

If failure occurs, prioritize source-clock JSON and actual target PC/stack;
only that target's saved relocation and notes may symbolize it. If automatic
reboot happens, retrieve two raw console copies/device hash and retained
adjacent boot IDs before recovery. Require the unique source marker; retained
data without a live reference still lacks full integrity proof even with no
uncorrectable ECC blocks. A missing pseudo-NMI response cannot distinguish
raw DAIF masking, firmware, GIC state or CPU non-progress.

Package/backup/device/hash checks precede flashing boot/vendor_boot only.
Rootfs, shared USB gadget, recovery, init_boot, dtbo and vbmeta stay unchanged.
At the attempt's end restore original images and verify all five hashes plus
a separate >=150-second production boot and ADB/NCM SSH protocol response.
If software recovery cannot respond, request owner TWRP recovery and continue
offline analysis; never silently extend this attempt or claim a CPU fix.

Outcome: the single 306.92-second window was clean, without a CPU repair
conclusion. A separately registered test244 now tests one direct Debian warm
reboot (historical test234 failure path), using the unchanged installed
profile. Restoration is deferred to that session's end to avoid redundant
partition writes. The original single-boot budget is complete; see RESULTS.md.
