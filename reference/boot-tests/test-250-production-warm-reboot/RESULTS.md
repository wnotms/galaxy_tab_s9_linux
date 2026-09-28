# Test250: stopped during read-only production preflight

**No Test250 reboot was issued: 0 of 20 registered rounds were executed.**
The unchanged Test249 software identity passed, but the current boot did not
pass the registered clean gate. The series stopped before round 01. No kernel,
config, DTB, modules, rootfs, USB, watchdog or panic setting was changed;
no image was built or flashed and no rollback was required. Test251 was not
created or executed.

Registration and the independent runner were pushed to `origin/test` in
`104b5eb`, before physical testing. A DCC-output parser correction and stronger
evidence gates were validated and pushed in `f4099d8`. The final runner review
executed all **1,006 host tests**, with zero failures, errors or skips;
`HOST_VALIDATION.json` records commands, source hashes and results. No GitHub
Actions workflow was started.

## Production identity

The read-only capture at 2026-09-28 04:14:49 UTC remained on boot
`b08bbc9b-3bbf-417e-9935-619fcc5d7222`, with snapshot uptime 7,511.58 s.
This boot started before Test250; its age is not a registered Test250
observation window. Complete raw command output and statuses are in
`preflight/`. The earlier `preflight-attempt-01/` is an observer false negative:
the runner expected three DCC output lines but the empty `symbol=` marker is
a fourth line. It did not issue a reboot or establish full preflight acceptance.

- `uname`: Linux `7.2.0-rc3-gts9wifi-dirty`, production build.
- Embedded config SHA-256:
  `95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`.
- Kernel notes SHA-256:
  `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`.
- All five partition hashes exactly match Test249: boot, vendor_boot,
  init_boot, dtbo and vbmeta. Exact values are in `summary.json`.
- The full module file set and all **181** hashes exactly match the
  manifest-verified Test249 module list; no `.gts9-test*` backup directory exists.
- `CONFIG_HVC_DCC=n`; `/dev/hvc0` and `/sys/class/tty/hvc0` absent,
  hvc0 getty inactive, DCC write symbols absent. Full captured config identity
  matches; no explicit unset `HVC_DRIVER` line is required.
- Watchdog, soft watchdog, softlockup panic, panic timeout and ramoops ECC
  remain the accepted production zeros. No systemd failed unit was reported.

## Kernel journal stop and offline attribution

The complete current kernel journal contains 1,096 rows, including source-time
zero startup records. The registered parser found **no CPU-stall/panic
signature**, but flagged 21 priority-3 message variants: one boot-protocol
register warning, ten SMMU context-fault messages and ten SMMU syndrome rows.
The exact-message reference was Test249's final accepted warm boot.

Offline comparison with both manifest-verified Test249 production captures
shows that the *class* of early SMMU error is already present in accepted
Test249 boots. `preflight/offline-comparison.json` preserves the source hashes,
boot IDs, source timestamps and individual messages.

| Capture | Early SMMU context faults | FSYNR | Context bank / SID |
| --- | ---: | --- | --- |
| Test249 TWRP-entry production | 10 | `0x620021` | `9` / `0x1c00` |
| Test249 accepted warm production | 10 | `0x630021` | `9` / `0x1c00` |
| Test250 current preflight boot | 10 | `0x620021` | `9` / `0x1c00` |

All three report FSR `0x402`; their IOVA values differ. The current ten faults
occur at source times 0.141176–0.141875 s. The boot-protocol warning also exists
in both accepted Test249 captures, with differing x2 values. These comparisons
do **not** establish a new CPU fault or a new SMMU fault class, and the warning
variants must not be called proof of a recurring DCC stall. Their changing
parameters expose a limitation of the conservative exact-message gate. The
runner's allowlist was not broadened after this stop and the boot was not
retroactively marked clean.

The known unchanged `aux_bridge` deferred probe and deliberately retained
regulator warning were recognized and did not cause the stop.

## Independent same-boot NCM transient

Read-only supplemental transport capture was performed after the stop,
without restarting or reconfiguring the tablet. It independently establishes
a non-clean `usb-transient` under the registered rules:

| Windows NCM SSH-banner attempt | UTC start → end | Result |
| --- | --- | --- |
| 0 | 04:16:22.427 → 04:16:29.286 | TCP connect timeout, exit 1 |
| 1 | 04:16:39.286 → 04:16:44.740 | TCP connect timeout, exit 1 |
| 2 | 04:16:54.740 → 04:16:55.160 | OpenSSH banner, exit 0 |

Recovery was observed 32.733 s after the first attempt began, approximately
25.874 s after the first recorded failure. The device remained on the same
boot ID before and after capture. Windows ADB was available; the composite,
ADB and NCM PnP devices had problem code zero and the NCM adapter was up.
Device-side UDC was configured, `ffs.adb` and `ncm.usb0` were linked, `usb0`
was up, sshd listened on port 22 and the actual USB/ADB services were active.
The authenticated SSH read-only command returned the same boot ID.

Raw attempts, stderr, UTC command timestamps, PnP state, post-recovery Windows
IP/neighbor/routes, authenticated SSH and complete boot journal JSON are in
`preflight/supplement/`. This was a connection transient on an already aged
boot, not an observed Test250 warm-start failure. No Windows Code43 or CPU
wedge is established by it. Its cause and relationship to Test249's prior
NCM transient remain unproven. Even if the kernel warning variants were
adjudicated as known startup messages, this transport transient would still
prevent a clean preflight.

The best-effort last-30-minute Windows PnP event query returned exit 1 with
empty stdout/stderr; no event-history completeness claim is made. Current
PnP problem-code observations and all command statuses are retained. No
packet trace was enabled, so the captures do not isolate the TCP timeout cause.

## Limits and disposition

`summary.json` records zero rounds, no reboot request, matched production
identity, DCC absence, kernel parser findings and recovered transport. There
is no final acceptance because no registered reboot round completed. Raw
evidence is protected by `SHA256.json`.

Keep the accepted production installation unchanged. Review these first
non-clean preflight records before deciding on any further hardware test;
do not automatically retry the series, alter USB settings or enable historical
diagnostics. This result does not answer whether 20 production warm reboots
are stable, estimate a failure rate, prove long-term reliability, cover cold
boot/power transitions or identify the cause of every historical CPU wedge.
