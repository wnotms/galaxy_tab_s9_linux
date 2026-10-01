# Test274 — bounded fresh-acquisition observer, offline only

Test273 proves C1 advertises PPS5–11V3A and ordinary fixed9V1500mA works, not
active readiness. Test272 provides the sleepable OFF-only API but no hardware
caller. Add a stand-alone external GPL diagnostic module built against exactly
that already qualified provider. Do not change its Image/config/DT/181module
archive, production fragment or any hardware driver. No autoload/rootfs package.

Explicit future module load starts at most8 single calls,1s between successes;
first provider/measurement/deadline error stops permanently. No repeated load
or retry to replace an error. One dedicated kthread, no charger/TCPC/provider
lock during acquisition or sleep. Module exit joins the thread; provider API
already pins its provider and revokes on suspend/unbind. Read-only0400debugfs
exports cached request/start/return/acquisition times/status/uV/uA/deciC, never
calls I2C or triggers another request. No parameters/write/ON/PPS/faultclear.
Consumer verifies online/IBUS0, frozen<4.3V OFF-mode diagnostic range and ordinary
<=9.5V reported VBUS, temperature, genuinely newer stamp/100ms delivery. This
is observation, not physical ADC calibration or guaranteed current cutoff.

Build new .ko once with sameclang21/ccache/ARM64 pinned7.2-rc3 tree and Test272
Module.symvers; record imports/source/header/symbol/artifact identities. Reuse
unchanged272 Image/config/DTB/181modules. Fullhost once after implementation;
results/docs do not repeat it. No device commands, install, flash, reboot or PPS.
Old263 lacks the new symbol; do not force-load the observer there. A future
separate Test275 must register exact272provider/pairedmodules+optionalobserver,
263rollback, essential once-only rescue/identity/thermal gates and one PCUSB
OFF-mode30s observation; no high-power stage is authorized by timing acceptance.
