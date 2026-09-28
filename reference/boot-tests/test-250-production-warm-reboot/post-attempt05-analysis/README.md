# Read-only review after attempt 05's host probe timeout

Attempt 05 remains stopped. Its first non-clean condition occurred before
round 13 issued any reboot: the Windows PowerShell process for the source-bound
NCM SSH banner reached the host's 20 s deadline with no stdout or stderr.
The current boot ID and journal history did not change. Full read-only
post-stop Test249 identity passed and the same exact probe subsequently
succeeded four times, once during full capture and three times independently.
No Code43, new kernel fault or failed systemd unit was detected in the
captured evidence. The stopped round is **not** reclassified CLEAN.

`analysis.json` independently measures every saved successful Windows
source-bound banner command in this attempt: 29 completed in 2.104–2.520 s,
with a median of 2.179 s. The one failed command ran for 20.025 s and was
terminated by the host deadline. Windows PnP showed the composite/ADB/NCM
functions as OK with problem code 0 and the adapter Up just before it.
This large timing outlier is consistent with a host observer stall, but the
current capture has no internal stage timestamps. It cannot distinguish slow
PowerShell startup or adapter lookup from an actual TCP connect or banner-read
stall, nor prove continuous NCM availability.

## Concrete, unapproved next registration

If the owner authorizes a **fresh** Test250 attempt 06, change only the host
probe implementation and register a new 20-round series:

1. Keep the accepted Test249 production kernel, DTB, config, modules, cmdline,
   rootfs services and USB gadget untouched. Keep exact production preflight,
   20 ordinary warm reboots, unique boot attribution, 150 s per new boot,
   original CPU/USB/identity/fault and first-non-clean gates, and the approved
   bounded per-setup-cycle QCA rule. Do not count attempt 05's twelve rounds.
2. Emit flushed PowerShell stderr stage markers and elapsed times for process
   start, NCM adapter lookup, preferred source IPv4 lookup, bound socket,
   TCP connect and SSH banner read. `Recorder` already preserves partial
   stderr on timeout. Keep the existing **5 s TCP connect** and **5 s banner
   read** deadlines and exact source-interface/bound-socket checks.
3. Raise only the *outer PowerShell process* deadline from 20 to **30 s** for
   attempt 06. A bounded host startup or adapter-query delay would then be
   measured instead of necessarily becoming a false NCM failure. A failed
   internal TCP or read deadline, an outer timeout, Code43, failed SSH or any
   first transport failure remains non-clean and stops the new series, even
   if a same-boot retry later succeeds. The longer outer deadline does not
   extend the 5 s network deadlines or the 150 s device observation window.
4. Test stage-capture behavior for a simulated host timeout, wrong NCM
   interface, TCP timeout, invalid banner and first-failure-then-recovery;
   confirm all remain non-clean except fully successful first probes. Push
   the registration and tests, run full read-only preflight and push it before
   the first physical reboot. Stop on the first non-clean round as before.

This is a proposal only: no attempt 06 code, registration, preflight or reboot
has been executed. The owner must decide whether changing the host process
deadline is acceptable. Test251 is not created.
