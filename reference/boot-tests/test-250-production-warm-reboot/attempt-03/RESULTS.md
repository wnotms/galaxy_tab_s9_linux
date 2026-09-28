# Test250 attempt 03: first warm reboot stopped on a Bluetooth suspect

**One ordinary warm reboot was issued. Round 01 stopped as `suspect`;
round 02 was not started and zero rounds were clean.** The registered 150 s
window did not complete. The series remains stopped; no final acceptance or
20-round regression pass is claimed.

Registration, host runner review (1,018 tests, no skips) and accepted preflight
were pushed before the physical reboot: registration `79c0fbf`, preflight
`a93d927`. All device configuration stayed at accepted Test249 production.
No kernel/config/DTB/modules/rootfs/service/cmdline/USB/power/watchdog/panic
setting was changed; nothing was built or flashed and no rollback is required.
The original and attempt-02 stops remain immutable.

## Attribution and first stop

| Item | Result |
| --- | --- |
| Source boot | `188fd5c9-14ca-4818-9ded-e96669a9c836` |
| New boot | `830da717-5e6d-40be-8390-7398b55ff2e2` |
| Reboot request | 2026-09-28 05:05:18.696 UTC |
| First new-boot ADB response | Uptime 9.44 s |
| Last successful registered health poll | Uptime 21.30 s |
| Minimum registered window | 150 s; incomplete |
| First suspect | `Bluetooth: hci0: unexpected event for opcode 0xfc48` |
| Suspect kernel source time | 8.365905 s; priority 3 |
| Verdict | `suspect`; stop on first non-clean |

The boot lists prove exactly one new boot after the source, with no unexplained
intervening boot. The ended target's complete kernel JSON/text is kept separately
from the new boot's complete journal and live-follow stream. Both raw journal
JSON and text, source timestamps, IDs, command records and host/device transport
records are preserved in `round-01/`.

The production-DTB-backed startup gate recognized the ten early SMMU messages
within the unchanged 43 MiB splash carveout, their exact syndrome/bank/SID and
startup count/time bounds. These existing SMMU errors are retained and counted,
not declared repaired. The one unclassified Bluetooth event triggered the stop.
No CPU non-response, soft/hard lockup, RCU/CSD stall, panic, Oops/BUG, SError,
hung task or workqueue-lockup signature was detected in the captured journals.
This absence does not convert an incomplete suspect round into clean.

The live follow exited with host SIGTERM (`-15`) during stop cleanup. Its
metadata explicitly says `host_stopped_on_non_clean: true` and
`registered_window_completed: false`; the runner's broad
`new boot kernel fault during observation` exception denotes a classification
stop here, not proof of CPU failure. The original `verdict.json` is unchanged.

## Read-only follow-up on the same boot

Post-stop capture at uptime 124.79 s confirmed exact embedded config and kernel
notes, all five Test249 partition hashes and all 181 production module hashes,
no temporary module backup directory, DCC nodes/getty/write-symbol absence,
unchanged production profile and no failed systemd unit. ADB, source-bound
Windows NCM banner and authenticated SSH all passed on their first attempts;
no Code43 or NCM transient was observed in this capture. All returned the same
new boot ID. These are supplemental results, not a resumed registered window
or final series acceptance.

A later read-only check at uptime 404.20 s still found that same boot responsive
and its Bluetooth controller powered. Both Bluetooth units were active; firmware
setup completed after the error. The latest complete kernel capture contains
1,106 rows with a source-time-zero Linux-version row, only the same Bluetooth
suspect and no detected CPU-stall/panic signature. Current state and parsed
findings are stored under `round-01/offline-analysis/`.

## Bluetooth analysis and limits

The pinned upstream HCI event handlers emit this error when request completion
leaves `HCI_CMD_PENDING` set. `hci_req_cmd_complete()` returns without clearing
that flag when the received opcode does not match the last sent command. The
captured event is consistent with a command/event mismatch; it is not a kernel
panic path or evidence of CPU non-response. Source excerpts, file hashes and the
checkout commit are recorded in `bluetooth-analysis.json`.

The exact message also exists in retained Test241 and Test247 captures. Those
historical profiles are not the accepted Test249 baseline; neither accepted
Test249 capture contains this event. The controller's subsequent readiness does
not establish its packet ordering, cause or harmlessness under every boot.
No HCI packet trace was collected, and opcode `0xfc48` is not documented by the
pinned QCA driver source searched here. Do not invent a vendor command meaning,
attribute it to the DCC stall or add a blanket Bluetooth error exemption.

## Disposition and validation

Keep production unchanged and retain the first non-clean boot evidence. Do not
restart this series, widen its gate after the stop, enable old diagnostics or
create Test251. Further diagnosis must start from this Bluetooth evidence and
the unchanged production baseline. A separate explicit registration is needed
before any later hardware series; no additional reboot was issued here.

`summary.json` records one attempted round (`completed_rounds` is the runner's
attempted-round count), zero fully observed/clean rounds, exact boot IDs,
21.30 s observation, unchanged production identity, CPU signature counts and
supplemental ADB/NCM/SSH/DCC state. `SHA256.json` seals all files in this attempt,
including the previously pushed preflight; older attempt seals are checked
separately. The final record contains host validation details in
`host-validation.json`.

This bounded observation covers an ordinary warm reboot only. It is not a
failure-rate estimate, a long-term reliability proof or evidence that all
historical CPU stalls had the Test247 DCC cause. Cold boot, battery-only boot
and Type-C power transitions were not tested.
