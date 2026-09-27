# Test 242: one pseudo-NMI natural-capture window; no fault reproduced

CPU repair remains open. Target `c2f8ec82-d57e-4c42-8dc9-7ab2b3900f08`
reached **308.48 seconds** without a detected CPU/RCU/workqueue failure or
registered suspect timeout. No automatic lastactivity snapshot or naturally
stalled CPU stack was produced. This is not a repair, a rate comparison, or
proof that pseudo-NMI changes the fault.

## Identity and scope

Reused the exact test241 kernel, DTB, configuration, vmlinux and System.map.
Only the early `gts9_pnmi_test.enable` boot flag changed 1 to 0. Package and
backup checks passed; boot.img equals test241 byte-for-byte. No kernel rebuild
or unrelated full host regression was needed. Detector replay used the actual
CPU2/5 failure archive and two healthy archives, plus relevant edge cases.
Source/plan commit before flash: `23ab822`.

Runtime verified GIC pseudo-NMI and priority masking, watchdog 1/1/1/10,
ECC64, console threshold 5, helper enable=N and started=0 throughout. Kernel
notes matched the saved symbols; all six anchors gave **+0xb0000** for this
boot, not the previous boot's +0x20000. Lastactivity ID:
`c748cbd4-d315-473d-950f-78ae50ca00f0`. No calibration, manual dump, hotplug,
load injection or panic was requested. BBM remained absent.

The host followed this immutable boot's kernel journal continuously and made
19 identity samples. Follow's initial default is only ten records, so a
separate complete startup catch-up was saved and classified clean without
restarting the live process or tablet. Initial/full final journals cover the
whole target; all raw command metadata remain archived. At the planned end,
the live host process was terminated intentionally (status -15), not because
of a device or stream failure. No additional target was started.

Afterward the same immutable target supplied **1,104 kernel JSON entries**,
all with matching boot ID and kernel source-boottime timestamps. This avoids
reusing rendered receipt time for future duration inference. See natural/,
target/, validation/ and runner/ for exact commands, raw data and verdicts.
For the next collector use `-n all` at follow startup and keep source fields.

## Separate historical finding

An offline audit of test235's binary journal found that two nominal ten-second
backtrace waits actually spanned **10.001179 / 10.001217 seconds** on the kernel
source clock, although journal header deltas were only 21/20 microseconds.
The old delay-loop inference is withdrawn. This does not locate the CPU fault
or prove every historical wait duration. The independent evidence is in
[the source-time audit](../../offline-reviews/20260927-journal-source-time/README.md),
committed separately as `97bd5d9`.

## Recovery

BCB/plain reboot reached TWRP; original boot/vendor_boot were restored and
all five partition hashes matched production. Final production boot
`d95f41a4-ca6e-4bd5-8a35-207126620d14` passed **214.07 seconds** with
no detected CPU failure, zero failed units, the original watchdog/panic/ECC
zeros, and no calibration helper. USB ADB commands and all four relevant
services respond; Windows NCM receives the SSH protocol banner. No
authenticated SSH session or long-term stability result is claimed.

## Next discriminating step

Do not repeat the same clean boot as a repair claim. A less intrusive capture
can now retain the calibrated standard pseudo-NMI backtrace path while turning
off optional lastactivity callbacks at boot. Verified source la_init returns
before all seven tracepoint registrations when gts9_lastactivity is not 1.
Those callbacks otherwise add preemption control, atomic accesses, clock
reads and memory barriers to IPI/CSD paths. Removing them reduces diagnostic
perturbation; it is not evidence that the recorder causes or hides the fault.
Test235 already observed CPU2/5 failures without that recorder, but the small,
uncontrolled histories cannot establish a rate difference. Register any next
single-variable trial before flashing; keep ECC64, pseudo-NMI, symbols and
power settings fixed and retain the loss of lastactivity evidence explicitly.
