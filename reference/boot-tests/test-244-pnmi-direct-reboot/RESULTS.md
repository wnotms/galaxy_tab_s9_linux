# Test 244: direct reboot did not reproduce CPU failure

One normal direct reboot from the test243 boot reached target
`fd1a8ab6-85e9-40fb-b321-207faeaaa525`, the immediate retained successor of
`2094eeee-8fe2-48e5-aea6-abbc1788ea92`. It completed **304.07 seconds** without
detected CPU/RCU/workqueue failure or suspect timeout. No stalled CPU stack
exists in this trial. This is neither repair nor a reboot-path/rate comparison.

No kernel rebuild, repackaging or initial flash occurred. Source gates checked
unchanged kernel notes/profile and clean journal before the one requested
plain systemctl reboot. Poll/preflight/capture ran automatically in sequence:
ADB answered at 9.37 seconds, full identity/marker gates completed and the live
JSON follower started by the 17.45-second sample. Source identity cannot be
substituted for target identity; the target independently matched notes and
six anchors at **+0xc8000**, differing from its predecessor's +0x188000.

Runtime pseudo-NMI/priority masking, ECC64, 1/1/1/10, console 5/4, empty
lastactivity ID and disabled/unstarted helper were verified. The one priority-0
marker binds target boot ID and notes hash. All **1,099 complete live JSON
entries** carry this boot ID and source timestamps; the final query has 1,101
entries. The marker is unique in both. The host stream ended by deliberate
host termination after the planned window. Full stdout/stderr/status and boot
history are archived; no unrecorded-boot exclusion is claimed.

The historical test234 direct-reboot failure justified this distinct entry
path, but it did not reproduce here. No synthetic CPU action, hotplug, power
change, forced panic or further target was added. A separate source review
mapped the seven strict CPU-feature warnings to SpecSEI variation, with
conservative FTR_HIGHER_SAFE policy; that explains the taint's immediate
source but establishes no CPU-stall cause. See
[SpecSEI review](../../offline-reviews/20260928-specsei-variation/README.md).

## Shared rollback for tests 243/244

BCB plus plain reboot reached TWRP. Original boot/vendor_boot were restored
from the verified backups; all five partition hashes match production.
Recovery and full readback records are under twrp-restore/ and restore/.
Final production boot
`1aaffb9a-3a07-4415-91a8-7bf40d14328e` passed **179.21 seconds** without
a detected CPU failure, with zero failed units and original watchdog/panic/
ECC zeros. The calibration helper is absent. ADB commands and four SSH/gadget
services respond, and NCM returns the SSH protocol banner; no authenticated
SSH session or long-term stability claim. This closes both tests243/244. Delaying rollback across this explicitly registered
shared session avoided four unnecessary partition writes and unrelated boots.

## Next work

No further identical clean-window boot is justified as a repair claim. Return
to the concrete known A715 BBM range defect: test240's mprotect workload proved
high-address nr=1 execution, while low-address underflush/empty-range cases
remain physically unverified. First prepare/review an isolated bounded
reproducer for the missing branch, including mapping permissions, fault
handling and exact path proof; do not change power or default kernel policy
based on these no-failure windows. Even reproducing/fixing that defect would
not by itself prove the intermittent CPU non-response has been repaired.
