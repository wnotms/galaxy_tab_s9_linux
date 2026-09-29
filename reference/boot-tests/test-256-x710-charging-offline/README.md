# Test256: X710 wired charging audit and offline Stage3 development

Purpose: extract X710 vendor hardware/policy evidence, improve SM5714 lifecycle
and bounds while retaining fixed5V/9V behavior, and prepare passive SM5440 /
default-inactive transaction code. This is not physical charging acceptance.

Start HEAD `ebf4af1c098af1179c69d6f59dcdcb756d03e21a`, branch test. Test255
attempt03 is immutable. Linux7.2-rc3 pin and all accepted software artifacts are
frozen. No tablet commands, flash/reboot/module/rootfs/config deployment,
PPS request or pump activation. No GitHub Actions. Push only origin/test.

Design docs precede implementation. Keep audit, SM5714 lifecycle work, PPS
bounds, passive hardware, and transaction tests separable. After each commit
run isolated build, host tests, config/DT diff and protected-source audit;
record failure honestly. Each candidate includes resolved config/Image.gz/DTB/
notes/module archive/hashes and exact source identity. New image is unaccepted.

Primary build keeps SM5440 and every APDO/direct path disabled. Passive profile
is explicitly named and isolated; no CPU diagnostic profile reuse. Unresolved
OCP/sensor/ADC/PM semantics block active readiness. Stage3D/E only future plans.
Rollback is unnecessary here because no device state changes. Preserve actual
accepted artifact pair for future authorized recovery, not a newly rebuilt image.

See five design documents under docs and final RESULTS/summary for implemented,
compiled, host-tested, hardware-tested and unimplemented distinctions.
