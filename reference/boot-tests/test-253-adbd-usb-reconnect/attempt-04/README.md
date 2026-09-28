# Test253 attempt04 proposal: observed cable recovery

Status: proposed, not owner-adopted; no physical action may run yet. The owner's
ongoing ADB repair request authorizes source review, host code/tests and read-only
preflight. Root Test253 registration prohibits changing policy to get a pass; the
one new bounded daemon-warning classification below requires an explicit owner
decision before fresh hardware testing. Attempt03 remains stopped and unaccepted.

Keep the exact installed Test252 Stage1 kernel/config/DTB/modules/partitions and
Test253 daemon/launcher/service, boot461c1408e42643afae5b48162771d077 PID834. No
device file/config change, flash, daemon/gadget/controller restart, normal reboot,
host ADB restart/backend change or charging extension. Retain the hash-pinned
UPower classification only; Test252 remains stopped and Stage2/3 do not start.
ADB tools stay D:\android\platform-tools\adb.exe37.0.1/LIBADBUSB.

Before asking for a cycle, pass full read-only config/notes/five partitions/181
candidate plus181 original module/protected settings/DCC/failed-unit/kernel and
ADB/NCM/Wi-Fi checks. Native1MiB roundtrip evidence from attempt03 is the same
boot/daemon/software prerequisite, preserved rather than called new evidence.
Commit/push adoption/preflight/tests before any new physical action.

Fresh series: three owner-operated computer USB unplug>=10s/replug cycles;
instruct20s to allow conservative command-sampling uncertainty. Wi-Fi stays up,
charger stays disconnected, no reboot. This starts new cycle01 and does not count
the earlier unaccepted cycle. Detect physical absence from USB supply offline
and Windows native-ADB absence together. Record UDC state but do not require it
to become unconfigured. Require an observed offline lower bound>=10s.

After return, real native USB shell and authenticated NCM SSH plus a source-bound
banner must complete<=60s measured conservatively from the START of the last
confirmed offline command. No invented delay subtraction. Then observe>=150s
elapsed after both transports recover, continuously capturing Wi-Fi kernel/adbd
journals and checking native shell plus both SSH paths. Stop on first new fault,
Code43, identity change, evidence loss, missing recovery/window or extra cable
transition. After each window require the read-only post-cycle exact identity/
failed-unit/transport gate before the next owner action. Runner enforces prior
cycle acceptance and refuses any series containing a cycle failure.json.

Proposed narrow classification: at most one exact
`received FUNCTIONFS_DISABLE while not enabled?` warning per physical cycle,
from the exact installed PID/binary, preceded within1s by monitor spawn and
DISABLE on that monitor TID, followed<=5s by ENABLE and<=1s by worker spawn.
The real shell/NCM recovery, full kernel/fault/identity gates remain mandatory.
Warning source time must lie between the last connected sample and the first
return sample plus5s; journal timestamps must be ordered. Other/duplicate
warnings, missing context or missing completion stop. AOSP
severity is parsed from MESSAGE: journald PRIORITY=6 does not hide W/E/F.
This source-derived classification is a proposal, not retroactive attempt03
acceptance or proof that all queued-event behavior is harmless.

Runner: `python3 scripts/adbd-cable-observer.py --registration <this>/policy.json
--cycle-dir <this>/cycle-01`. It rejects an unadopted plan before device access,
uses single-use folders and does not install/modify/restart anything.

Final full gate repeats all five partitions, embedded config/notes,181+181
module hashes, DCC absence, complete kernel/adbd journals, systemd failures,
exact daemon/PID and protected NCM/SSH/gadget/guard/holder files, ADB and both
SSH paths. Archive results/summary/seals and update AGENT, push origin/test;
no CI/main merge. Results remain bounded cable-path observations, not all USB
failure modes or long-term reliability. Root raw `adb reconnect` incident and
Test252 stopped battery attempt stay unresolved/preserved.
