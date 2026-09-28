# Test250 attempt 04: four clean rounds, repeated QCA event stops round 05

**Verdict: `stopped_on_first_non_clean`; the registered 20-round objective is
not complete.** Five ordinary warm reboots were issued. Four new boots passed
the registered observation and health gates; round 05 stopped as `suspect` at
the 21.37 s health poll because it contained **two** exact QCA `0xfc48` events,
exceeding the owner-approved maximum of one per boot. No sixth reboot, resumed
round, final series acceptance or Test251 was performed. No CPU-stall/panic
signature was detected in the captured source, ended-target or new-boot journals.

The original and attempts 02/03 remain stopped and unchanged. Their rounds are
not combined with these four clean rounds or retrospectively reclassified.

## Registered policy and chronology

The owner adopted the precisely bounded proposal with “采用”. Attempt 04 kept
20 consecutive ordinary warm reboots, each new boot observed from startup to
uptime at least 150 s, exact Test249 production identity and first-non-clean
stopping. `README.md` and `policy.json` were pushed in `86952b7`. A host-only
registration check initially compared README with the wrong remote path;
it stopped before device access or preflight creation, with zero reboots.
`fa7c913` fixed the comparison to each file's own remote blob and passed local
validation before physical work. The accepted full read-only preflight was
pushed in `c0523c2` before the first reboot.

Physical reboot requests were 2026-09-28 05:43:40–05:56:12 UTC
(13:43:40–13:56:12 Asia/Shanghai). Every source gate passed before its one
`systemctl reboot`. Boot IDs and journal histories prove exactly one new boot
per request; SSH disconnection is not used as reboot proof. The final suspect
verdict was written at 05:56:55 UTC. Source-boot journal, just-ended target
journal and new-boot journal are captured separately for every round.

## Per-round evidence

IDs below are journal-form boot IDs. The source of round 01 was
`830da7175e6d40be83907398b55ff2e2`; each later source is the preceding row's new ID.
“Observed to” means actual new-boot uptime at the last successful health poll,
not host time since ADB first appeared. Startup records and kernel source
timestamps are retained in full raw JSON and monotonic text journals.

| Round | New boot ID | Observed to (s) | Exact QCA events | Verdict |
| --- | --- | ---: | ---: | --- |
| 01 | `c6f88ac95b164471b23c90493044c495` | 153.71 | 1 | clean |
| 02 | `33faa528758a47f9abdaa5e3f90c186d` | 153.98 | 1 | clean |
| 03 | `19291e98e658442781f58869bacce5e4` | 154.04 | 1 | clean |
| 04 | `1a46b6c7d8d14db782bc4f7676d644ca` | 153.51 | 0 | clean |
| 05 | `457ecc1a5d904d6f8c5fad67e069bef3` | 21.37 | 2 | suspect; stopped |

Rounds 01–04 passed unchanged kernel/config/build notes, DCC absence, no failed
units, powered same-boot hci0 with both Bluetooth units active, Windows ADB,
source-bound NCM SSH banner and authenticated SSH. Their one-event recovery
delays were 0.798011, 0.781810 and 0.824020 s; round 04 had no event. All measured
transport gates succeeded on their first attempt, with no observed Code43 or
NCM transient. This describes those measured calls, not continuous network
availability. Known aux_bridge/regulator warnings and registered startup SMMU
variants remained separate and counted; the underlying SMMU messages are not
claimed repaired.

The runner's legacy `completed_rounds` field counts five terminated attempts.
`attempted_rounds: 5`, `fully_observed_rounds: 4`, `clean_rounds: 4` and
`registered_window_completed: false` for round 05 disambiguate the result.
No five-clean or 20-clean result is asserted.

## First non-clean boot and read-only analysis

Round 05's full raw journal has two priority-3 rows with the identical message
`Bluetooth: hci0: unexpected event for opcode 0xfc48`. They occur in two
distinct WCN6855 setup cycles:

| Event | Preceding setup (s) | Event (s) | Following UART setup complete (s) | Delay (s) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 5.260132 | 5.341435 | 6.135215 | 0.793780 |
| 2 | 8.457357 | 8.536921 | 9.334439 | 0.797518 |

Both individually satisfy the early-message shape and setup deadline, but
**the boot-level count of two violates `policy.json`'s maximum of one**. The
parser correctly retained both as suspects; the live follow was deliberately
terminated by the host on that non-clean condition (`status: -15`,
`host_stopped_on_non_clean: true`), rather than lost to a device crash. Only two
health polls completed; this round did not reach its registered 150 s window.
The generic exception text `new boot kernel fault during observation` means
a gate stopped: actual `kernel_fault_counts` are empty and the two structured
`kernel_suspects` are the reason. It is not a demonstrated CPU wedge.

`round-05/post-stop/` contains a separate, read-only full identity/transport
capture on the same boot (identity uptime 105.72 s; Bluetooth query 106.51 s),
full kernel JSON/text, full system journal JSON, Windows PnP/device state and
the two-event timing analysis. hci0 was powered, both Bluetooth units active,
with no failed unit; ADB, bound NCM and authenticated SSH passed immediately.
No additional reboot is present in the final journal history. The captured
kernel journals contain no detected CPU non-response, soft/RCU/CSD/workqueue
lockup, panic, Oops, BUG, SError or hung-task signature.

Required common round filenames missing after the early stop are raw byte
aliases of these supplemental captures; `round-05/POST_STOP_ALIASES.json`
identifies each source, hash and original command timestamp. Original live
progress, follow metadata and suspect verdict remain unchanged. Post-stop
health does not resume the registered window or make the round clean.

The prior primary-source review identifies `0xfc48` as QCA's baudrate command
and describes the WCN6855 response-handling issue (see
`../post-attempt03-analysis/`). These two completed setup cycles strengthen
that explanation, without HCI packet evidence proving packet ordering or
causality. No source patch or new diagnostic instrumentation was applied.
No claim links these events to historical CPU wedges.

`round-05/post-stop/setup-cycle-review.json` compares both accepted Test249
boots, this attempt's source boot and all five new boots. Test249 has two
completed setup cycles per sampled boot; this attempt already has two or three
cycles in its healthy boots. Round 05's first setup has no event, and each of
its second and third setups has one. Its full system journal orders the
public-address helper before bluetooth.service and the final setup after the
daemon starts, consistent with the provisioning/startup explanation. Journal
receipt times and kernel source times are stored separately; no HCI packet
trace proves the cause, and repository helper code is not a new measurement
of installed rootfs file identity.

A concrete **unapproved** host-only proposal is saved in
`round-05/post-stop/classification-proposal.json`: at most two exact events per
boot, at most one per distinct non-overlapping WCN6855 setup cycle, at most
three completed cycles, with events and completions within the first 20 s,
event-to-completion at most 5 s, and the existing powered-controller/unit and
all CPU/USB/identity/20-round/150-second gates retained. Extra, incomplete or
different errors would still stop. This narrower cycle-aware proposal explains
the observed variation without unlimited count acceptance. It is not a policy
change: implementation, new registration and physical testing require the
owner's explicit decision. No old verdict would be rewritten.

## Production integrity

Initial preflight and full post-stop captures both match the existing accepted
Test249 manifest `ed9a7b8544215662ebe7d800316b4952902fd0e1684b16528469a57758af87d4`:

- Linux `7.2.0-rc3-gts9wifi-dirty`; build notes SHA-256
  `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`.
- Full embedded config SHA-256
  `95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`;
  `CONFIG_HVC_DCC=n`, no hvc0 nodes/getty/write symbols.
- All five boot/vendor_boot/init_boot/dtbo/vbmeta hashes match; all **181**
  production module files and hashes match, with temporary backups absent.
- Live accepted 43 MiB splash property and production cmdline match;
  watchdog/soft_watchdog/softlockup_panic/panic/ramoops-ECC remain zero.

Exact partition values are in `preflight/summary.json` and both full raw
identity captures. The Test249 kernel/config/DTS/DTB/modules/rootfs services,
USB gadget, OPP/power/clock/GPU and diagnostic settings were unchanged. No
build, flash, partition write, runtime repair or rollback occurred. The
post-stop integrity check is supplemental evidence, **not** a final acceptance
of an uncompleted 20-round series.

## Local verification and disposition

Before physical testing, all 50 focused host tests and the retained **1,034**
tests passed, with zero failures/errors/skips, using both the required changed
workflow and final `all --fail-on-skip` runner review. See
`HOST_REGISTRATION_GATE_REVIEW.json` and `host-registration-gate-report.json`.
The earlier 1,033-test registration report is retained as historical evidence.
`audit-evidence.py` replays the actual captures entirely offline, checking the
six-ID chain, five normal reboot requests, source/ended/new journal attribution,
four completed windows, transport and identity, the exact round-05 stop and
unchanged historical/preflight seals. Its executed result is
`EVIDENCE_AUDIT.json`; final result-change host validation is recorded separately.

The series remains stopped. Any decision to change the boot-level QCA bound
requires explicit owner resolution and fresh registration before hardware work;
this stopped attempt is never resumed or reclassified. Do not create Test251.
The full 20-round goal remains outstanding.

These are bounded observations of the warm-reboot path, not a failure-rate
estimate, long-term reliability proof, future-stall guarantee or evidence that
all historical stalls shared the DCC cause. Cold boot, battery-only operation
and Type-C power transitions were not tested. No GitHub Actions was launched
or awaited, and `main` was left unchanged.
