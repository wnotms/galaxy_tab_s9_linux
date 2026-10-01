# Test267 — physical attempt stopped; exact Test263 restored

The qualified Test266 kernel was installed with181 exactly paired module files,
boot readback b9f296d8 and unchanged vendor_boot/init_boot/dtbo/vbmeta. One new
Debian candidate boot0fb695fd reached ADB at10.95s; resolved config f289 and
kernel notes f007 match the candidate. Journal history attributes its preceding
Debian boot753b5cf5 and the later recovery/rollback separately. No PPS or pump
activation, current increase, protection/thermal/USB/rootfs change occurred.

**Physical acceptance did not pass.** The original observer stopped before the
registered30-second sample window, at its wrong cmdline comparison. The package
contains only vendor cmdline; ABL adds the stable Samsung suffix at runtime.
The actual complete runtime equals accepted Test263 exactly, and candidate
config/notes match. Original script/STOP/raw evidence remain untouched. This is
an observer defect, not a software identity change; independently comparing the
accepted runtime also rejects a panic=10 mutation. Future runners must compare
full runtime and package vendor inputs at their respective boundaries.

First-failure capture independently proved a device-side passive monitor fault:
source0.278016s, bitmap0x80, mode01/01 OFF, VBUS4.964V, VBAT4.3055V, IBUS0,
die23.0C. The unchanged sm5440_passive_pc_sample()/startup classifier requires
VBAT<4.3V, so this full-pack sample is outside its narrow confirmation range.
No startup-awaiting/two-confirmation exemption was granted. Cached snapshot
fault=1 and stale data/Unspecified failure were retained; no fault clearing,
retry, gate broadening or driver modification was performed. Gauge battery
health was Good, pack29.2C and SOC99; switching input remained SDP500mA.
These facts do not independently calibrate ADC or prove reverse-current safety.

The preboot INSTALL_STATUS source review already warned that full-pack
REVBLK could be refused. Registering a passive snapshot ceiling of4.44V did not
alter or satisfy the driver's separate startup eligibility condition. Future
entry planning must account for that existing limit before installing another
passive candidate. This result cannot qualify full-pack monitor behavior or
active direct charging.

Per registered first-device-fault stop, BCB requested verified SM-X710 TWRP,
then exact Test263 boot cc31efa0 and181 original modules were restored and
readback verified. All five partitions match accepted Test263. Candidate modules
remain in .gts9-test267-tested; Test263/Test260 and older rollback directories
remain intact. Root unmounted, BCB cleared, one ordinary baseline boot4bbd8221
returned to Debian with exact Test263 config/kernel notes and unchanged cmdline.
ADB, authenticated NCM SSH and Wi-Fi SSH10.168.36.149 pass; no Windows Code43
or failed systemd unit was recorded. Battery health remains Good. Baseline also
reports the same passive0x80/OFF/IBUS0 refusal, now VBAT4.3215V; passive health
remains Unspecified failure. Rollback restores known software, and is not a
claim that the full-pack passive monitor fault has been fixed.

The entire ended candidate kernel JSON (1118 messages) and restored baseline
kernel journals are archived with boot attribution. Neither scan detected
CPU-stall/panic/new severe kernel signatures. This is bounded evidence, not
reliability or reverse-current proof. Generic kernel scan and explicit SM5440
fault gate are separate; an empty CPU-fault count does not mean passive PASS.

Reused Test266 final Linux7.2-rc3/clang21 build, exact config/DTB,181-module,
85-container/DCC/96-protected-file and full1379/static qualification. Packaging
validation and42 focused host tests pass (initial test-fixture hex-width error
retained, corrected before deployment). No kernel rebuild/full rerun or CI.
Results/status-only checks executed:false for build/regression; hashes/summary
were reviewed. No successful runtime call to the new in-kernel cached API is
claimed: it has no live consumer, and this trial's purpose was boot/poller/USB
regression. No9V charging or activeStage3 test was run.

Next: offline audit the existing full-pack startup latch policy against Samsung
and Fedora, or register a fresh passive trial after discharge into the existing
range. Do not just raise the cutoff, whitelist0x80, clear the latch or retry the
failed trial. Current device stays on Test263. **ActiveStage3 NOT READY.**
