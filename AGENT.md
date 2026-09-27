# AGENT.md — SM-X710 mainline port working rules

## Current review (2026-09-28)

Test245 now CLOSED with a real natural startup failure before its workload.
Fixed-BBM target9c9d553e-86c9-4b80-b6d7-9c29447f7125, cap9343ce3b-8159-47ad-
a4be-5cb28d453aad, exact notes/six anchors +0x178000. Retained console/panic
agree on48 last-activity cells: RCU CPU2 at30.68 s, CPU1 soft lockup/panic at
36.54 s. Exact binary/registers show CPU1 waiting for CPU2 synchronous CSD
inside KFENCE static-key synchronization; CPU2's own stack is missing.
Two pulls/device hashes agree, ECC1004/1814 corrected/zero bad; no independent
live reference, so do not overstate integrity. Older .enc.z is unattributed.
BBM0026 did not prevent this failure; no helper execution/low-address coverage
or failure-rate/causal claim. Defer that independent branch and prioritize the
new natural CPU2 evidence; no more test245 boots. See test245 RESULTS.md.

Original images/all-five hashes restored. Production bd20438b-cea6-4172-8e5f-
de83a6b69a51 has no CPU signature in120.08 s and working ADB/NCM SSH banner,
but full health is INCONCLUSIVE: UPower fails217/USER (user namespace EINVAL).
This issue is archived, not hidden/reset. Recovery observer's systemctl reboot
returned Access denied; ordinary reboot.target transaction worked. No rootfs
or USB change. Next review CPU2 capture before panic; KFENCE waiter is not proof
of the target's root cause. CPU repair remains OPEN.

Test245 is pre-registered for one low-address coverage boot using exact test240
corrected-BBM artifacts. Offline helper review is in
reference/offline-reviews/20260928-bbm-low-address/. It maps one page at0x1000
with NOREPLACE, verifies old valid/executable PTEs and performs16 permission
changes; no deliberate instruction abort or global mmap setting change.
The owner questioned the repeated300 s wait. For this focused trial use120 s
total uptime, profile ready by90 s, workload after60 s and >=30 s afterward;
early failure stops immediately plus bounded20 s backtrace collection.
Production restoration also gets120 s. This is a shorter startup check, not
long-run health or CPU-repair proof; older completed results stay unchanged.

Tests243/244 completed a shared minimal-observer session. Exact test241 kernel,
lastactivity=0 and calibration=0; pseudo-NMI/ECC64 and 1/1/1/10 remained active.
TWRP-entry target 2094eeee-8fe2-48e5-aea6-abbc1788ea92 passed 306.92 seconds
(offset +0x188000). Separately pre-registered direct normal-reboot target
fd1a8ab6-85e9-40fb-b321-207faeaaa525 passed 304.07 seconds (+0xc8000), with
automatic full capture starting by 17.45 seconds. Notes/six anchors were
independent per boot. No natural fault or failed-target stack was captured.
All 1,103 / 1,099 live JSON records respectively have target identity/source
time; each boot has one priority-0 userspace attribution marker. No claim
that recorder removal, NMI, or a reboot path changes the failure rate.

Paired rollback restored originals/all-five hashes. Final production
1aaffb9a-3a07-4415-91a8-7bf40d14328e passed 179.21 seconds; original
watchdog/panic/ECC zeros, helper absent, ADB/NCM SSH protocol responsive.
No authenticated SSH session or CPU-stall repair claim. See test243/244
RESULTS.md; both fixed attempt budgets are closed, no more identical boots.

The seven feature-variation warnings in test244 are only SpecSEI differences
in AA64MMFR1/MMFR4. Pinned strict/higher-safe policy conservatively retains 1;
this explains the taint, not CPU failure. No policy was changed; do not mask
the warning as a repair. See reference/offline-reviews/20260928-specsei-variation/.

Next return to the concrete opt-in A715 BBM defect: test240 physically covered
high-address nr=1, not the low-address underflush/empty-range branch. Prepare
and review a bounded missing-branch reproducer offline first, including
mapping permission/fault handling/path-proof gates and recovery. Keep BBM
validation separate from proof it caused the multi-CPU stall, and register
any later fault-generating hardware scope before use. No blind power changes,
further identical clean-window trials or completion claim.

Test-242 reused the exact test241 kernel with calibration enable=0. Target
c2f8ec82-d57e-4c42-8dc9-7ab2b3900f08 passed 308.48 seconds without detected
CPU failure; no natural snapshot or failed-target stack exists. GIC pseudo-NMI,
notes/six anchors (+0xb0000), ECC64, 1/1/1/10 and inactive helper were verified.
Full source-time JSON (1,104 kernel records) supplements the rendered journal
and live stream; the initial default-ten-line follow view was supplemented
without restarting the process or device. All five original hashes restored.
Final production d95f41a4-ca6e-4bd5-8a35-207126620d14 passed 214.07 seconds;
USB ADB and NCM SSH banner respond, no authenticated SSH session claim.
CPU repair remains OPEN; see test-242/RESULTS.md.

Separate binary-journal review corrected an old timing error: test235 CPU2/5
backtrace waits span 10.001179/10.001217 seconds on kernel source timestamps,
while journal receipt deltas are only 21/20 microseconds. Do not investigate
mdelay failure based on that rendering artifact or infer simultaneous onset.
See reference/offline-reviews/20260927-journal-source-time/ and corrected
docs/CPU_WEDGE_EVIDENCE.md. Preserve raw JSON/export source fields for timing.

Next reduce optional observer perturbation before another capture: keep the
calibrated standard pseudo-NMI/ECC64 path but consider lastactivity=0, whose
verified la_init branch returns before all seven tracepoint registrations.
The active recorder adds preemption/atomic/barrier/clock work to IPI/CSD paths.
This is a reason to simplify diagnostics, not proof it hides or causes faults.
Test235 had real failures without it, but no controlled rate comparison exists.
Pre-register one variable and a fixed attempt budget; keep BBM/power settings
separate. Use -n all at journal follow startup and retain source-time fields.
Do not repeat the same clean window or treat synthetic passes as CPU repair.

Test-241 calibrated the isolated pseudo-NMI route (0022+0024+0027, no BBM).
CPU0's actual backtrace arrived 61,407 ns into a 200,000,157 ns PMR-masked
interval with NMI context and saved IRQ-disabled PMR; both workers completed.
The stack is the expected calibration counter-read loop, not a clocksource
fault. After a clean 73-second post-observation, the immediate normal-reboot
observer recovered all 28 lines / 1,583 payload bytes exactly (two pulls/device
hash agree; ECC corrected 61 bytes, zero unrecoverable blocks). Source boot
3bfa876b-be6e-49d3-8029-79e65d0f7ba6, offset +0x20000 with matching notes/anchors;
observer e72b6d0c-fbf6-4348-bccb-93db1c14e98b. CPU repair remains OPEN. Only the
healthy CPU0 masking and warm-retention cases were measured.

Original boot/vendor_boot and all five hashes restored. Final production
6a9e0303-fc8c-4c7f-a18a-0a26727a49cd passed 215.02 seconds; USB ADB
and NCM SSH banner respond (no authenticated SSH session claim). Watchdog/
panic/ECC are back to production zeros and the calibration helper is absent.
Next pre-register one bounded natural failure capture with pseudo-NMI active
and the synthetic trigger disabled; keep BBM separate, preserve exact target
symbols/offsets and stop at first failure for review. Do not repeat a successful
calibration or treat absent failure as repair. See test-241/RESULTS.md and
docs/PSEUDO_NMI_DIAGNOSTIC_REVIEW.md.

Test-240 physically validated the opt-in 0022+0024+0026 BBM candidate. Target
fe1196f2-4464-4c82-b63e-7f875c88223b passed 169 seconds before an A715 CPU3/4
permission workload, 6,049,962 sustained mprotect calls and 75.75 seconds
post-workload. Six preliminary kprobe hits prove high-address nr=1 path
coverage; no natural failure or CPU-stall repair is established. The initial
tracefs text-append setup failed before workload and was fixed with raw
non-truncating writes; preserve both attempts. All owned tracing was removed.
Original images/five hashes restored. Final production c333bb1b-d09b-4b32-
ac4f-d8e166d4cac7 passed 153.52 seconds with ADB/NCM SSH banner responsive.
See test-240/RESULTS.md; defaults stay unchanged, 0026 remains opt-in.

The pre-test240 follow-up investigated the missing stack via pseudo-NMI;
test241 above now supersedes its untested status.
The old inference that ordinary-IPI non-response excludes NMI-only capture
was incorrect and is withdrawn. Pinned sources show PMR-based IRQ masking and
per-CPU NMI backtrace routing only with CONFIG_ARM64_PSEUDO_NMI plus the boot
flag and successful runtime setup. Test241 has now built/flashed and calibrated the isolated candidate.
See docs/PSEUDO_NMI_DIAGNOSTIC_REVIEW.md for the bounded IRQ-masked calibration
design and limits before using it. Keep BBM and NMI causal variables separate.


Tests 238/239 reused calibrated 0022+0024 without injection: one 304.96-second
and two 184-second natural boot windows did not reproduce the CPU failure.
This is not a repair/rate estimate; no spontaneous snapshot was available.
Per-boot runtime symbol relocation differs despite nokaslr: +0x8000,
+0x100000, +0xd8000. Verify the actual target's anchors/kernel notes; never
reuse an observer's offset. Original boot/vendor_boot and all five hashes
were restored; final production 0893538f-26ac-4965-9d76-f57b3b7886c5 passed
162.65 seconds, USB ADB and NCM SSH banner responsive. See test-239/RESULTS.md.

A separate source review verified A715 BBM TLB end-address bug in the pin.
Exact arm64 maintainer commit 1fef81669147d63eb8c5d3627d54eadc21173a0b is opt-in
patch 0026, not a production change or established CPU-stall cause. The actual
function harness fails 12/120 cases before and 0/120 after; clean ccache build
and out/boot-bundle-bbm-range packaging passed. Config/DTB/release equal test236;
new symbols are out/test240/vmlinux and System.map. Candidate is NOT flashed.
Mainline-master compare diverged at check time; do not call it mainline-merged.
Next assess a separately registered candidate validation, including a bounded
permission-change workload to exercise the corrected path, and preserve the
CPU-failure goal rather than treating range correctness as stall resolution.
See reference/offline-reviews/20260927-a715-tlb-range/.


Test-237 passed actual RCU-triggered capture and later controlled-panic retention.
An explicitly injected 35-second PREEMPT_RCU reader triggered the unchanged
RCU callback after ~21 seconds; thread and callback both completed. All 58
marker lines / 6,293 bytes survived SysRq panic and automatic reboot exactly;
ECC corrected 189 bytes, zero unrecoverable blocks. Source 1926858e-37b8-40be-
a38c-689ef86583c3, observer 2856e9cd-3cac-452b-8a05-354e6792a125. This is synthetic
calibration, not spontaneous CPU failure or a root-cause fix. Test-only patch
0025/flag must be omitted from future natural-failure trials. Next register one
natural-failure capture using 0022+0024 with explicit integrity/attribution
limits, not an unbounded reboot series. See test-237/RESULTS.md. Original
boot/vendor_boot and all five partition hashes were restored after collection.
Final production boot 6d4e3bae-b772-4ae8-91e2-3034b6205b96 passed 161.11 seconds
without detected CPU stalls; USB ADB and SSH protocol over NCM responded.
This is a bounded observation, not long-term stability.


Test-236 passed exact lastactivity console retention on a normal warm reboot.
Source 10f7f83a-d669-4855-8f24-87b5c6568aa6 produced 58 lines / 48 event cells /
6,294 canonical bytes; observer 95089f53-9cd4-41d3-a799-85a648485731 recovered
identical markers after ECC corrected 135 bytes, zero unrecoverable blocks.
Source runtime arming was 1/1/1/10; level-0 output passed console threshold 4.
This clears manual-snapshot normal-reboot retention only, not automatic RCU
capture/crash retention, CPU causality or readiness for a wedge series.
Original boot/vendor_boot and all five production hashes were restored.
Final boot d5fd2f74-0854-41f4-b8f2-94874d63340f stayed responsive beyond
151 seconds without detected CPU non-response/workqueue stalls. USB ADB and
SSH protocol over NCM responded; no long-term stability claim.
See test-236/RESULTS.md. The combined diagnostic is opt-in; defaults unchanged.

Test-235 completed retrieval: ECC=64 recovered the exact 33,005-byte PMSG,
correcting 246 bytes with zero unrecoverable blocks. Device hash, two TWRP
pulls and the original observer journal's FILE field match. Its level-6
console probe was filtered by loglevel=4: invalid console test, not a pass.
CPU failures remain (manual boot c1027ef1-e680-425b-b6fc-6d7819800639: CPUs 2/5).
Original boot/vendor_boot and all five partition hashes were restored.

Restored boot 2d1619e1-3130-418c-b5d3-af51b14e9280 later powered off normally.
A subsequent owner-started production boot f4d0de47-11eb-4aa5-a19e-9263ed385a31
has CPU 5 non-response despite ADB/systemctl answering at 200 seconds; firmware
appended lpcharge=1. Do not label it healthy or attribute the failure to that
flag. The recovery helper's read-only BCB check timed out without a write;
owner restart aad74b03-7579-49dc-ba8e-d50b6e8269bd then allowed the normal
BCB helper to reach TWRP, where all production hashes were verified again.
Device is parked in TWRP while Test-236 prepares existing lastactivity pr_emerg
(level 0) plus ECC=64 for console retention calibration; no wedge series.
See test-235/RESULTS.md and test-236/README.md.

Latest: tests 233/234 isolated corrupt retention further. Test-233 recovered a
known 33,005-byte PMSG with 464 changed bytes / 542 bits. Test-234's opt-in
read-only live RAM view proved exact bytes in three reads before reboot, but
the next boot recovered 251 changed bytes / 293 bits. Damage occurs after the
final source read and before observer archive reads; no CPU causal link is
established. No wedge series before trustworthy retention. See test-234/RESULTS.md.

Test-234 observer `4c78d2cc-7ed8-4a33-be1c-05c2345f77c5` lost responsiveness.
After owner manual recovery to Debian, its disk journal confirms CPU 5
non-response to the backtrace IPI and RCU/workqueue stalls. CPU 7's responsive
idle stack is not the stalled CPU's stack. The helper then reached TWRP;
original boot/vendor_boot were restored and all five partition hashes match
production. Restored boot e1ae1723-f52f-4493-9088-6df9a58a46cc passed a
151-second responsive observation; no long-term stability claim. Test-235 prepares an
isolated upstream ECC=64 retention calibration, not a CPU fix or wedge series.

Read `docs/STALL_TEST_WORKFLOW.md` before continuing stall work. It supersedes older causal exclusions and trace sizing assumptions. The owner resumed hardware work on 2026-09-27. Test-229 captured another CPU 6 non-response, followed by owner recovery to Debian and a healthy 60-second calibration. Memory coverage passed for that observation, but the reduced seven-event set still exceeds the persistent text budget (2,213,931 bytes in 41 seconds versus 786,432 available). Offline bounded replay is now complete: corrected ramoops budget is 393,204 bytes because the 896 KiB request rounds down to 512 KiB, with a 12-byte header and 128 KiB crash reserve. Equal per-CPU text tails keep only about 2 seconds on CPUs 0/7 with modeled 32-byte prefixes. This fails the original 41-second question; select a separately validated sink or explicitly narrower positive-evidence question before preparing a hardware candidate. No new wedge series before retention passes. The unchanged production profile has watchdog/panic disabled, so matching production partition hashes does not establish the armed stall baseline. Do not reuse the outdated parked baseline bundle. Preserve the production kernel/configuration while establishing retention.

Test-230 subsequently built and physically tested the opt-in last-activity
instrument (diagnostic patch 0022). Live capture passed: READY at 0.103705 s,
48 event cells / eight valid CPUs, 6,245 marker bytes. The source trial used
watchdog/panic state 1/1/1/10. Persistence through Debian → TWRP → restored
Debian failed to yield matching pstore; only old archives remained. Production
boot/vendor_boot were restored and all five partition hashes verified. Next
perform one healthy direct Debian → Debian persistence calibration with the
same bounded candidate, keeping the source capture ID distinct from later
boots. No wedge series before retention passes. See test-230/RESULTS.md.

Test-231 tested that same candidate through a direct Debian → Debian warm
reboot. Pstore retained the source capture but corrupted 8 of 58 marker lines
(18 bytes / 26 bits); two repeat reads matched device-side hashes while the
source journal remained exact. Retention integrity therefore still fails,
with ECC=0 confirmed at runtime. This does not locate the corruption or prove
a shared cause with CPU wedges. Next validate known payload/checksum retention
and consider a separate ECC diagnostic within the existing reserved region;
no wedge series yet. See test-231/RESULTS.md for source/observer IDs and rollback.

Test-231 rollback restored all production partition hashes, but boot
79815bbb-a96b-40c3-a152-ab958fd57d5d then wedged on CPU 5 with PID 1 blocked
and systemctl timing out. The owner returned to TWRP; recovery evidence is
archived. Image integrity passed; healthy rollback boot did not. USB ADB work followed at the owner's request while preserving NCM/SSH.

Test-232 added native USB ADB to the existing NCM gadget. Final boot
 a80804be-229c-46f7-aae8-bd797fb22883 has USB/TCP ADB and SSH responsive after
more than 150 seconds. Existing SSH survived stopping adbd (100 heartbeats,
max gap 2.01 s). Preserve no_disconnect, the independent ep0 holder, and the
adbd restart guard: FunctionFS reopening can reset the shared gadget. Prepare
NCM/UDC before adbd's one-second bind deadline, then use bounded 50 ms polls.
Changes apply next boot; never unbind a live gadget to add ADB. ADB transport
failure can require reboot to recover while SSH stays available. This does not
resolve CPU non-response or corrupt pstore. See test-232/RESULTS.md.

## Mission

Maintain a mainline-first Linux port for Samsung Galaxy Tab S9 Wi-Fi (`SM-X710`, Android codename `gts9wifi`) on Qualcomm SM8550 (`kalama`). Prefer upstream Linux interfaces and bindings. Samsung's downstream 5.15.153 sources/config/device tree are evidence about hardware, not the target architecture.

## Ground truth and pins

- Device: SM-X710 / gts9wifi, Wi-Fi model.
- SoC: SM8550 / Snapdragon 8 Gen 2; GPU Adreno 740.
- Samsung ABL selector values observed in the supplied live DTS:
  - `compatible = "qcom,kalama-mtp", "qcom,kalama", "qcom,mtp"`
  - `qcom,board-id = <0x10008 0x04>`
  - `qcom,msm-id = <0x218 0x20000 0x207 0x20000 0x207 0x10000 0x218 0x10000>`
- Stock config evidence: Linux 5.15.153, Android clang 14.0.7.
- Mainline build pin: Linux `v7.2-rc3`, commit `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
- Bootstrap board DTS reference: `troikoss/gts9wifi-fedora` commit `656d2ded8031657b60cde22e6fdfbc0b722a9dff`.
- Earlier X710 bring-up reference: `Azkali/sm8550-mainline` branch `gts9wifi-7.0`, inspected at `c48fedbd799a2b792a095840eeb96746afe2f327`. See `docs/AZKALI_SM8550_MAINLINE_ANALYSIS.md` and `kernel/PROVENANCE.md`.

Do not silently change either pin. A kernel bump and a hardware-port change must be separate changes so regressions remain attributable.

## Stock evidence supplied by the owner

The owner supplied a live DTB, a decompiled live DTS and a full stock `.config`. Their SHA-256 values and extracted hardware facts are recorded in `reference/stock/MANIFEST.md`.

Important device-specific differences from the S9 Ultra/X910:

- SM-X710 panel: `GTS9_ANA38407_AMSA10FA01`.
- Touch: STM FTS1BA90A, not the X910 Goodix GT9916.
- Pen: Wacom W90xx / WEZ01 family on I2C.
- WLAN/BT: QCA6490/WCN6855-class, not X910 WCN7850/Kiwi v2.
- Power: SM5714 charger/fuel gauge/USB-PD plus SM5440 direct charger.
- Type-C redriver: Parade PS5169; eUSB2 repeater: NXP PTN3222.
- Audio: four CS35L45 speaker amplifiers are visible in the stock DTS.

Never copy the entire downstream DTS into `arch/arm64/boot/dts/qcom/` and call that a mainline port. Translate only evidenced hardware into upstream bindings and keep unsupported vendor-only properties out.

## Repository invariants

1. `scripts/fetch-mainline.sh` must verify the exact upstream commit.
2. The upstream checkout under `.work/linux-mainline` stays pristine.
3. Device changes are staged into a disposable worktree under `.work/build/`.
4. Kernel build output goes to `.work/build/linux-out` and `out/kernel-gts9wifi`; never commit it.
5. Use `USE_CCACHE=1 ARCH=arm64 LLVM=1`; ccache is required for builds. Do not introduce a GCC-only build path unless there is a demonstrated need.
6. Keep critical early-boot/storage/console providers built in when the port depends on them before the root filesystem is available.
7. The owner-extracted stock config is immutable evidence: reconstruct it with `scripts/materialize-stock-config.sh`, verify its recorded SHA-256, then use it as the Kconfig seed. A symbol requested by the mainline fragment but dropped by `olddefconfig` must be treated as a build/config issue, not ignored.
8. Kernel image, DTB, config and release string must be hashed in every build.
9. No build script may flash or repartition a physical device.
10. Do not claim hardware works because a driver compiles or probes. Record `compiled`, `booted`, `enumerated`, and `physically verified` as different states.

## Remote workflow (owner instruction, 2026-09-21)

- `main` is left alone unless the owner explicitly asks for it. Work happens on a
  branch (currently `test`) and is pushed there.
- One purpose per commit; do not batch unrelated work into one commit.
- **Push to `origin` after every operation.** Verified work must not exist only on
  the local disk: commit it and push the branch, so the remote always matches what
  was actually built, tested or documented.
- If an operation changes nothing in the tree (a read-only check, for example),
  there is nothing to push; do not create an empty commit.
- GitHub Actions is **manual-only** (`workflow_dispatch`). A normal push must not
  start a kernel build or packaging job.
- Routine development is validated **locally**. After pushing a commit, do not wait
  for, poll, or require GitHub Actions before continuing.
- Run the GitHub Actions workflow only when the owner explicitly requests a remote
  CI check. A local successful build/validation is sufficient evidence for
  `compiled` / `packaged` status; it is still not evidence of a physical boot.

## Current direction and physical-test workflow (owner instruction, 2026-09-21)

- **Milestone reached (test 010, `reference/boot-tests/test-010-.../`): the
  owner watched the tablet power itself off while running this port's kernel.**
  `ABL -> mainline Linux -> BusyBox /init` is therefore established on hardware.
  A hung kernel cannot power a tablet off and `panic=0` removes the only way it
  could fake it. Everything below applies to work *beyond* that chain.
- The "stuck on the Samsung logo" state is a **running initramfs** waiting on a
  console that does not exist (no panel driver, unreachable UART, and a
  `console=null` the bootloader appends). Do not read it as a kernel failure.
- **Do not use the sec_log ring as evidence.** Test 007 measured the
  bootloader's own log spanning 2,096,187 of the 2,097,136 bytes of
  `sec_log_buf`, so mainline writes are overwritten before recovery can read
  them. An empty ring proves nothing. Live channels (USB, once it probes) or
  physical observation are the evidence paths.
- **Storage is up** (test 020): the missing provider was `CONFIG_QCOM_PDC`, the
  interrupt controller the SPMI arbiter hangs off.  With it the microSD (`mmc1`)
  and UFS (`sda`..`sdf`) both enumerate, the PMIC GPIO card detect works, and the
  bring-up report reaches the card - see tests 020 and 028.
- **The evidence loop is closed** (test 028): `/init` writes the report to the
  microSD card, waits ten seconds and resets into TWRP through the Android
  bootloader control block, so a test costs about half a minute and needs no
  hand-carried recovery boot.  `scripts/read-bringup-report.sh` reads the card.
- **The display pipeline is up** (test 035): the ported ANA38407 panel driver
  probes, `card0`/`card0-DSI-1` exist, the connector reports `connected`,
  `2560x1600` appears twice (the panel's 120 Hz and 60 Hz mode sets) and
  `/proc/fb` is `msm-kmsdrmfb`, so fbcon finally has a real surface.  Two things
  had to be true at once: `msm.separate_gpu_kms=1` (the Adreno is a component of
  the msm DRM master and fails without GPU firmware, which fails the card), and
  that parameter must sit near the *front* of our cmdline - the bootloader appends
  kilobytes of its own and was dropping the last token of ours.
- **Display status update (offline audit, 2026-09-22):** test 038's fb blank
  cycle recovered panel ID `80 00 04`, but CTL/vblank timeouts and partial
  pixels remain. Test 039's no-DSC modes exceed the DSI OPP limit and provide
  no decoding verdict. DSC/120 Hz is the default again; premature kickoff
  patch 0005 is held in pending because normal MSM kickoff follows modeset
  enable and DSC preparation. See `docs/DISPLAY_OFFLINE_AUDIT.md`.
- **Official-source candidate v1 (2026-09-22):** the owner supplied the full
  X710 source archive, including vendor display commands. The panel now uses
  X710 slew/PM_EN/TSP-sync/120HS programming, exposes only DSC/120 Hz and uses
  236 x 148 mm dimensions. Stock PPS matches the pinned helpers byte-for-byte
  over its 88 supplied bytes. Kernel, six host tests and an isolated boot
  bundle validate locally. See `docs/DISPLAY_X710_OFFICIAL_V1.md`.
- **The panel displays (test 040, `reference/boot-tests/test-040-.../`):** the
  official candidate was flashed to `boot` only and it works. The owner saw the
  boot command line on the panel, then a green/black marker, then three lines
  written two seconds apart appearing live - so the console both decodes and
  updates. `ctl start` failures are zero, where tests 037-039 never completed a
  command-mode start. What fixed it was the DDIC's own power-on and refresh-mode
  programming (`0x60`/`DD 0x13`/`B9 0x10 = 80 00 00 00` for 120HS), not DSC and
  not the DPU. The panel still cold-boots dark and is still recovered by the
  framebuffer blank cycle, now in 8 s. Unvalidated: the brightness/gamma/ACL
  stack, 60 Hz, other panel revisions, and long-run stability.
- **Pogo keyboard: input driver registered, application startup unresolved (test 045,
  `reference/boot-tests/test-045-.../`).** The driver
  (`kernel/drivers/keyboard-samsung-pogo.c`, `0006-input-add-samsung-pogo-keyboard.patch`)
  binds on hardware, registers `Book Cover Keyboard Slim (EF-DX710)` as event0,
  powers the rail, pulses the MCU's reset and reads its version actively, which is
  how Samsung's own driver proves presence. Five real faults were found and fixed
  along the way: the connect line is an edge not a presence level, cycling the
  rail on every edge reset the STM32 before it could answer, the diagnostic
  flooded the panel console, the handshake was passive, and the SWD pins were not
  owned by the driver.
  At that stage every application read returned `-ENXIO` (a NACK:
  the transfer ran, the bus was idle, nothing acknowledged) and a quick-write scan
  of the whole adapter finds **no device at any address**, while TWRP's stock
  kernel enumerates the same cover minutes earlier as `EF-DX710_v1.4.1.0`,
  `con:1/1`, `model_id 0x2`. The controller, pins (`qup2_se7` on gpio72/106),
  address, IRQ type, reset and rail model all match the vendor node. Two
  candidates were fitted and did not help: patch 0007
  (`samsung,reset-before-trans`, now in `pending/`) and an explicit rail
  power-cycle; both are retired with that result recorded.
  Round 2 compared the stock and mainline regulator tables: the pogo rail is
  enabled in **both** (`fixed_regulator${#}` / `pogo-vdd`, use=1, each with its
  client as consumer), no relevant rail differs, and the rail's source is not
  modelled as a parent in either tree.  It also established that gpiolib refuses
  to hand out gpio72/106 while they are multiplexed to `qup2_se7` (-EINVAL) and
  that `of_get_named_gpio()` no longer exists, which is why the vendor reads those
  lines with `gpio_get_value()` on numbers it never claims.
  Round 3 read the tree TWRP is built from: it uses a **prebuilt stock kernel**
  plus stock `dtb.img`/`dtbo.img` and Samsung's module stack, so its working
  environment is not reproducible in mainline.  Two facts came out of it.  Stock's
  log shows `rst:0`, so the MCU answered first try and was *already running* when
  the stock driver probed - nothing in that driver powers it from cold.  And
  `stm32_pogo_v3_start()` begins by instantiating a second I2C client at
  **`boot_addr = 0x51`**, the STM32's **system bootloader** interface, then runs
  `stm32_dev_firmware_update_menu(stm32, 0)`; the application interface at 0x2a is
  used only after that, and `client->addr != 0x51` guards the driver's power-reset
  and connect-state paths.
  Round 4 implemented that handshake and it answered: `MCU bootloader took the
  0xFF sync`, then `MCU bootloader version 0x12`.  **The MCU is powered and
  executing** - rail, bus, pins and address are all correct, and the whole
  power/supply line of investigation is closed.  What does not happen is the
  *application*: after the vendor's `sysboot_disconnect()` sequence the bootloader
  goes quiet and 0x2a never answers, which is what a boot-mode selection problem
  looks like.
  Round 5 tried both app-entry mechanisms on hardware and both failed: the
  vendor's exact `stm32_sysboot_disconnect()` timings leave 0x2a NAKing, and the
  bootloader's `GO` (0x21) write then times out because by that point the MCU
  answers on neither interface.  It has left the bootloader without the
  application coming up on i2c.
  Round 6 disproved the read-first hypothesis: with no rail cycle, no reset and no
  bootloader dance the application does not answer either, so the MCU genuinely
  sits in its system bootloader and goes quiet on both interfaces after any
  app-entry attempt.  It also established that the gpio12/13 sharing with the DMIC
  is genuine hardware sharing present in the vendor tree as well
  (`dmic45_clk_active`/`dmic45_data_active`, `function = "func1"`), and inactive
  here - the pinmux still shows those pins owned by `5-002a` minutes in.
  Round 7 offline audit (2026-09-22): commit `776b7d4` sends GO while the
  bootloader session is live, but leaves Get Version's final ACK unread. Samsung's
  `stm32_sysboot_i2c_get_info()` and ST AN4221 both require ACK/version/ACK.
  The caller also unconditionally resets after app entry, and the read-first
  success path skips mode checking, leaving `ready` false. These are driver
  defects; the earlier assertion that the remaining issue lies outside the driver
  was not established. The new candidate consumes the full version response,
  restarts a failed version session before GO, preserves successful application
  startup and checks mode on both success paths. Bus recovery now runs only after
  an application read fails. See `docs/POGO_STARTUP_REPAIR.md` for validation.
  Test 046 (`reference/boot-tests/test-046-20260922T055740Z/`) booted that
  candidate and returned safely to TWRP. The owner saw the console, but version
  exchange timed out (-110), GO was refused, and the application still NAKed
  after reset. The version error did not identify a transfer stage. Stock's
  `stm32_sysboot_connect()` then revealed a missing STEP3: after probing with
  unknown command 0xFF it resets into the bootloader again, without another
  probe, before issuing commands. The follow-up candidate now mirrors that
  sequence, tested against the actual GPIO/reset helper on the host.
  Test 047 (`reference/boot-tests/test-047-20260922T060344Z/`) validates that
  correction: the full version exchange returns 0x12 and both GO command/address
  ACKs succeed. Application 0x2a still NAKs after 150 ms; the fallback resets it
  and 40 further retries fail. The owner confirmed the keyboard stayed attached
  and unfolded. Pretest TWRP identifies EF-DX710, firmware 34, con:1/1, rst:0.
  Both tests returned safely to TWRP; 1d8a977 remains installed with read-back
  hashes verified. No key has been typed through mainline yet.
- **The acknowledged GO was the wrong command (2026-09-22, round 6).**  Tests 048
  and 049 settled it: no reset timing and no polling window makes the application
  answer after `GO 0x08000000`, and the READ path (now working, framed exactly like
  `stm32_sysboot_i2c_read`) shows `0x08000000` holds a Cortex-M vector table
  (SP `0x200056c0`, reset vector `0x0800c4a5`), not Samsung's `"STM32"` header -
  that header sits at offset `0xbc`/`0xc0` *inside* the image. After the GO the MCU
  answered on neither `0x2a` nor `0x51`. The vendor's own bring-up, run on every
  stock boot, never sends GO: `stm32_sysboot_mcu_validation()` enters the system
  bootloader, `stm32_sysboot_i2c_read()` takes the IC version from `0x08000200`
  (stock prints its last byte as `mcu_fw(ic):34`) and `stm32_sysboot_disconnect()`
  - BOOT0 low, one NRST pulse, 150 ms - releases the part so the application runs
  from flash. The port now does exactly that, plus stock's
  `stm32_set_mode(MODE_APP)`: a part reporting DFU mode gets the ABORT command
  (`0x17`) before it is read again. Test 050 measures it.
- **The host harness is not a compile test (2026-09-22).**  `tests/test_pogo_startup.py`
  strips forward declarations (`re.sub(r'^static [^\n]+;\n', ...)`) and mocks the
  helpers it does not extract, so it passed while the driver still called
  `pogo_recover_bus()` and `pogo_scan_bus()` after their definitions had been
  deleted. Always run `scripts/build-kernel.sh` before flashing, and treat the
  kernel build - not the harness - as the gate.
- **Display regression, found and fixed (2026-09-22, round 5).**  The owner
  reported a blank screen; `display_recover` was cycling the framebuffer as soon as
  `fb0` appeared, 5.91 s, before the panel driver's first read at 6.29 s, and had
  no retry - so test 040's working display stayed dark.  It now waits for the
  driver's own line and retries the full cycle up to three times; cycle 1 recovers
  `80 00 04` at 6.5 s and the owner confirms the console is visible again.
- **Physical tests need a recorded owner request (2026-09-22).** The test 040
  flash was made on one and tests 041-045 continued under the same recorded
  authorization, which each test's `source.txt` quotes. Do not flash, reboot or
  claim a hardware observation without a current request; ccache builds are
  always authorized. Compilation is not screen or keyboard validation.
- Next milestones: a microSD root filesystem, then the touchscreen, and the pogo
  keyboard's first run on mainline. Compilation is not screen validation.
- **The USB rescue channel works** (test 029): with `gts9_usb_gadget=msc` the
  gadget exports the microSD partition read-only, Windows mounts it by itself,
  and the report can be read off the running tablet over USB - no TWRP, no power
  button, no owner.  Bulk transfers are therefore fine; the CDC-ACM function is
  what fails (the host sees its control interface and never its data interface),
  so a serial console is a gadget-side fix rather than a PHY problem.
- Known blockers on the way: an SPMI *write* blocks this kernel uninterruptibly,
  so `reboot recovery` through the SDAM and the RTC state word are both out until
  it is understood - the BCB path (a UFS write) replaces the former.  Nothing on
  this device clears that BCB afterwards (TWRP's cmdline still said
  `androidboot.boot_recovery=1` after a `gts9-to-recovery` boot), so `/init` now
  clears a stale block on every mainline boot: one request, one boot.  Reaching
  mainline at all means the request was served, so this is safe by construction.
- USB re-enumeration is marginal: the gadget comes up on most boots, but test 035
  lost it after a DSI host rebind under a live DRM master, and Windows then
  reported a failed device-descriptor request (code 43).  Do not rebind the DSI
  host while DRM holds it; a real suspend/resume is the documented recovery for
  the panel's cold-boot state.
- The generic initramfs lives in **init_boot**, so include init_boot whenever the
  new bundle differs from the flashed version. `gts9_userspace_proof=<seconds>`
  stays an opt-in in the initramfs (it powers the tablet off by itself) and is
  deliberately absent from `boot/cmdline.example.txt`; re-add it to reproduce
  test 010.
- The owner explicitly requested flashing this candidate and collecting logs.
  This authorizes a controlled TWRP/adb test of boot, init_boot, vendor_boot and
  the documented dtbo fallback after validating the bundle, device identity,
  partition sizes, backups and per-partition write/read-back hashes. Build and
  validation scripts must remain non-flashing. Do not rewrite recovery, vbmeta,
  bootloaders, userdata or the partition table as part of these tests.
- Start log capture before reboot. Observe for 60–90 seconds, then return to
  recovery and capture immediately. If adb is absent, ask the owner for the
  physical observation/recovery key action; absence of adb is expected with
  this minimal initramfs and does not establish a crash. When a test's signal is
  a physical action (power off, reset, screen change), say so and let the owner
  watch instead of asking for a key combination.
- **Every subsequent physical test must have a committed log directory** under
  `reference/boot-tests/test-NNN-YYYYMMDDTHHMMSSZ/`, including failed or aborted
  attempts. Save raw last_kmsg, available pstore, recovery dmesg (labelled as
  recovery), device/layout checks, flash/read-back transcript, artifact hashes,
  source commit, bundle metadata and an observation/result README. Mark absent
  logs explicitly; never fabricate a successful capture or overwrite an older
  test directory. A directory containing only a summary is insufficient when
  raw logs are available. Do not commit firmware images or partition backups.
- Hash the archived evidence and commit/push it to `origin/test` after each
  test, before changing the next kernel/config/DTB. `.work` or external folders
  are staging locations, not the sole home of test evidence. The capture tool
  defaults to the tracked archive; pass CAPTURE_DIR for the specific test.
- Mainline log/marker present: follow the last proven stage and the actual
  panic/probe output. Init reached: verify persistence, then storage and USB
  rescue. Reboots without mainline evidence: validate the sec_log retention
  path and kernel handoff separately. An absent write-back marker, empty pstore
  or a compressed-file DTB offset does not prove that Linux was never entered.
- Keep experiments attributable: change one failure hypothesis per follow-up
  test. MMU-off/head.S or Gunyah watchdog instrumentation remains a separate
  diagnostic branch, not a default workaround. Record the final device state
  and any stock restoration with read-back hashes in the test record.

## Latest pogo audit (2026-09-22, after f6c5c6b)

The current candidate restores DATA to IRQ_TYPE_LEVEL_LOW: announce-gpios is
GPIO_ACTIVE_LOW, so descriptor 1 means a physical low, not a high pulse. The
normal startup now releases the protocol mutex before enabling DATA, with only
50 ms power settling and no bootloader/scan/rail cycle. A model event makes a
single version-read attempt, not a minute-long loop under that same mutex.
Previous local startup experiments remain opt-in through
`keyboard_samsung_pogo.startup_diagnostics=1`; do not enable this for normal
keyboard validation. See `docs/POGO_EVENT_STARTUP.md` for the pinned S9U source
comparison and limits. The S9U firmware-update result is not permission or proof
that X710 needs another MCU image. Host tests pass; record physical results
separately and keep pre-existing test-087 logs distinct from new tests.

## Build commands

Host regression uses `bash scripts/check-stall-offline.sh` (changed files by default).
Use `--changed --base REV` for committed changes, `--core` for unconditional core
regression, or `--full` for all tests. A clean worktree against HEAD runs no tests;
it does not establish a regression pass. Unknown dependencies select all tests.
See `docs/HOST_TEST_WORKFLOW.md` for artifact/archive triggers and exact suite
selection. `--full` remains exhaustive; run it after changing suite routing or
retiring tests. New tests default to core. Do not interpret skipped prerequisites
as successful artifact validation; use `--fail-on-skip` on the Python runner when
complete validation is required. These commands do not contact the device.

Normal build:

```bash
./scripts/fetch-mainline.sh
./scripts/build-kernel.sh
```

Clean source-level comparison:

```bash
KERNEL_CLEAN=1 ./scripts/build-kernel.sh
```

Faster compile-only iteration when modules are irrelevant:

```bash
BUILD_MODULES=0 ./scripts/build-kernel.sh
```

Audit stock evidence supplied locally:

```bash
./scripts/audit-stock.sh /path/to/stock.config /path/to/live-device-tree.dts
```

Before committing a script change, at minimum run:

```bash
for script in scripts/*.sh scripts/lib/*.sh boot/*.sh; do
    bash -n "$script"
done
```

If the build environment is available, also perform `BUILD_MODULES=0 ./scripts/build-kernel.sh`. For config/DTS/patch changes, a clean build is preferred.

## Bring-up order

Do not debug everything at once. Work in this order unless logs prove another dependency is blocking:

1. ABL accepts the Android v4 image and enters Linux.
2. persistent log / serial diagnostics survive reboot;
3. reserved-memory is safe and there are no TrustZone fatal resets;
4. UFS and/or microSD root storage;
5. USB gadget/Ethernet rescue path;
6. panel/display;
7. touch, buttons and S Pen;
8. GPU/Turnip;
9. Wi-Fi and Bluetooth;
10. audio and DSPs;
11. charging/Type-C/DisplayPort;
12. cameras, sensors and fingerprint/SPSS.

A failure before Linux entry must be debugged as an ABL/boot-image/DT selection problem. An empty pstore is not evidence of a kernel crash if the bootloader never transferred control.

## Boot architecture after the Debian userspace split (2026-09-24)

The minimal profile (`gts9_minimal_rootfs=1`) now does one thing: find the TF
card, mount it, and `switch_root` into Debian. Everything that used to happen
in the initramfs before that - panel recovery, the USB ACM gadget, the report
channels - is Debian's job:

- `boot/minimal-rootfs-init.sh` + `boot/minimal-rootfs-state.sh` write the
  persistent stage record `/var/log/gts9-minimal-last-boot` on the Debian root
  (atomic replace, `switch-root` flushed before the exec).
- `rootfs-overlay/` carries the Debian units and helpers:
  `gts9-debian-entered/basic/getty/multi-user-stage.service` continue the same
  record from systemd, `gts9-usb-acm.service` creates only `acm.usb0`,
  `gts9-panel-recover.service` runs the X710 framebuffer blank/unblank cycle,
  and the ttyGS0 drop-in auto-logs in root on that console only.
- `scripts/install-debian-rootfs.sh` installs that overlay into a mounted
  Debian root or builds `out/gts9-debian-overlay.tar` for TWRP.  Kernel
  modules and firmware live in Debian under `lib/modules/<release>` and
  `lib/firmware/`; the minimal initramfs carries neither.
- `scripts/twrp-mount-debian.sh` and `docs/TWRP_DEBIAN_RECOVERY.md` are the
  offline path: identify the ext4 partition, mount it read-only and read the
  record when the panel is black and no USB console appears.

Rules that follow from this:

- Never make USB, DRM or tty1 a dependency of the root handoff. Panel and USB
  must fail independently of each other.
- A black screen plus no COM port is not a rootfs failure verdict; read the
  persistent record first (live or from TWRP).
- Do not modify regulator/PMIC parameters without stage evidence proving that
  the card never appeared.
- Keep the boot-critical providers built in (MMC/SDHCI, ext4, RPMh, PMIC, PDC,
  clock, pinctrl); do not move Pogo or the panel to modules yet.

## Samsung ABL constraints

Keep the legacy Samsung selectors in the board DTS unless a physical test proves they are no longer required. The X710 Azkali bring-up and sibling X910 work both demonstrate that Samsung ABL can reject an otherwise valid upstream-style DTB before Linux starts. Preserve `/__symbols__` in DTBs used in experiments that exercise Samsung's DT overlay path (`DTC_FLAGS_... := -@`).

For the pinned Linux 7.2-rc3 baseline, keep `kernel/patches/0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch`: Samsung ABL expects `qcom_tzlog`, `arch_timer`, and `qcom_scm` labels in the SM8550 base tree. Re-check whether the patch is still needed whenever the upstream kernel pin changes.

The current boot-bundle script uses the safer appended-DTB fallback pattern and deliberately does not flash anything. Do not change `dtbo` strategy casually; document the reason and recovery path first.

## Working with the stock config

The owner-extracted stock 5.15.153 `.config` is the **immutable seed and evidence baseline**, but it is not assumed to map one-for-one onto Linux 7.2. It is stored as deterministic Base64/gzip parts under `reference/stock/config/`; `scripts/materialize-stock-config.sh` reconstructs the original bytes and refuses a SHA-256 mismatch.

Use the stock config to answer questions such as:

- was a hardware block enabled in Samsung's kernel?
- was a driver built-in or modular?
- what compiler/Kconfig features did stock use?

For the mainline build, reconstruct the stock config, merge `kernel/config/gts9wifi-mainline.fragment`, then run Linux 7.2 `olddefconfig`. Unknown Samsung/Android-only 5.15 symbols are expected to disappear; required upstream symbols must be asserted explicitly by the fragment/build checks. Never edit the stock seed in place. A refreshed stock extraction must be added as a new identified artifact with updated hashes.

## Patch discipline

- Prefer upstream commits/backports over local patches.
- Every local patch should have one purpose and an explanatory commit message.
- Keep device-specific quirks gated to SM-X710/SM8550 where practical.
- If a patch becomes upstream, replace the local copy on the next controlled kernel rebase.
- Do not add Android-rooting/security modifications to this repository; keep the mainline hardware port focused.
- Do not import Azkali's `c48fedbd799a` early-boot framebuffer/Gunyah watchdog instrumentation into the default patch queue. If conventional logs are unavailable, reproduce it only as a temporary diagnostic series on a dedicated branch.

## Logs to request after physical tests

Ask for the smallest useful evidence set, typically:

```bash
uname -a
cat /proc/cmdline
dmesg -T > dmesg.txt
cat /proc/iomem > iomem.txt
cat /sys/firmware/devicetree/base/model 2>/dev/null
ls -l /dev/dri /dev/mmcblk* /dev/sd* 2>/dev/null
lspci -nn 2>/dev/null
ip -br link
```

For boot failures also collect Samsung/TWRP `last_kmsg` or ramoops/pstore if available. Record the exact artifact hashes that were flashed/tested.
