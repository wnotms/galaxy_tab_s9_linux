# Test347 candidate prepared for owner-confirmed C1 activation

Fresh PC preflight passed on accepted Test331 boot a96de8c0 at SOC 68%, 32.0°C.
The earlier SOC 71% rejection remains retained separately. One paired installation
verified all five partitions and 181 candidate module files. Normal PC boot
19fbf94136a64f7cb73e9e263da8549c was uniquely attributed; exact candidate config,
notes, partition/module identities, journal and rescue gates passed.

ADB, device-side NCM and authenticated Wi-Fi SSH (10.175.236.175) are available.
Admission readings: SOC 69%, 32.4°C, 4.086V. The initial preparation worker was
drained, the driver unbound, and physical pump-OFF/no-entry proof retained.
No Test347 guardian, activation, PPS request or pump run has started.

The next step requires a fresh owner C1 reply tied to this candidate boot. Only
then launch the sole guardian and one 300-second attempt; no timer runs during
manual cable handoff. Hardware input remains 1700mA; PPS/raw-current stop remains
1800mA. Exact Test331 boot and original 181 modules must be restored after this
attempt. rollback_required=true. This is deployment evidence, not charging
acceptance. Full charging port remains NOT_READY.

Tests executed: false; build executed: false. Reuse existing 60 host / 79 actual-C
and ARM64/W=1/sparse qualification. No kernel/config/DT/policy edits in this stage.
