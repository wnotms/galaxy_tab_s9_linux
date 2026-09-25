# test-188 result: 6 warm-reboot cycles on the post-hwspinlock kernel

Run 2026-09-25T01:13Z → 01:55Z. Profile A, the already-flashed kernel:

| image | sha256 |
|---|---|
| `boot.img` | `bf6a02bbe19e9561be2bae6d691cbaad0c3871ed4efc3878b8f689f2af00bd3e` |
| `vendor_boot.img` (profile A) | `06902f993f6fe9b682686ab36ad956032a8f6a250e595a85e1d7ac82092f211f` |

No flash, no partition write, no command-line change. Every cycle a warm reboot
issued over COM17, labelled `kind=warm-reboot`.

## The result

`classify-captures.py` over the six raw captures (full output in
`classify-captures.txt`):

| round | verdict | boot after | `previous_boot_end` | `reboot.target` | `systemd-shutdown` | open silence | `CTXFAULTS` |
|---|---|---|---|---|---|---|---|
| 1 | clean | `cfd83b6a` | clean-shutdown | 1 | 3 | 0.906 s | 3 |
| 2 | clean | `2e629ae6` | clean-shutdown | 1 | 0 | 1.015 s | 3 |
| 3 | clean | `2381ae1f` | clean-shutdown | 1 | 2 | 1.085 s | 10 |
| 4 | clean | `e94ab268` | clean-shutdown | 1 | 1 | 0.995 s | 2 |
| 5 | clean | `300173a4` | clean-shutdown | 1 | 1 | 0.910 s | 10 |
| 6 | no-stall-signature | `fd68fa9c` | not captured | 0 | 0 | 1.067 s | 10 |

**Zero stalls, zero panics, zero lockups, zero hung tasks, zero RCU stalls, zero
unattended resets.** Five rounds carry a positive completion marker — either the
device's own `previous_boot_end=clean-shutdown` or `Reached target reboot.target`
on the console. Round 6's gadget dropped 1.24 s after the first stop line, before
`reboot.target` printed, so its completion marker was never captured; it is
recorded as `no-stall-signature`, **not** as clean.

Also measured every round, and unchanged from round 15: `GPU=adreno`,
`DEF=3`, `ADSP=offline`, `ACD=0`, `RPMH=0`, `FAILED=0`, `BURST=2`. The early
`arm-smmu` context faults varied as expected — **2, 3, 3, 10, 10, 10** — always
with the single `SID=0x1c00`, re-confirming `docs/EARLY_SMMU_CONTEXT_FAULTS.md`.

## The runner mis-scored one third of the series

`shutdown-series.sh` classifies a round on `systemd-shutdown` alone, and that
marker is unreliable here: the USB gadget disappears at the moment
systemd-shutdown starts printing. Counts fell 3, 0, 2, 1, 1, 0 across the six
rounds, so rounds 2 and 6 were reported `unknown-capture-empty`.

`classify-captures.py` was written for this and replaces the single marker with
two better signals plus a calibrated measure:

* **`previous_boot_end`** — the device's own verdict from the previous boot's full
  journal, authoritative and unaffected by when the gadget drops;
* **`reboot.target`** — systemd prints it *before* handing over to
  systemd-shutdown, so it survives the drop more often;
* **longest open-port silence** — the failure's actual signature. Measured:
  **0.597–1.085 s across the 15 clean rounds** in test-187 and test-188, and
  **28.903 s** in the test-184 A-5 failure. The threshold is 5 s.

Run against test-187's 8-round series it independently reproduces 8/8 clean — and
flags the unattended reset that series never noticed, which is
`docs/STALL_FAILURE_SHAPE.md` §6.

## What this does and does not establish

**Supports:** the current kernel has now completed six more consecutive warm
shutdown cycles with no stall signature, on the provider set that round 15
changed. Combined with `test-187`'s record — with its one correction — that is 20
cycles with one unattended reset, none of them showing the shutdown-path failure
`docs/STALL_FAILURE_SHAPE.md` §1 describes.

**Does not establish a fix.** There is still **no pre-fix rate**: the two archived
failures were found by reading archives, not by counting attempts, so "N clean"
cannot be compared against anything. Every cycle is a warm reboot, not a cold
boot, and no cold-boot claim is made — a cold boot needs the power button and
cannot be captured while USB is attached, because the tablet powers on from VBUS
(`test-187/on-device/COLD-BOOT-CONSTRAINT.md`).
