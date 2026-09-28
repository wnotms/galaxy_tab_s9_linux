# Test250 attempt 03: full unchanged-production warm-reboot regression

The owner explicitly requested completion of the full test after the prior
stops. This is a new registered attempt, not continuation past the non-clean
verdict in attempt 02 and not Test251. Earlier evidence and results stay
immutable. The bounded objective remains **20 consecutive attributed ordinary
warm reboots**, every new boot observed through at least uptime **150 s**.

The installed, accepted Test249 production software remains the only baseline:
Linux 7.2-rc3, config SHA-256
`95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`,
notes `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`,
all five partition hashes and all 181 module hashes from the verified Test249
manifest. DCC nodes, getty and write symbols remain absent. No build, flash,
kernel/config/DTB/module/rootfs/service/cmdline/USB/power/GPU/watchdog/panic or
diagnostic modification is permitted. No rollback is required because the
only device-changing command is one normal `systemctl reboot` per clean gate.

Before physical testing, push this registration, runner/parser and passing
host tests to `origin/test`. Then run:

```
scripts/production-reboot-stability.sh preflight --attempt 3
# Only after accepted same-boot preflight is committed and pushed:
scripts/production-reboot-stability.sh run --attempt 3
```

The parent and attempt-02 registrations define the complete preflight,
source/new-boot separation, raw JSON/text evidence, failed-unit/CPU fault gates,
boot-ID and journal attribution, 60 s initial ADB visibility, 180 s return
limit, five-second health polls and final full acceptance requirements.
Every round has separate before/after IDs, both boot lists, uname, cmdline,
uptime, complete startup kernel journal, DCC, ADB, SSH, USB and verdict files.
Faults are parsed during observation; do not wait for 150 s after detecting one.
Progress now records the last successful poll even on early stop and separates
host termination after non-clean from completion of the registered window.

## Classification tied to accepted DTB, not sampled address bounds

The previous 2 MiB address restriction was narrower than the unchanged
production `splash_region`, directly verified in both the running device and
the hash-verified Test249 compiled DTB. Attempt 03 obtains its allowed IOVA
bounds from that accepted artifact: **`0xb8000000 <= IOVA < 0xbab00000`**.
The live DTB property is read and compared every production snapshot. Artifact
or live-property identity mismatch stops before further reboot; no DTB is edited.

All other bounds from attempt 02 stay unchanged: priority 3, source time
at most 0.200 s, FSR `0x402`, FSYNR `0x620021` or `0x630021`, context bank 9,
SID `0x1c00`, exact corresponding FSR/FSYNR messages, at most ten rows of each
type, and the single exact-shape source-time-zero register warning. Changed
syndrome/SID/bank, out-of-carveout address, late or extra error remains suspect.
No CPU-stall/panic message is suppressed. These pre-existing early SMMU errors
are counted and preserved, not claimed fixed or harmless in general.

The profile references both manifest-verified Test249 accepted journals.
Attempt 02 retains its old range when replayed. Read-only evidence explaining
the correction is in `../post-attempt02-analysis/`; old verdicts remain stopped.

## Explicit NCM socket attribution; transient rule retained

Windows SSH-banner checks bind the probe's socket to the one up production
NCM adapter's preferred APIPA IPv4 and explicitly select its outgoing interface.
The probe reports interface index, source IP, actual local/remote endpoints,
socket interface and SSH banner in JSON. This changes only that temporary
host socket, not host routes/IPs/neighbors/adapters/drivers or device settings.
The five-second connect and five-second banner deadlines stay unchanged.
Authenticated read-only SSH must independently return the target boot ID.

At most three banner attempts, ten seconds apart, may record same-boot recovery.
An initial failure remains **usb-transient/suspect**, even if it recovers; only
an entirely clean round proceeds. Code43 triggers host PnP and reachable
device evidence and stops. ADB+SSH loss, CPU non-response/lockup/RCU/CSD/panic,
extra reboot, incomplete attribution/evidence, changed identity, new severe
kernel/systemd fault or any unclassified suspect stops immediately. No
configuration repair, additional reboot or automatic new attempt follows a stop.

If all 20 rounds are clean, final acceptance repeats all five partitions, exact
config/notes, all 181 modules, DCC absence, complete journal, systemd, ADB and
attributed NCM/authenticated SSH. Results and machine summary must retain each
boot ID and actual observation duration. Only then may Test251 be suggested
for separately registered cold/power-path coverage; it must not be executed here.
This is not a failure-rate estimate or proof of future reliability/all historic
DCC causation. It covers only ordinary warm reboot.
