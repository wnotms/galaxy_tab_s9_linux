# X710 fixed-peripheral USB lifecycle

Actual disconnect was detected by Type-C (partner absent) and SM5714 (USB
online=0, battery discharging), but DWC3 retained `configured`. Windows could
not see the tablet. A single UDC unbind/rebind restored USB ADB shell and
interface-bound NCM SSH in the same boot. See the complete evidence in
[USB recovery](../reference/desktop-bringup/usb-rescue/read-only-1791509149465214397/RESULTS.md).
The manual recovery also produced an ep0 dequeue diagnostic; this is not a
claim of a fault-free kernel USB path or a fully established low-level cause.

Stage2 deliberately keeps DWC3 `peripheral`, removing its inherited optional
role-switch provider. Linux TCPM's role switch and DWC3's OTG provider are in
the pinned source `drivers/usb/typec/tcpm/tcpm.c` and `drivers/usb/dwc3/drd.c`.
The current DTS explains this topology. Fedora X710 has broader dual-role/dock
support; blindly copying it would change source/host/OTG behavior. Reference
Fedora HEAD remains `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`. This candidate
keeps the accepted topology, using standard configfs as documented by pinned
Linux `Documentation/usb/gadget_configfs.rst`.

## Candidate

`userspace/adbd/typec-lifecycle.py` receives kernel Type-C/USB-supply uevents,
requires one second of consistent cable state, and rechecks before each write.
It does not poll the I2C supply while stable or use repeated Windows/ADB probes.

| Observation | Action |
| --- | --- |
| Partner absent, online0, original UDC bound | Unbind once and remember ownership |
| Partner present, online1, own UDC empty | Bind the same controller once |
| Healthy attached state | No reset |
| Mixed state, including partner present/VBUS0 during PD reset | Wait for another event |
| Binding/layout/kernel/role drift or read error | Stop; restore only its own empty binding when identity still matches |

Startup on a detached stale link is covered. An initially empty or unknown UDC
is rejected. Exact machine/boot/release/config/notes, DCC off, direct disabled,
Sink/Device and both original functions/links are checked. No descriptor, NCM
address, adbd, TCPM, charging, firmware, DT or kernel changes. The original unit
still creates the gadget. The new independent unit starts after it and adbd,
with `Restart=no`; stop restores its owned binding. SIGTERM/SIGINT are masked
through write/ownership updates. SIGKILL, a blocked kernel write or external
configfs changes require explicit recovery; no unknown binding is adopted.
This does not promise recovery from all USB faults or reset a healthy attached
link merely because an application cannot see ADB.

## Physical acceptance — registered, not yet executed

Independent [Test367](../reference/boot-tests/test-367-usb-typec-lifecycle/README.md)
now permits testing the userspace helper alone on the existing exact Test331
boot, without waiting for a sensor/kernel flash. It freezes prior fault evidence,
stops on any new error, deploys only three absent owned files and initially runs
a bounded transient unit. It does not reuse stopped Test366 or deploy native
Escape prematurely. Current GNOME and interim key mapping remain unchanged.

[Host results](../reference/desktop-bringup/usb-typec-lifecycle/RESULTS.md):
17 new lifecycle plus 24 existing adbd tests PASS/0skip. No installation or
enabled link. Profiles name exact Test331 and compiled native-Escape identities.
Install the helper at `/usr/local/libexec/gts9-usb-typec-lifecycle`, one exact
profile at `/etc/gts9-usb-typec-profile.json`, and the unit only through an
independently registered, hash-frozen reversible overlay. Back up pre-existing
files and reject unknown ownership. Do not reuse stopped Test366.

The next sensor/kernel test must include native Escape and remove only its
interim XKB swap. Include this helper's files/profile/cleanup if selected:

1. Admit the exact new kernel, disabled direct charge, ordinary limits, Wi-Fi,
   ADB/NCM and GNOME/input. Start this unit once, initially without enabling it.
2. Unplug PC USB once for at least15s; record absent partner, online0,
   discharging, one unbind, responsive Wi-Fi and unchanged boot.
3. Reconnect once; require one bind, Windows enumeration/ADB shell/device NCM.
   Report host NCM TCP separately. Preserve complete unit/kernel journals with
   source monotonic time; wall-clock jumps exist on this device.
4. First unknown/new kernel error, Code43, lost rescue, I/O failure or identity
   drift stops. Keep first evidence; no repeated resets. Stop this service,
   verify binding cleanup and restore its exact owned overlay/enabled link.
   Use the registered kernel/modules rollback if necessary.
5. Keep normal desktop startup and charge caps. Charger→PC can be a separate
   later boundary. Do not enable PPS/pump or increase current for this test.

Investigate the manual recovery's ep0 diagnostic if it recurs. Original GPU
suspects and missing SSC service remain separate open issues. Host mocks and
the manual recovery do not complete sensor rotation or the whole port.
