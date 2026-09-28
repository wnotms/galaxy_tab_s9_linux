# Test250 attempt 02: first attributed warm reboot stopped as suspect

**One ordinary `systemctl reboot` was issued; round 01 stopped as suspect and
round 02 was not started. Zero rounds were clean.** The registered 150 s new-boot
window did not complete. No CPU-stall/panic signature was detected in the
captured kernel journals, but this is not a clean 20-round regression result.

Production kernel/config/DTB/modules/rootfs services, USB settings, cmdline,
watchdog and panic settings were unchanged. No image was built or flashed;
no rollback was needed and Test251 was not created. The explicitly requested
attempt registration and 1,013-test passing host review were pushed in
`4de53e2`; full accepted preflight was pushed in `bf5947a` before any reboot.
The stopped original attempt remains intact in the parent folder.

## Attribution and observation

| Item | Evidence |
| --- | --- |
| Source boot | `b08bbc9b-3bbf-417e-9935-619fcc5d7222` |
| New boot | `188fd5c9-14ca-4818-9ded-e96669a9c836` |
| Reboot requested | 2026-09-28 04:32:55.710 UTC |
| First new-boot ADB response | Uptime 6.30 s |
| Last successful observation poll | Uptime 20.11 s |
| Registered window | 150 s; not completed |
| Verdict | `suspect`; immediate series stop |

Both the initial and later journal boot lists contain exactly one new boot
after the source. The source's full final kernel journal has 1,100 rows and
is stored separately in `ended-target-kernel-journal-json.txt` and its text
equivalent. The new boot's full source-time-zero kernel journal has 1,092 rows;
live follow, full JSON/text, full system journal JSON and command timestamps
are retained in `round-01/`. No additional boot appeared during supplemental
capture; authenticated SSH and final ADB returned the same new boot ID.

The live parser stopped after ten early SMMU context-fault messages exceeded
the registered IOVA range. Their addresses span **`0xb82a6d00`–`0xb844da00`**,
outside the allowed `0xb8000000 <= IOVA < 0xb8200000` region. FSR `0x402`,
FSYNR `0x620021`, context bank 9, SID `0x1c00`, ten-message count and source
times **0.150874–0.151530 s** remain in the same observed early error class.
Changing IOVAs do not by themselves demonstrate CPU non-response or prove a
new SMMU root cause. The host classification boundary was not widened after
this stop and the boot was not retroactively called clean.

`runner-verdict.json` preserves the initial runner output with zero completed
window seconds. The derived `verdict.json` and `summary.json` record the actual
last successful poll, 20.11 s, and explicitly mark the 150 s window incomplete.
The live follow's SIGTERM status `-15` came from host cleanup after the suspect;
its original `host_stopped_at_window_end` flag is a cleanup flag, not evidence
that 150 s elapsed. Raw journal and command files were preserved unchanged.

## Unchanged production and independent NCM transient

The accepted preflight passed ADB, NCM banner and authenticated SSH on their
first attempts. After the stop, supplemental read-only capture at new-boot
uptime **78.62 s** again confirmed exact Test249 config/notes, all five
partition hashes, all 181 module file hashes, DCC absence, production zeros
and no systemd failed unit. This is evidence after the stop, not a resumed
registered round or final series acceptance.

During that supplemental capture, Windows NCM TCP independently failed twice
and recovered on its third bounded attempt in the same boot:

| Banner attempt | UTC start → end | Result |
| --- | --- | --- |
| 0 | 04:34:39.151 → 04:34:44.634 | TCP connect timeout, exit 1 |
| 1 | 04:34:54.635 → 04:35:00.082 | TCP connect timeout, exit 1 |
| 2 | 04:35:10.083 → 04:35:10.646 | OpenSSH banner, exit 0 |

Recovery was observed **31.495 s after the first attempt began**. ADB remained
available, UDC was configured, gadget ADB/NCM functions were linked, `usb0`
was up and sshd listened on port 22. Current Windows composite/ADB/NCM devices
had problem code zero; no Code43 was observed. Authentication over SSH
subsequently returned the same boot ID. Windows PnP, post-recovery IP/neighbor/
route state, all attempts and stderr are retained. The best-effort PnP event
query returned exit 1 with empty output; historical event completeness is not
claimed. No packet tracing was enabled, so the TCP timeout cause is unproven.

This supplemental `usb-transient` is another non-clean observation, distinct
from the IOVA gate that initially stopped the round. Neither observation is
called a CPU wedge, and recovery is not counted as clean.

## Disposition

Keep the accepted Test249 production installation unchanged. Review round 01
offline before any further physical test; do not automatically retry, broaden
the gate in this series, modify USB or enable old diagnostics. All evidence
and machine summaries are sealed by this folder's `SHA256.json`.

The result is one attributed reboot with an early suspect stop, not 20 completed
warm windows, a failure-rate estimate, a long-term reliability proof or evidence
that every historical CPU wedge shared the DCC cause. Cold boot, battery-only
and Type-C power transitions were not tested. No final acceptance is claimed.
