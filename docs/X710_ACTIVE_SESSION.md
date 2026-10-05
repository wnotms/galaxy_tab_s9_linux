# Retained native direct-charge session

This change continues the full X710 charging port; it is not an activation
release. It is confined to the isolated native-control profile. Ordinary
SM5714 fixed charging, the connector, USB/userspace and production configuration
remain frozen. No device operation or physical test is performed here.

The terminal OFF-roundtrip coordinator cannot serve an active transaction:
clearing context loses hardware/source ownership, terminal OFF destroys prepared
settings, repeated facts reads launch too many conversions, and an active sample
is rejected as though the pump must always be OFF. Correct these semantics before
introducing an activation grant.

Keep one controller session across entry, monitor, refresh and retarget. Only a
new admitted session creates an epoch. Ownership survives a successful active
operation; first error/cancel/PM executes terminal OFF, verified fixed return and
source-bound switching release. Caller timeout cancels that same session and
cannot replace its work. PM drains both explicitly queued work and periodic work,
then performs the same terminal cleanup; resume never arms.

Temporary OFF uses checked native pause with settings/ENHIZ/watchdog retained,
followed by a fresh OFF sample. Every PPS refresh is OFF -> Request -> actual
VBUS check -> eligible facts -> native resume -> fresh running observation.
Retarget cannot increase current. Final OFF alone releases/restores hardware.
Running ADC uses the native supervisor, including actual raw-current/fault checks
and watchdog service. Terminal cleanup cancels both the historical running-monitor
converter and any newer paused OFF conversion; independently held ownership cannot
be skipped merely because the monitor has started. Facts collection brackets fresh source/pack reads around
the previous genuine native sample; it never retimestamps that sample or launches
three independent conversions in one monitor window.

Native source binding checks an actual owned TCPM snapshot and switching lease
outside the SM5440 I/O lock, then rechecks the hardware token under that lock.
It maps the controller epoch to the driver's hardware-session epoch only after
binding the source/lease. It cannot set actuator enable or OCP qualification.
Native ON remains closed without the separately qualified private activation
grant. The retained coordinator likewise has no public arming/qualification
setter. Host tests may seed private mock grants to exercise control flow; those
are not compiled into the kernel and are not physical acceptance.

Periodic monitoring must share the single ordered queue, preserve the original
epoch and refuse late work under the existing100ms deadline. Refresh is proposed
at4s from the Fedora reference, always paused. This is scheduling/refusal logic,
not a hard realtime protection guarantee. Source/temperature/I2C/ADC/PM faults
must terminate rather than retry or increase the current. Physical ADC validity,
calibration, current/protection/cutoff, PPS and <=1.8A pump acceptance remain
separate prerequisites before any activation or higher-power scope.
