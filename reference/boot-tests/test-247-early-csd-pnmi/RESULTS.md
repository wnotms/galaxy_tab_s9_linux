# Test247: natural stall captured inside the ARM DCC transmit loop

**The cause of this observed stall is now identified; a fix is not yet applied.**
Pseudo-NMI captured CPU4 inside hvc_dcc0_put_chars with normal IRQs masked,
while CPU1 and CPU7 waited for it through CSD. The process was `(agetty)`.
This is the failed target's own PC, not merely a synchronization waiter's stack.
Earlier failures may share this mechanism but are not retroactively proven.

## Exact target and evidence

Deployment source bb11a37. Matched181-file modules plus boot/vendor_boot were
verified in TWRP before reboot; other partition hashes were checked unchanged.
Target `e432f1a0-f6ab-4e82-be70-4c9ba7ab80cb`; capture ID
`49aded33-4369-49a8-8da6-2adf06809e75`. Notes and six anchors agree on+0x88000,
also matching the eventual panic's Kernel Offset. First ADB response6.71 s;
GIC pseudo-NMI, LA1/ECC64, watchdog1/1/1/10, CSD timeout5000, CSD panic0 and
RCU detailed-report suppression=N were verified. All181 candidate module files
match. No failed-target loaded-module-note check completed; do not substitute
an observer's notes. The observed DCC fault is built-in kernel code.

| Source time | Attributed observation |
| --- | --- |
| 6.502969 s | systemd starts serial-getty@hvc0.service |
| 13.831690 s | CPU1 has waited5.000000102 s for CPU4 do_nothing |
| 13.832136 s | CPU4 pseudo-NMI answers; PID1251 `(agetty)`, PC hvc_dcc0_put_chars+0x34 |
| 14.055159 s | CPU7 reports its own CSD wait for CPU4 rcu_barrier_handler |
| 29.746246 s | RCU-triggered CPU4 backtrace shows the same DCC loop |
| 35.664604 s | Third CPU4 backtrace again shows the same DCC loop |
| 35.689645 s | CPU7 soft-lockup panic; later panic=10 reboot |

The exact compiled+0x34 instruction is `yield` in the loop reading
MDCCSR_EL0 and testing bit29. Saved x9=0x20000000 is TX-busy; saved PMR=0xc0
masks ordinary IRQs while the higher-priority backtrace still works. The pinned
hvc_write holds its spin_lock_irqsave while hvc_push calls the driver's
put_chars. With HVC_DCC=y and HVC_DCC_SERIALIZE_SMP unset, the wrapper directly
uses an unbounded DCC transmit loop on the calling CPU. This explains this
CPU's failure to service normal IPIs without assuming a dead CPU, firmware
entry, KFENCE causation or an RCU root cause. The observed target was CPU4,
not the CPU2 target from245.

The host stopped on the first positive signature, not after120 s. It retained
1335 source-time target kernel records, then final systemctl health timed out.
That timeout does not invalidate the positive captured stack. Subsequent
failure-live/identity-process was already boot ca2235ae-e5c9-4129-858c-9cea934a2c52;
its PID1251 was a NetworkManager thread. That /proc information is explicitly
observer-only. The retained boot history identifies it as the immediate
successor. The by-ID full target journal proves the hvc0 getty startup.

## Retention and limits

Two raw ADB pulls of each pstore file match device hashes before and after.
Console:31589 bytes, SHA1931b7ce7de7d291c7d1f813de292f683e180c3f0fbc78a950144310f4efed4c.
Panic:135119 bytes, SHAceffaef55edfc795f7bf5e3855972d806b61343320f2d28d5ee66c38d7245122.
ECC reports2227/2314 corrected bytes and zero unrecoverable blocks respectively.
Unlike245,14 selected failure/backtrace messages can also be compared against
independent live JSON: both retained areas match exact text and source time.
That validates this selected overlap, not every byte of the crash payload.
The older .enc.z and pmsg files retain old metadata and are not attributed here.
Raw logs, source snapshots, exact disassembly and replayable attribution checks
are preserved in retained/, observer/, target-run/ and analysis/.

## Restoration and next repair

Both original images and all181 original module files are restored; all-five
partition hashes match the original baseline. The owned used-candidate directory
was removed only after checking all181 candidate hashes. No SSH/USB setting or
rootfs service was changed. Production6c51a304-186e-41bd-a38c-e6040ddeeaba passed
120.08 s with1089 source-time kernel records and no failed units. At151.52 s,
ADB and all four SSH/USB services respond, with a Windows NCM SSH banner.
No authenticated SSH shell was tested. Earlier UPower217/USER remains a separate
unresolved finding. Full health in this one boot does not erase it.

The one247 trial is closed. Next remove the inherited ARM DCC driver from this
tablet's mainline config, assert its absence in build validation, and verify a
repair candidate has no DCC hvc0/getty path while retaining panel/ADB/NCM SSH.
This targets a directly observed unbounded IRQ-masked wait; it does not require
another speculative power/clock change. Repair still requires actual build and
hardware validation. No more247 boots.
