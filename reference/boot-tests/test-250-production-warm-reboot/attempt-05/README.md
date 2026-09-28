# Test250 attempt 05: approved bounded QCA setup-cycle classification

The owner explicitly selected **采用有界按周期分类，重新注册20轮** after
reviewing attempt 04's first non-clean boot and the concrete proposal committed
in `e547486`. This is a fresh Test250 registration, not a resumed attempt or
Test251. All earlier sealed results, including attempt 04's four clean rounds
and fifth suspect, remain unchanged and are not counted in this series.

## Purpose and unchanged production

Execute **20 consecutive ordinary warm reboot rounds**, observing each new
boot from startup to uptime at least **150 s**, to look for CPU non-response,
panic, RCU/CSD/soft-lockup and other severe boot-stability faults on the currently
installed accepted Test249 production software. This is bounded observation,
not performance testing, a root-cause experiment or failure-rate estimation.

The sole production baseline remains Test249: pinned Linux 7.2-rc3, kernel
notes SHA-256 `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`,
complete embedded config `95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`,
five partition hashes and exact 181 module-file set/hashes from its existing
accepted manifest. HVC_DCC stays disabled; both hvc0 nodes, getty and DCC write
symbols stay absent. Temporary module backups and diagnostic profiles stay absent.

No kernel/config/DTS/DTB/modules/rootfs/services/cmdline/USB/OPP/cpufreq/cpuidle/
regulator/clock/power-domain/GPU/watchdog/panic or diagnostic setting is changed.
No build, flash, partition write or runtime repair occurs. The only device
mutation is one normal `systemctl reboot` following a clean source gate.
**Rollback is unnecessary**, since no images or configuration are written.

## Approved classification and evidence basis

Attempt 04 round 05 contained one exact priority-3
`Bluetooth: hci0: unexpected event for opcode 0xfc48` in each of two distinct
completed WCN6855 setup cycles; each completed within 0.8 s of its event. Its
first setup had no event. Raw comparison shows two or three completed cycles
in the same production's healthy boots. See the immutable attempt-04
`round-05/post-stop/setup-cycle-review.json` and `classification-proposal.json`.
Prior primary-source review identifies this opcode as QCA's baudrate command
and describes WCN6855 response handling, without proving HCI packet ordering
on this tablet. No source patch is applied and no historical CPU-cause claim
is made. Bluetooth setup/public-address provisioning/daemon startup stay intact.

`policy.json` and host-only parser now enforce precisely:

- At most **two** exact hci0/0xfc48 priority-3 events per boot.
- At most **one** event per distinct, non-overlapping WCN6855 setup cycle.
- At most **three** setup cycles; every started cycle must finish. Different
  controller/SoC, orphan completion or overlapping/restarted setup is suspect.
- All setup/event/completion source times must be ordered and within
  `0 < t <= 20 s`; each event must strictly follow its setup and strictly precede
  completion by at most **5 s**.
- A live prefix is pending only to the lesser of 20 s or event time + 5 s.
  Missing completion then stops; a pending prefix can never qualify clean.
- Same-boot read-only health must show exactly hci0, powered public controller,
  active bluetooth.service and gts9-bluetooth-address.service.
- All other Bluetooth errors remain suspects, including lower-priority errors;
  CPU faults, Code43, transport/evidence/identity failures never receive exemptions.

The attempt-04 single-event parser and all historical wedge diagnostic runner
behavior/tests remain unchanged. The inherited Test249-DTB-verified 43 MiB
startup SMMU class and source-bound Windows NCM probe remain unchanged; SMMU
messages stay counted and are not claimed repaired. Exact known aux_bridge and
regulator-ignore-unused warnings remain independently classified.

## Registration, read-only preflight and execution

Commit and push registration, policy, runner/parser and passing local tests to
`origin/test` before device work. Run:

```
scripts/production-reboot-stability.sh preflight --attempt 5
```

Save boot ID/uname/cmdline/uptime, binary build notes, complete embedded config,
five read-only partition hashes, 181 module hashes/file set and backup absence,
DCC/runtime profile, live accepted splash property, complete source kernel
JSON/text journal and boot list, failed units, Bluetooth health, Windows
ADB/PnP/NCM state, source-bound NCM SSH banner and authenticated read-only SSH
below `attempt-05/preflight/`. Windows ADB must be
`/mnt/d/android/gts9-active/platform-tools/adb.exe`.
Any identity mismatch or non-clean preflight stops without repair or reboot.
Commit and push accepted same-boot full preflight before:

```
scripts/production-reboot-stability.sh run --attempt 5
```

Each `round-01/` through `round-20/` has an independent source preflight,
before/after IDs and full boot lists, exactly one normal reboot request,
complete just-ended target journal separately attributed from the new boot,
startup-to-150-s observation, full kernel JSON/text, uname/cmdline/uptime,
systemd failed units, DCC/ADB/SSH/NCM/USB/Bluetooth health and verdict. ADB must
return within 180 s with first uptime at most 60 s. Boot ID must change and
journal history prove exactly one new boot. Five-second read-only health polls
and live full kernel follow stop faults immediately, rather than waiting out
150 s after a detected failure.

Only CLEAN authorizes the next reboot. Stop on the first CPU non-response,
soft/RCU/CSD/workqueue stall, panic/Oops/BUG/SError/hung task, unexplained reboot,
attribution gap, identity change, new severe kernel/systemd fault, incomplete
evidence, ADB/SSH failure, Code43, NCM transient or other suspect. Preserve raw
evidence and analyze offline; do not enable diagnostics, repair configuration,
loosen bounds, add a reboot or automatically start another attempt.

NCM gets at most three same-boot attempts, ten seconds apart, recording first
failure and recovery. A recovered initial failure is still usb-transient and
stops the series. Code43 stops with Windows PnP and reachable device-side
gadget/DWC3 evidence. No USB condition is attributed automatically to CPU/DCC.

## Final acceptance and report limits

Only after 20 clean attributed rounds, repeat full five-partition/181-module/
config/notes/DCC/backup identity, complete kernel journal, failed units,
Bluetooth, ADB and NCM/authenticated SSH on the last boot. Save RESULTS,
machine summary with every ID/window/verdict/transport/fault count and final
acceptance, seal hashes, commit and push to `origin/test`. Do not start or wait
for CI; `main` stays untouched. Local development uses changed-file testing;
final runner review uses all retained tests with `--fail-on-skip`.

No detected stall within registered windows is a bounded warm-reboot result,
not a future guarantee, failure-rate estimate or proof of every historic stall's
DCC cause. Cold/battery-only/Type-C power paths are not covered. Recommend a
separately registered Test251 only in RESULTS after full clean acceptance;
never create or run it here, particularly after any non-clean stop.
