# Test245: natural startup failure before the low-address workload

**CPU repair remains OPEN.** The corrected-BBM candidate failed during startup;
the planned low-address helper was never pushed or executed. Do not retry this
closed one-target budget or count it as low-address coverage. The owner's
observed frozen screen → automatic restart agrees with the retained panic.

## Target and failure evidence

- Target: `9c9d553e-86c9-4b80-b6d7-9c29447f7125`; capture
  `9343ce3b-8159-47ad-a4be-5cb28d453aad`.
- Exact test240 fixed-BBM kernel/bundle rehashed and validated before flashing;
  boot/vendor_boot read back, all five partition hashes checked. Runtime
  ECC64, watchdog/panic 1/1/1/10, READY and erratum2645198 verified.
- First ADB response at6.70 s; full JSON follower then started, target checks
  completed by16.28 s. Six anchors gave **+0x178000**, matching the later panic's
  own Kernel Offset. Notes match exact saved test240 vmlinux.
- An identity read after26.44 s timed out after emitting only the target UUID.
  Live stream and by-ID disk kernel journal stop before the failure. The live
  runner correctly stopped as `inconclusive`; its original verdict is preserved.
- Immediate retained successor: `2545579b-f7a5-4123-9439-5c0218de7cee`.
  Initially fetched live dmesg is this **observer**, not the failed target.
  The subsequent immutable boot list/identity prevents that attribution error.

Retained console and panic records contain the source's exact capture ID:
RCU snapshot at30.655377 s, RCU warning naming CPU2 at30.681332 s, backtrace
request at30.682872 s; CPU1 soft lockup at36.543182 s followed by panic at
36.543400 s. Panic precedes completion of the ordinary backtrace timeout;
there is no CPU2 stack here. This build has no pseudo-NMI capability.
The configured panic=10 accounts for automatic recovery. New classification
is in `analysis/verdict.json`, separate from the initial transport verdict.

## What the saved stack establishes

CPU1's interrupted task is KFENCE `toggle_allocation_gate`, through static-key
patching → `kick_all_cpus_sync()` → `smp_call_function_many_cond()`.
The exact saved binary places PC+0x3ec at `ldar w11,[x10]` in the final CSD wait.
Register x9=2 identifies target CPU2; last-loaded w11=0x11 contains LOCK|SYNC.
This is a **CPU1 waiter for CPU2**, not CPU2's blocked program counter.
The normal IRQ watchdog running on CPU1 also rules out treating CPU1 as a
CPU that stopped taking every interrupt at this instant.

The bounded recorder decodes all48 cells with this target's relocation.
CPU2's last positive IPI exit is an IRQ-work interrupt at9.652418 s; its last
CSD entry/exit is `sched_ttwu_pending` at9.652330/9.652355 s. CPU4's last
recorded function-call exit is9.652041 s. CPU5 has a completed `do_nothing`
callback at9.884214/9.884215 s. These last observations do not timestamp the
failure, prove no later unrecorded work, or establish simultaneous CPU faults.
No causal KFENCE exclusion/inclusion follows solely from its waiter stack.

0026 therefore did **not prevent this natural failure**. The trial does not
show that 0026 caused the failure or measure its effect on frequency. Defer
the unfinished independent low-address branch test; investigating the natural
CPU2 non-response now has priority over another BBM functional boot.

## Retention integrity and limits

Two raw pulls per console/panic file match their on-device SHA-256 hashes.
Strictly parsed48-cell snapshots/58 marker lines agree across console and panic
storage. ECC reports1004/1814 corrected bytes respectively, zero unrecoverable
blocks. Target IDs, six anchors, panic relocation and retained adjacency agree.
No pre-reboot live snapshot exists, so this is not a known-payload end-to-end
integrity proof; zero bad blocks alone is insufficient. See `analysis/integrity.json`.

The separately copied `.enc.z` file is older (mtime1790452825 versus current
panic text1790535490), has no established target attribution and fails both
wrapper/raw-deflate decoding. Preserve it as stale supplementary evidence;
do not call its decoding error corruption of this target's recovered text.

## Restoration and remaining service issue

Recovery BCB read/write succeeded in the observer. `systemctl reboot` returned
Access denied; the separately logged normal `reboot.target` transaction
succeeded. No forced reboot syscall or `reboot recovery` was used. TWRP restored
original boot/vendor_boot; all five production hashes match. No rootfs, USB
configuration, kernel default or global mmap setting was changed.

Restored production: `bd20438b-cea6-4172-8e5f-de83a6b69a51`. Its planned120.08 s
window has1095 source-timestamped kernel JSON records and no detected CPU
failure. Original watchdog/panic/ECC zeros verified; calibration helper absent.
ADB and all four SSH/gadget services respond; NCM SSH banner passes (no
authenticated shell claim). The boot-level health gate **did not pass**:
UPower fails217/USER with `Failed to set up user namespacing: Invalid argument`.
Do not reset its failed state or disable isolation to manufacture a clean boot.
The issue/logs are preserved separately; the full startup verdict remains
inconclusive despite successful original-image restoration and transports.

Next: use the actual CPU2/waiter evidence to review which early capture can
obtain CPU2 PC/interrupt state before the watchdog panic. Keep KFENCE's observed
caller role distinct from causation; do not simply disable it and call a clean
boot a fix. No additional hardware boot is registered by these results.
