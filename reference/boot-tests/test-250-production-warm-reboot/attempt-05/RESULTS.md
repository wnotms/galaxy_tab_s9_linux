# Test250 attempt 05: stopped before reboot 13 on a host transport timeout

**Verdict: `stopped_on_first_non_clean`.** Twelve ordinary warm reboots were
attributed and CLEAN. Each new boot was observed from startup to more than
150 seconds. Round 13 began its source-boot preflight but the first Windows
source-bound NCM SSH banner command timed out after 20 seconds. The runner
did not issue a thirteenth reboot, did not finish the registered round-13
evidence gate, and did not perform final 20-round acceptance. The 20-round
objective remains incomplete; no Test251 was created.

## Production and registration

The owner approved a fresh attempt using the bounded per-setup-cycle QCA
classification. Registration and host tests were pushed as `e2afb31`; the
full read-only preflight was accepted and pushed as `01133ab` before the first
reboot. The prior attempts and their verdicts remain unchanged. The only
device-changing commands in this attempt were the twelve normal
`systemctl reboot` requests. No kernel/config/DTB/module/rootfs/USB or
diagnostic setting was changed, built, flashed or repaired. No rollback was
needed.

The first preflight and same-boot read-only post-stop capture both match the
accepted Test249 production baseline: Linux `7.2.0-rc3-gts9wifi-dirty`, build
notes SHA-256 `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`,
complete embedded config SHA-256
`95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`,
all five boot/vendor_boot/init_boot/dtbo/vbmeta hashes and the exact 181
production module files and hashes. DCC config, nodes, getty and write
symbols and temporary backup modules remain absent. The accepted cmdline,
runtime profile and live splash-region property remain unchanged. Full raw
captures are in `preflight/` and `round-13/post-stop/`; accepted expected
partition values are in `preflight/summary.json` and Test249's manifest.

## Attributed rounds

Every CLEAN round has a changed boot ID, an exact one-boot journal-history
transition, its own source and just-ended target journals, complete new-boot
kernel JSON/text and source timestamps, live health polls, final identity,
Bluetooth health and ADB/Windows NCM/authenticated SSH evidence. No measured
transport gate in these twelve rounds reported Code43 or an initial NCM
failure. Known aux_bridge/regulator warnings and bounded existing startup
SMMU classes were retained as independent warnings, not claimed repaired.

| Round | New boot ID | Observed uptime (s) | QCA `0xfc48` count | Verdict |
| --- | --- | ---: | ---: | --- |
| 01 | `0d3543aa73f4484ba7bacd3dc9057d44` | 150.33 | 0 | clean |
| 02 | `c819d52864fb49fdb48f8b7580d16482` | 150.15 | 0 | clean |
| 03 | `e8ff94a52e6a4c129ffc5766fbc9c8a5` | 150.36 | 0 | clean |
| 04 | `af99164be4da495a94277ca637962d0d` | 151.02 | 0 | clean |
| 05 | `926c2310a92c435e8b3c63f64f6a7b03` | 151.25 | 1 | clean |
| 06 | `6bf45166665a48da8b02788655e181ca` | 150.70 | 2 | clean |
| 07 | `2533bcb3cb244abdbbc9a78e9638b473` | 150.85 | 1 | clean |
| 08 | `4ff2a339ac684862992e6db0fbcf07fd` | 150.94 | 1 | clean |
| 09 | `bc4e2ffa015547f1aedbeea7d4308780` | 150.21 | 0 | clean |
| 10 | `228f72d1e89c4d9aa9c81e971eb87bd8` | 150.15 | 1 | clean |
| 11 | `d85d14df71be480487f15016fe52b054` | 150.38 | 0 | clean |
| 12 | `a48bfed924f64996833e789baf2ab011` | 150.55 | 2 | clean |

The two-event boots each had at most one exact priority-3 hci0/0xfc48 message
per distinct, completed WCN6855 setup cycle and passed every registered
same-boot controller/unit, timing and fault gate. The captured source,
ended-target and new-boot journals for these twelve rounds contain no
detected CPU non-response, soft/RCU/CSD/workqueue lockup, panic, Oops, BUG,
SError or hung-task signature. `summary.json` and `EVIDENCE_AUDIT.json` hold
the complete boot chain, exact observation times, transport and fault counts.

## First non-clean condition

Round 13 started at 2026-09-28 07:05:42 UTC on boot
`a48bfed924f64996833e789baf2ab011`. Its read-only production identity,
source journal and Windows PnP checks succeeded. Windows reported the USB
composite, ADB and NCM devices as OK with problem code 0 and the NCM adapter
Up. The first source-bound SSH-banner PowerShell command started at
07:05:48.850 UTC, exceeded its 20-second host deadline and wrote zero
stdout bytes (`status: timeout`). Its stderr was empty. The runner process
ended before the planned bounded retries or authenticated SSH call, so the
source transport gate was incomplete. `round-13/verdict-interrupted.json`
retains its original `in_progress` record; `round-13/verdict.json` records
the terminal `suspect` assessment. No `reboot-request.command.json` exists
for round 13.

Read-only capture at `round-13/post-stop/` showed the same boot ID still last
in persistent journal history, exact Test249 production identity and all
181 modules, DCC absent, no failed systemd units, powered hci0 and both
Bluetooth units active. Its full kernel journal had no detected CPU fault or
new suspect. ADB, source-bound Windows NCM SSH banner and authenticated SSH
succeeded on their first post-stop attempt. Three further repetitions of the
same Windows banner probe succeeded and are retained in
`round-13/post-stop/host-probe-review/`.

The first 20-second timeout is a **host observation/transport failure** under
the registered stop rule. The captured command has no internal stage trace,
so it does not show whether PowerShell startup, adapter lookup, TCP connect
or banner read consumed the deadline. Later success cannot turn this source
gate into CLEAN, prove continuous NCM availability or establish a CPU wedge.
It is not classified as a demonstrated TCP failure or Windows Code43.

## Verification and disposition

Before device work, 68 focused tests and the full 1,052 retained host tests
passed with zero failures, errors or skips; the changed workflow also passed
1,052 tests. See `HOST_VALIDATION.json` and `host-all-report.json`.
`audit-evidence.py` independently replays all twelve raw source/ended/new
journals, exact boot-list transitions, actual reboot commands, 150-second
windows, identities, transports and the round-13 no-reboot stop; its executed
result is `EVIDENCE_AUDIT.json`. Historical attempt seals and this attempt's
pushed preflight seal were rechecked. No GitHub Actions was launched or
awaited; `main` was left unchanged.

The series remains stopped on the first non-clean condition. A fresh series
would require a new registration and explicit owner decision about the host
transport probe; this attempt cannot be resumed or counted as 20 clean.
No Test251 is authorized by this result. These twelve bounded warm-reboot
observations are not a failure-rate estimate, future-stall guarantee or proof
that all historical CPU wedges shared the DCC cause. Cold boot,
battery-only boot and Type-C power transitions were not tested.
