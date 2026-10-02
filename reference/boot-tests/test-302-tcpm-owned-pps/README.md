# Test302 — owned standard TCPM PPS operation, offline only

Baseline df9888a3/Test301; current device remains retained source9173df11/Test300.
No device commands/flash/reboot/rootfs/pump ON or installed live consumer.

Purpose: implement actual standard ONLINE=2/current/voltage transactions with
per-operation exact RDO permissions and checked switching-OFF ownership callbacks,
plus fixed return through native 2.5W standby. This is protocol and OFF-ownership
qualification, not physical PPS/direct-charge acceptance or ADC/OCP waiver.

Code: SM5714 battery/TCPC/shared bounds and callback contract kind only. Keep
fixed5V1.8A/9V1.5A, 4.44V/thermal safety, config/DTS/core/USB/roles/SM5440 unchanged.
Initial kernel-only PPS bounds8.2–10.5V/1.8A from existing reviewed bring-up gate;
no activation absent explicit owned operation, and permission closes on return.
Use real TCPM PSY APIs/own protocol engine, no Samsung private PD framework.

Host tests execute actual API/gate/TX/callback C with real mutexes, faulted
properties, setter, transport and lifecycle; actual battery/I2C lease tests cover
hardware OFF programming. Native TCPM remains mocked, not hardware proof. Test
all old affected SM5714 plus shared pure bounds, retain existing negative checks.
One incremental ARM64 Image/DT/modules, W1/sparse changed objects using the exact
ccache environment, exact prior config/DT, compiled overlays/protected files and
181 matched modules. No routine full rerun or Actions under latest owner scope.

Stop qualification on source/test/build/identity mismatch, retain failures and
fix them. Candidate cannot be installed without a separately registered physical
scope. Next consumer/physical ADC-OCP-PM requirements remain; Stage3 NOT READY.
