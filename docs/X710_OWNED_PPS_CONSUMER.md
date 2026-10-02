# X710 owned PPS consumer — pump OFF only

Planning baseline a3d8bd4c/Test302. Keep the retained Test299/Test300 device and
fixed5V1.8A/9V1.5A path unchanged. Implement an actual kernel consumer of the
owned TCPM operation and battery switching lease, not another mock-only engine.
This is the pump-OFF protocol prerequisite to the eventual direct coordinator;
it does not replace active charging, protection or physical acceptance.

An explicitly called, single serialized operation reads the real standard pack
properties, fixed TCPM snapshot and new SM5440 OFF-mode acquisition before any
switching ownership. Use the existing100ms fresh API, not500ms diagnostics or
cached/restamped telemetry. Validate present/Good pack, SOC5..<80,3500..<4300mV,
20..<38C, die0..<55C, actual fixed9V within100mV, pump OFF and IBUS0. Validate
source APDO and existing8.2–10.5V/1.8A limits. These are initial bring-up limits,
not an increased ordinary charge limit or measured active protection.

Acquire the checked Q4-OFF lease, revalidate the pack/physical OFF evidence and
exact provider/source, then invoke the real owned PPS API once. Take genuinely
new physical VBUS/pack evidence for the requested pair; immediately return to
fixed through the real TCPM API. No timer, pump ON, auto-retry, source/role/DTS
change or userspace activation interface. After any post-acquire error, one
same-owner fixed cleanup is allowed only after physical OFF proof. The native PPS API already attempts fixed cleanup on a mutating error; the
consumer requires a read-only fixed snapshot after such failure, so it never
retries a failed native restoration. Release
switching only after logical fixed identity and a newly acquired100ms physical
fixed9V/OFF proof agree. Preserve the first error and report cleanup separately.
A source change may never restore or release an old lease onto a new connection.

A consumer mutex serializes the entire operation; neither it nor PM uses provider
locks. No charger/TCPC/ADC mutex is held over TCPM waits. A PM prepare notifier
sets cancellation before waiting for the consumer to drain. Cleanup may restore
the same physical source despite this cancellation, but cannot begin another
PPS request. Unresolved ownership blocks another attempt and suspend; post-PM
does not rearm, refresh or forget the fault. Built-in initialization only installs
this PM boundary. The existing offline-policy profile compiles the consumer;
normal passive/default profiles do not call or arm it.

Test actual consumer C, not a reimplementation: healthy roundtrip/action order,
all standard-property/ADC/ownership/PPS/fixed/release failures, epoch changes,
PM during acquisition/negotiation/cleanup, concurrent callers and stale/future
measurement times. Also retain existing affected policy/PPS/ownership tests.
Build the explicit policy profile and audit its sole explained config delta.
No flash/reboot/cable test in this offline qualification. Known passive startup
refusal and>100ms converter latency remain real blockers, not exceptions.

Release means authorization returned to the unchanged battery poller, not
completed Q4 programming. The source-bound release uses try-only companion/
charger locks and schedules that poller; no IIO/I2C under the TCPC source gate.
This avoids adding its possible501ms thermistor wait to a transport lock.
The existing synchronous release/default charging behavior remains unchanged.
Physical acceptance must separately observe ordinary charging restoration.
