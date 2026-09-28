# Test250 attempt 02: explicitly requested production warm-reboot series

The owner requested physical testing again on 2026-09-28 after reviewing the
stopped preflight result. This is a fresh, explicitly authorized attempt of
Test250, not an automatic retry or Test251. Original registration, stopped
preflight, summary, results and hashes remain unchanged in the parent folder.
All new evidence goes into this folder and must never overwrite old captures.

The question and device variables are unchanged: can **20 ordinary warm
reboots** of the installed, accepted Test249 production expose CPU
non-response, panic, RCU/CSD/soft-lockup or other startup instability?
No kernel is built or flashed. No kernel/config/DTB/module/rootfs/service,
cmdline, power, GPU, USB, watchdog, panic or diagnostic setting is changed.
The only device-changing command is one normal `systemctl reboot` per clean
source boot. No rollback is required because no software is installed.

## Baseline and commands

The full accepted Test249 manifest remains the only software baseline:
Linux 7.2-rc3, embedded config
`95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`,
notes `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`,
all five matched partitions, all 181 matched module files, DCC absent and
production diagnostic/watchdog/panic values unchanged. The detailed identity,
transport, attribution, raw evidence, health and final acceptance requirements
in the parent registration still apply. Do not use old diagnostic arming gates.

1. Commit and push this registration, runner/parser and passing host tests.
2. Run `scripts/production-reboot-stability.sh preflight --attempt 2`.
3. Only an accepted, same-boot, clean preflight may be committed and pushed.
4. Run `scripts/production-reboot-stability.sh run --attempt 2` for exactly
   20 rounds, stopping on the first non-clean condition.

Every new boot must first respond by uptime 60 s and be observed to at least
uptime **150 s**, with source-time-zero kernel journal coverage, ongoing ADB
boot-ID polls and live fault parsing. New-boot return is bounded to 180 s.
Exactly one new journal boot must follow the source boot; the final source
shutdown journal is analyzed separately. Any CPU fault, extra boot, incomplete
attribution/evidence, identity change, failed systemd unit, transport suspect
or Windows Code43 stops further rounds immediately. Twenty clean rounds must
be followed by a full read-only partition/config/notes/181-module/journal/
DCC/ADB/NCM/authenticated-SSH final acceptance.

## Host-only warning classification correction

The original exact-message gate incorrectly treated changing data fields
within already accepted startup classes as wholly new messages. Attempt 02
uses an opt-in parser profile whose references are **both manifest-verified
Test249 accepted production captures**, not a newly diagnosed kernel or a
newly observed message added to an unrestricted allowlist.

- The exact boot-register warning shape is accepted only at source time zero,
  priority 3, once. x1 must remain `0000000080000000`, x3 must remain zero;
  only the formatted 16-hex-digit x2 data field may vary.
- SMMU messages must remain priority 3 and occur within the first **0.200 s**.
  Context faults require device `15000000.iommu`, FSR `0x402`, context bank 9,
  SID `0x1c00`, and FSYNR `0x620021` or `0x630021`, both directly present in
  accepted Test249 captures. Only IOVA varies within the same observed 2 MiB
  region, `0xb8000000 <= IOVA < 0xb8200000`.
- FSR and decoded FSYNR rows must have the exact corresponding accepted
  contents. Each of context-fault, FSR and FSYNR rows is capped at **10**;
  later, additional or different messages remain suspect, including exact old
  text appearing beyond the time/count limits.
- Raw rows are preserved and classified warning counts are reported. These
  existing SMMU errors are not claimed repaired or harmless in general.
  The correction does not suppress CPU-stall/panic signatures or new errors.

The profile is enabled only for explicit `--attempt 2`; running the original
attempt retains its conservative exact-message behavior and overwrite guard.
Host tests replay both accepted Test249 journals and the old stopped capture,
and verify that new syndromes, SIDs, banks, addresses, late/additional errors
and new CPU faults still stop.

## USB and disposition

The earlier same-boot NCM transient is preserved as non-clean. It is not
retroactively accepted or counted as a reboot round. The new preflight and
every round must still pass ADB, Windows NCM/SSH banner and authenticated
read-only SSH without an initial failure. At most three NCM attempts, 10 s
apart, are permitted to record same-boot recovery. Any initial failure is
`usb-transient` or suspect, not clean, and stops this attempt even if it
recovers. Code43 requires host PnP and reachable device-side evidence and an
immediate series stop. No USB configuration changes or automatic retry after
the first non-clean verdict are permitted.

Results and summary will state the actual completed rounds and observation
windows. A stopped preflight means zero new reboot rounds. A clean 20-round
result would be bounded warm-path observation only, not a failure-rate
estimate or proof that all historical stalls had the DCC cause. Cold boot,
battery-only and Type-C transitions are excluded. Test251 may only be proposed
after a clean final acceptance, and must not be executed here.
