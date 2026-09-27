# Test247 prospective scope: early CSD request over pseudo-NMI

One candidate startup target; total observation120 s with full source-time JSON
from first response. Stop at first failure/suspect/transport loss; at most20 s
extra collection, no target retry or intentional stall/workload. Source review:
reference/offline-reviews/20260928-early-csd-pnmi/.

Relative to246, only the existing CSD debug/default options are enabled and
csdlock_debug=1 is added as the boot identity marker. Existing0022+0024+0026,
PNMI/LA1/ECC64/loglevel5/watchdog1/1/1/10 are retained. Calibration helper absent.
Build and save exact kernel/symbols/module manifests; inspect the actual early
CSD backtrace path. Config diff must contain only the two intended options;
DTB and release unchanged. No built-in CSD-panic setting: verify timeout5000,
panic_on_ipistall0 via sysfs. GIC activation, notes and six runtime anchors,
capture ID and installed module hashes are mandatory target attribution gates.

Before any writes verify current source boot, rootfs UUID/machine ID and all
original partition/module hashes. Use reviewed TWRP module staging and paired
image/module verification before reboot. Restore original module directory
and boot/vendor_boot, verify all five original hashes and full module manifest,
and observe production120 s with ADB/NCM SSH checks. Prior known UPower failure
is a separate unresolved health issue, never reset/hidden to pass a check.

No new hardware has run at registration. The measured outcome must be appended
in RESULTS.md. A clean window is not CPU repair or a failure-rate estimate.
