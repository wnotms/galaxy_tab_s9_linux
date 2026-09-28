# Test250 attempt 04: approved production warm-reboot classification

The owner explicitly answered **采用** to the bounded QCA startup-event
classification proposal in `../post-attempt03-analysis/README.md`. This
registration adopts that host-only classification for a fresh Test250 attempt.
The original, attempt-02 and attempt-03 results remain stopped and immutable;
none is retrospectively counted clean. This is not Test251.

## Purpose and unchanged baseline

Complete **20 consecutive ordinary warm reboot rounds**, observing each new
boot from startup through at least **150 s**, to look for CPU non-response,
panic, RCU/CSD/soft-lockup or other severe boot-stability faults on the currently
installed, accepted Test249 production software. This is bounded observation,
not a performance test, root-cause experiment or failure-rate estimate.

Only Test249's final accepted production baseline is allowed: pinned Linux
7.2-rc3, exact embedded config SHA-256
`95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`, kernel notes
`dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`, all five
partition hashes and all 181 module files/hashes from the existing Test249
manifest. DCC config, nodes, getty and write symbols stay absent. Temporary
module backup directories must stay absent. Full integrity checks occur at
initial preflight and final acceptance; kernel/config/DCC identity is checked
every round.

No kernel/config/DTS/DTB/module/rootfs/service/cmdline/USB/OPP/cpufreq/cpuidle/
regulator/clock/power-domain/GPU/watchdog/panic or diagnostic setting is changed.
There is no new kernel build or flash. The only device-changing command is one
ordinary `systemctl reboot` after a clean source gate. **No rollback is needed**
because no images, partitions or settings are written.

The inherited Test249-DTB-backed 43 MiB startup SMMU classification and the
source-bound Windows NCM socket probe are unchanged from attempt 03. Original
SMMU errors remain counted/preserved, not claimed fixed. The sole new rule is
below; `policy.json` fixes its bounds and is checked before device access.

## Owner-approved QCA rule

Count as an independent known startup warning only one exact
`Bluetooth: hci0: unexpected event for opcode 0xfc48` row with priority 3 and
kernel source time `0 < t <= 20 s`, preceded by the same hci0 WCN6855 setup.
The same setup must complete strictly after the event and within **5 s**;
a new setup before completion, a missing/late completion, different opcode/
controller/SoC, different priority, late message or more than one event stops.
Other Bluetooth kernel errors stop even if their severity is below priority 3.

During live capture a recognized candidate can remain pending only through
that five-second source-time deadline. An incomplete pending prefix can never
satisfy a CLEAN gate. CPU faults, Code43 and other suspects still stop immediately
while it is pending; no extra 150 s wait follows a detected fault. At source,
new-boot final health and final acceptance, read-only `bluetoothctl show` and
systemd/sysfs queries must prove the same boot, exactly hci0, a powered public
controller and both Bluetooth units active. Read failures or unhealthy state stop.
This does not repair the QCA driver or prove the exact packet order/root cause.

The approved explanation/proposal and pinned source excerpts remain in
`../post-attempt03-analysis/`. No primary-source patch is applied. Raw messages,
counts, source times, completion delay and controller health are retained.

## Preflight, rounds and stop policy

Push this registration, policy, runner/parser and passing local tests to
`origin/test` before physical testing. Then execute read-only:

```
scripts/production-reboot-stability.sh preflight --attempt 4
```

Preflight captures boot ID, uname, cmdline, uptime, binary build notes, exact
embedded config, five read-only partition hashes, all 181 module hashes/file
set, backup absence, DCC absence, live DTB splash property, complete kernel
JSON/text and boot list, failed units, Bluetooth health, Windows ADB/PnP/NCM
state, source-bound SSH banner and authenticated read-only SSH. Any identity
mismatch or non-clean state stops without repair. Commit and push its accepted
same-boot evidence before the first reboot, then:

```
scripts/production-reboot-stability.sh run --attempt 4
```

Each round verifies source identity, boot ID, boot list, full source journal and
transport; issues one `systemctl reboot`; and requires a changed boot ID plus
exactly one attributable new boot. The ended target's complete kernel journal
is separate from the new boot. ADB must reappear within 180 s with first uptime
at most 60 s. Five-second read-only health polls and complete live kernel follow
observe the new boot through uptime at least 150 s. Raw full JSON/text journal,
source timestamps, before/after IDs and boot lists, uname/cmdline/uptime, failed
units, DCC/ADB/SSH/USB/Bluetooth records and `verdict.json` are separate per round.

Only a round passing all original CLEAN criteria and the approved rule enters
the next round. Stop on the first CPU non-response/lockup/RCU/CSD/panic, serious
kernel/systemd fault, unexplained reboot or attribution gap, identity mismatch,
missing/empty/incomplete evidence, ADB/SSH failure, Code43, USB transient or any
unclassified suspect. A transient NCM failure gets at most three same-boot
attempts, ten seconds apart, with first failure and recovery recorded; recovery
still does not count clean. Code43 retains Windows PnP and reachable gadget/
DWC3 evidence. Exact known aux_bridge and regulator-ignore-unused messages stay
independent warnings. Do not change configuration, enable diagnostics, issue an
extra reboot or automatically start another attempt after a stop.

## Final deliverables and limits

If all 20 rounds are clean, repeat exact kernel/config/notes, five partitions,
all 181 modules, DCC absence, no backup directory, full journal, failed units,
Bluetooth health, ADB and NCM/authenticated SSH on the final boot. Record results
and machine summary, all boot IDs/actual observation times/transport/fault counts,
and seal evidence hashes; commit and push to `origin/test`. No CI is started or
awaited. Only after successful final acceptance may RESULTS suggest a separately
registered Test251 cold/power-path regression; no such test is run here.

Report bounded warm-reboot observations without claiming all historic stalls
had the DCC cause, future stall immunity, long-term reliability or a failure
rate. This series does not cover cold boot, battery-only or Type-C power changes.
