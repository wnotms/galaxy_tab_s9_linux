# Windows connection sounds: retained incident

The owner reported continuous connection sounds with the cable untouched,
then reported normal operation after manually unplugging/replugging PC USB.
The ordinary charging collector had not started, and no charger attachment,
reboot, flash or configuration change was requested or performed.

Before the manual replug, the captured tablet USB service journal contains only
startup events. Ten subsequent UDC samples remain `configured`, same boot
18bce160, adbd PID862 and NRestarts=0. The unattached `dummy_udc.0` is unrelated:
the gts9 gadget is bound to `a600000.usb`. Windows composite/ADB/NCM snapshots
are OK with problem code0; no Code43 was observed.

The first Windows inventory watch took58.924s but only obtained five polls;
it cannot exclude brief changes between snapshots. A50.816s generic WMI event
listener captured41 notifications (27 configuration changes,14 arrivals, no
removals), without device IDs. A separate50.041s PnP-ID listener captured162
modification events clustered at listener startup across many unrelated devices,
including the tablet; they all retain present/OK/problem0. These notifications
alone do not prove physical USB re-enumeration. System evidence also contains
Hyper-V/FSE-switch NIC create/delete/connect events; no causal link between
those events and the audible sound is established.

Event-log availability/errors are explicit in the raw records. Empty filtered
log output is not proof that Windows had no device changes. Generic event type
interpretation follows [Microsoft Win32_DeviceChangeEvent documentation](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-devicechangeevent).

After the owner's replug, the saved device journal shows FunctionFS suspend,
disable and enable; adbd remains PID862 with NRestarts=0. ADB lists the tablet
as `device`. One authenticated NCM SSH succeeds on the verified Windows/WSL
169.254.59.206 path, with13.043s metadata readiness and no delayed-readiness
sample. Wi-Fi health capture remains the same boot, battery54%/28.1C/Good,
passive SM5440 Good/Not charging/0A and no failed units.

First postprocessing of that health capture incorrectly removed the empty
failed-section terminator and raised a host KeyError. The complete same saved
raw capture was then parsed successfully; no device command was repeated for
that error. Its provenance is retained in `replug-health-summary.json`.

Outcome: owner-reported recovery and fresh transport/health gates pass.
Root cause remains **unknown**; this is not a software fix or repeated-reconnect
qualification. Preserve this incident separately from subsequent charging
results. No kernel, USB, adbd, charging policy or power configuration changed.
The40 affected host tests from registration and unchanged Test260 qualification
are reused; results-only analysis executes no new tests/build. Charging may
proceed with Wi-Fi telemetry and the registered first-fault stops.
