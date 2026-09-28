# Test253: userspace USB ADB reconnect repair

Owner authorization2026-09-28: "先解决adb问题". This is a new independent USB
repair/test; Test252 attempt01 remains stopped on its original final USB gate.
No charging extension, Stage2 TCPM, Stage3 SM5440 or new kernel experiment is
authorized by this registration.

The kernel-side baseline is the currently installed Test252 candidate, with its
exact embedded config/notes, five partition hashes and all181 paired module
files in Test252 ARTIFACTS/attempt01 post-stop evidence. Its retained Test249
original directory has181 verified files. DCC remains absent, CPU watchdog/
panic/ECC profile unchanged and no diagnostic kernel build is made. Do not
mistake this candidate for the exact Test249 accepted production image.

First capture read-only identity, full kernel journal/source timestamps, boot
history, failed units, Windows USB/PnP, NCM/Wi-Fi shells, original daemon and
unit/helper identities, NCM config and SSH config/key hashes. The existing
native ADB offline condition is the recorded repair target, not an exemption
for any other preflight failure. Stop on identity mismatch, CPU fault, new
unclassified kernel/USB fault, Code43, failed unit or lost SSH/evidence.

Only these userspace files may change: gts9-adbd.service ExecStart routes through
the new gts9-adbd-run selector, and the exact locally built ARM64 daemon is
installed at `/usr/local/libexec/gts9-adbd-reconnect`. Preserve packaged adbd,
ExecCondition, ep0 holder, no_disconnect, gadget/configfs/NCM/SSH settings and
all kernel/charge/power settings. Verify binary hash, ELF dependencies and ABI
before installation. Save byte-exact previous userspace files for recovery.
Installation never restarts the live daemon/gadget; a continuous NCM SSH
session must survive staging with the same boot, interface and UDC binding.

Commit/push code, passing local tests and registration to origin/test first.
Then stage userspace only and issue one ordinary `systemctl reboot` to apply
the new daemon on a fresh gadget startup. No recovery argument or flash is used.
Prove the new boot ID/persistent history and exact unchanged kernel/partition/
module identity. Require the executable/hash actually running to be the patched
daemon, plus native USB shell, NCM/Wi-Fi SSH and at least150s responsive boot
observation with full kernel/adbd journals and no new fault/failed unit.

Next, while physically connected, make one bounded host ADB reconnect request
and require native shell/file transfer to recover. Keep a continuous NCM SSH
heartbeat across that daemon transport recovery; software must not unbind/reset
NCM. Record first failures, source endpoints and recovery times. Windows
PowerShell outer probes are bounded30s, with TCP connect/banner reads each5s.

Then verify three physical computer USB unplug/replug cycles. The owner unplugs
for at least10s and plugs back in when prompted. Wi-Fi stays connected; USB ADB
and NCM unavailability during actual unplug is expected. After each reconnect,
allow at most60s for enumeration/native shell recovery, then observe at least
150s on the same boot. Save ADB state and actual shell result, Windows PnP/NCM,
adbd/gadget/kernel journals and both SSH channels. No charger is attached in
these cycles. A1MiB native USB push/pull must have exact byte/hash equality.

Stop on the first non-clean phase; do not reset the controller/host driver,
restart services, retry new software variants on hardware or change policy
to get a pass. Preserve the first abnormal boot for offline analysis. If a
new userspace file must be reverted, restore its verified old bytes for the
next ordinary boot; do not bypass the live shared-gadget restart guard. The
Test249 boot/module rescue set remains available but is not deployed here.

Final read-only checks repeat all five partition hashes, embedded config/notes,
181 candidate/181 original module hashes, DCC absence, failed units and complete
kernel/adbd journals, exact patched executable and unchanged NCM/SSH config/key
hashes. Save per-phase evidence, summary/results and evidence hashes, update
AGENT and push origin/test. No GitHub Actions. Successful bounded reconnect
checks would validate this tested userspace path, not all USB failure modes or
long-term reliability, and would not retroactively pass Test252's stopped gate.
