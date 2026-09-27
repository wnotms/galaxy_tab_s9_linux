# Test245: one corrected-BBM low-address coverage target

Pre-registered scope, 2026-09-28. Reuse exact test240 kernel/bundle and symbols
(0022+0024+0026), no build, power/USB/rootfs or default changes. Test240 covered
high addresses only; use the reviewed helper in
`reference/offline-reviews/20260928-bbm-low-address/`. No unpatched low-address
trial or execute-permission fault injection. CPU-stall causality stays OPEN.

Budget: ONE candidate boot. Archive fresh original identity/journal, verify
TWRP/device/all five production partition hashes and backup/candidate hashes.
Write boot/vendor_boot only with full readback; all other partitions unchanged.
Capture full boot kernel JSON/source timestamps from first ADB response.
Require this target's notes, six symbol anchors, capture ID/READY, ECC64,
runtime watchdog/panic 1/1/1/10 and erratum2645198 capability. Reuse test240
symbols, never its relocation offset. This kernel has no pseudo-NMI capability;
do not claim calibrated test241 NMI capture for this separate candidate.

Startup observation ends at **120 seconds of target uptime**, not 300 seconds
after connection. Profile/readiness gates must finish by 90 s; run the helper
once after 60 s and retain >=30 s after it. If workload finishes after 90 s,
classify the planned timing gate inconclusive and stop; no extending the boot
budget to manufacture a pass. Host workload timeout20 s. Full evidence and
the exact 16-hit/8-executable-PTE verdict are required. Stop on CPU/RCU/CSD/
workqueue failure, suspect hardware timeout, transport loss or changed boot;
allow only up to20 s extra capture for a positive failure's backtrace.

Remove only owned tracing/temp helper, save raw evidence and final immutable
boot journal/list. Restore originals via BCB helper plus ordinary reboot into
TWRP, never reboot recovery; verify all-five hashes. Separate restored
production startup observation also ends at uptime120 s, including profile,
failed units, native ADB and NCM SSH banner (no authenticated shell claim).
This explicitly replaces older >=150 s preflight/production requirements for
this new focused trial only; no unattended repeated boots or long-soak claim.

If a real kernel wedge prevents recovery, preserve what is available and ask
the owner for TWRP only then. Automatic panic/timeouts are not a guarantee of
recovery. A functional coverage pass still does not prove physical erratum
reproduction, CPU-stall repair, or an absence of failures after120 s.
