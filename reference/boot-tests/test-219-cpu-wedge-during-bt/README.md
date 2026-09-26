# Test 219 — a CPU wedge during the Bluetooth round

**This is the pre-existing CPU wedge, not a Bluetooth failure.** Recorded here
because it happened during Bluetooth work and the brief forbids attributing it to
Bluetooth without A/B evidence.

## What happened

After installing the Bluetooth userspace helper and rebooting to test it, the
tablet did not return over USB or ssh. The owner photographed the panel:

```
[   29.939035] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[   29.939070] rcu:   5-...0: (1 ticks this GP) idle=ffb4/1/0x4000000000000000 softirq=1118/1118 fqs=2482
[   29.939094] rcu:   (detected by 6, t=5252 jiffies, g=869, q=1745 ncpus=8)
[   39.940396] rcu: rcu_preempt kthread starved for 2498 jiffies! g869 f0x0 RCU_GP_DOING_FQS(6) ->state=0x0 ->cpu=7
[   39.940419] rcu: Unless rcu_preempt kthread gets sufficient CPU time, OOM is now expected behavior.
```

## Why this is the known wedge and not Bluetooth

**1. The structural signature is byte-for-byte the documented one.**
`docs/CPU_WEDGE_EVIDENCE.md:113` records the canonical form:

```
rcu_preempt kthread starved for 2495 jiffies! g65 f0x0 RCU_GP_DOING_FQS(6) ->state=0x0 ->cpu=7
```

The photo reads `g869` where the document reads `g65` — a grace-period counter,
which necessarily differs per boot. Everything else is identical, including
`f0x0 RCU_GP_DOING_FQS(6) ->state=0x0 ->cpu=7`.

**2. It matches a wedge recorded earlier the SAME DAY, before any Bluetooth work.**
`reference/boot-tests/test-213-production-initramfs/WEDGE-20260926.md`, committed
as `b5af40b` at 14:52 (this Bluetooth round began later):

```
rcu: rcu_preempt kthread starved for 2498 jiffies! g=221 f=0x0 RCU_GP_DOING_FQS(6) ->state=0x0 ->cpu=7
```

Same `2498 jiffies`. Same stall shape. Different boot, different `g`, no Bluetooth
involvement at all.

**3. It hits the CPUs the document already names.** The photo reports the stall on
CPU 5 with the GP kthread starved on cpu=7.
`docs/CPU_WEDGE_EVIDENCE.md` documents the wedged CPUs as 4 and 5 — the ones that
"did not answer an ordinary IPI" — with CPU 7 being the *reporting* CPU.

**4. Nothing in this round can reach the CPU/RCU layer.** The round's changes are:

| changed | kind | can wedge a CPU? |
|---|---|---|
| `scripts/*.sh`, `scripts/lib/btfw-name.py` | host-side tooling, never runs on the tablet | no |
| `rootfs-overlay/usr/libexec/gts9-bluetooth-address` | a POSIX shell script | no |
| `rootfs-overlay/.../gts9-bluetooth-address.service` | a systemd oneshot unit | no |
| `qca/wcnhpbtfw21.tlv`, `wcnhpnv21g.bin` | firmware blobs read by the BT controller | no |

and decisively:

```
$ git diff --exit-code 24dd156 HEAD -- kernel/ boot/
(kernel/ and boot/ are IDENTICAL to 24dd156 — the RTC-verified, already-flashed state)
```

No kernel source, no DTB, no config and no boot image was touched or flashed this
round. The running kernel is the same binary that booted cleanly for the RTC
verification (test 216) and for the three Bluetooth bring-up boots in tests 217
and 218.

**5. The documented base rate makes this expected.** `docs/CPU_WEDGE_EVIDENCE.md`
gives the post-fix rate as **1 of 29 boots (3.4%, CI 0.6–17.2%)**. A wedge during a
handful of Bluetooth test boots is within that. The document explicitly warns that
the rate must be counted by this whole signature and that flashing, entering
recovery and pulling power are *not* confounds for it — only an unanswered NMI is.

## What this does and does not establish

* **Established:** the failure is the repository's known CPU-level wedge, on its
  documented CPUs, with its documented signature, and the round changed no kernel
  code that could produce it.
* **NOT established:** that Bluetooth *cannot* contribute. Proving that would need
  an A/B comparison (identical workload with and without the Bluetooth helper over
  enough boots to separate a 3.4% base rate). That has not been run, so the honest
  description is **"a wedge coincident with Bluetooth work"**, which is what the
  brief asks for, not "Bluetooth caused a wedge".

## Consequence for this round's Bluetooth work

The cold-boot verification of `gts9-bluetooth-address.service` is **incomplete**:
the reboot that was meant to exercise it ended in this wedge, so the unit's
automatic path has not been observed end to end. What *was* verified, by running
the helper directly on the tablet, is recorded in
`reference/boot-tests/test-218-bluetooth-firmware/`: the address is read from
`/efs/bluetooth/bt_addr`, the controller leaves `DOWN RAW`, comes up
`UP RUNNING` with `BD Address: 38:8A:06:59:04:E7`, and `btmgmt find` discovers
devices. The unit wiring around it is unproven.
