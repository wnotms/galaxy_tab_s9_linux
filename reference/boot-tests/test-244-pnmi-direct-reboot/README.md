# Test 244: one direct Debian reboot with the minimal pseudo-NMI observer

Prospective follow-up to completed test243; this is a distinct entry path.
Test234's normal direct Debian reboot produced observer
4c78d2cc-7ed8-4a33-be1c-05c2345f77c5 with positive CPU5 non-response in its
later-retrieved journal. Test243's TWRP-to-Debian entry did not reproduce the
fault. This does not prove reboot-path causality or a rate difference. It
justifies one direct-transition capture with the now-calibrated NMI route.

Reuse the currently installed exact test243 profile: no kernel, DTB, power,
clock, rootfs, helper, recorder or USB changes; no flash before this target.
First require the current target's fresh identity/profile/notes and clean
kernel journal, then sync and request exactly one plain systemctl reboot.
Never use reboot recovery. Save the current boot list and require the new
target to be the immediate retained successor by immutable IDs.

Budget: ONE direct-reboot target, observe up to 300 seconds of its uptime.
The poll, full target identity/notes/six anchors, marker and JSON follower
start automatically in sequence to reduce early-boot collection delay.
Verify inactive recorder/helper, active pseudo-NMI, ECC64, 1/1/1/10 and 5/4
console thresholds independently; do not inherit the predecessor's offset.
Write one priority-0 attribution marker and follow all current-boot kernel
JSON records, preserving source timestamps. No synthetic stall, backtrace,
workload, hotplug, panic or further reboot trial is allowed in this budget.

Stop at first positive failure, suspect timeout, profile/identity/transport
loss or unexpected boot. Allow 20 seconds for a detected failure's target
stack before collecting final evidence. If automatic recovery occurs, retain
source/observer identity and two raw pstore reads/device hash before TWRP;
require the failed target's unique marker and explicit integrity limits.
Never decode with observer offsets or turn a missing response into a causal
claim. If software recovery cannot respond, request owner TWRP action.

If clean, conclude only that this bounded target did not reproduce the fault.
Do not extend or add targets. Restore original boot/vendor_boot after this
shared session and verify all five hashes, then a separate >=150-second
production boot and ADB/NCM SSH banner. That restoration also closes test243.
Deferring rollback avoids unrelated boots and four redundant partition writes;
all original backups/hash identities remain those already verified in test243.
