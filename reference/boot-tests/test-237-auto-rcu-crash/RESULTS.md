# Test 237: automatic RCU capture and controlled-panic retention pass

The real RCU detector automatically captured the bounded snapshot, and all
58 marker lines survived a subsequent controlled panic and automatic reboot
exactly after ECC correction. This validates these instrumentation paths in
this calibration. It does not repair or identify the spontaneous CPU failure,
prove full event history, or guarantee capture during a total CPU lockup.

## Source and automatic trigger

Source boot: `1926858e-37b8-40be-a38c-689ef86583c3`.
Capture: `597e2daf-1b06-488f-9d91-09f3544a5723`.
READY at 100,000,000 ns; ECC64 and runtime watchdog/soft_watchdog/
softlockup_panic/panic=1/1/1/10 verified. Console threshold 4 admits level 0.
RCU timeout=21, suppress=0 and panic_on_rcu_stall=0 were read independently.
The same source passed 162.83 seconds without detected spontaneous CPU stalls
before injection. The preflight journal and immutable boot identity are saved.

The root-triggered CPU-0 normal-priority thread entered its identified RCU
reader at ~176.126 seconds. The unchanged RCU warning tracepoint invoked the
existing snapshot at ~197.124 seconds, approximately 21 seconds later. The
warning names `gts9-rcu-test`; this is the intended synthetic stall, not the
original unexplained CPU non-response. No backtrace IPI non-response was found.
The reader exited at ~211.127 seconds and its queued callback completed;
status read at 211.63 seconds confirms started=1 finished=1 gp_done=1.
ADB continued to respond throughout.

The host saved the complete live journal and decoded eight valid CPU records,
48 event cells, **58 lines / 6,293 canonical bytes**, trigger=rcu, SHA-256:
`3258d3d3b511563730ecdf1fb5bf9b6fba5c4d6f9d0a36d37cb980ca74b4dbbd`.
Only after this check and a successful sync/identity/panic preflight did the
host issue one SysRq c. Its ADB command timed out as expected; that timeout
alone is not used to establish a crash.

## Recovered crash evidence

Immediate retained observer: `2856e9cd-3cac-452b-8a05-354e6792a125`.
Raw console includes `Kernel panic - not syncing: sysrq triggered crash` at
224.641 seconds and `Rebooting in 10 seconds..`. This positively establishes
the controlled panic. The retained journal boot list puts observer immediately
after source; it cannot rule out a boot that left no journal at all.

Two early USB pulls and the observer's device-side hash agree:
`8d3d143dceb1597efb34e408eab5bcb045c68857815990103cd3290979312cde`.
The recovered console reports **189 Corrected bytes, 0 unrecoverable blocks**.
Strict decoding and comparison against the pre-panic live reference recover
every canonical marker byte exactly. See `observer/verdict.json` and the two
raw `.bin` files. The observer was a retrieval boot, not a stability trial.

## Build, scope and rollback

Diagnostic patch 0025 is separately opted in and requires patch 0022. It adds
only the once-per-boot bounded reader test; the capture callback is unchanged.
Patch 0024 supplies the same ECC64 layout as test 236. Config, DTB and release
hashes match test 236; only Image.gz changes. Clean ccache build, packaging and
four focused decoder tests passed. No full host suite or remote CI was needed.
Rootfs, NCM/ADB configuration, clocks, voltages and reserved memory are unchanged.
The source checkout already contained local overlay changes; this run did not
alter them. The build used a fresh disposable worktree at the verified pin.

Only boot/vendor_boot were flashed. Original images were restored after
retrieval through the established BCB helper and TWRP; complete readbacks and
all five production partition hashes pass. Final production boot
`6d4e3bae-b772-4ae8-91e2-3034b6205b96` passed a **161.11-second** observation
with ECC=0, zero failed systemd units and no detected CPU non-response, RCU
stall or workqueue lockup. USB ADB responded and Windows received an SSH
protocol banner over the unchanged NCM interface. No authenticated SSH shell
or long-term stability claim is made. See `production/verdict.json`.

## Interpretation and next step

Manual normal-reboot retention (236), real RCU-triggered capture and subsequent
controlled-panic retention (237) now pass their defined calibration gates.
A naturally failing CPU may behave differently and may prevent any reset or
capture. These records contain only last positive observations, never enough
history for missing-event inference. ECC success in one trial does not provide
an end-to-end integrity proof for a future snapshot without a live reference.

Next pre-register a single natural-failure capture with the calibrated
0022+0024 recorder, omitting the injection patch/flag. Preserve source identity,
arming, ECC notices, raw records and any independent journal copy; reject
invalid/incomplete or unverified data rather than naming a driver from it.
Do not resume an unbounded reboot series or count this synthetic event as a
natural CPU fault. The current result leaves CPU root cause unresolved.
