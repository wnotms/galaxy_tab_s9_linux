# Type-C lifecycle reconnect candidate — host tested, not deployed

After the owner physically unplugged, authenticated same-boot SSH showed
port0-partner absent, sm5714-usb online=0 and battery Discharging, while DWC3
retained configured/high-speed and the gadget remained bound. Manual single UDC
unbind/rebind had restored Windows ADB/NCM and interface-bound NCM SSH. These
facts justify handling the missing physical-cable/gadget lifecycle boundary;
they do not prove the complete low-level cause or that automatic recovery works.

userspace/adbd/typec-lifecycle.py reads mainline Type-C/USB power_supply state,
uses kernel-origin netlink uevents and one-second stable confirmation, then
unbinds on partner-absent+online0 and rebinds its own empty binding on
partner-present+online1. Mixed state (including temporary VBUS loss during PD
reset) is unknown and causes no reset. Stable healthy links are never bounced.
No idle polling of I2C supply or periodic Windows/ADB failure heuristic. Before
writes it rechecks exact machine/boot/config/notes, DCC absence, direct disabled,
Sink/Device, VID/PID, both functions and their configuration links.

Only binding ownership is changed. No descriptors, NCM address, adbd binary,
service/helper, kernel/TCPM/DWC3/PHY, DTS, roles or charging policy changes.
Its independent service has Restart=no and no installed/enabled links. Unknown
binding/layout/kernel/role state stops without overwriting another actor. Normal
stop or receive/read fault restores only its own empty binding. SIGTERM/SIGINT
are masked through each write/ownership update; a real host signal test proves
successful unbind is not stranded in that critical interval. SIGKILL and a
blocked kernel write cannot be guaranteed recoverable; do not auto-restart and
adopt an unknown empty UDC. Physical rollback retains Wi-Fi and stops the unit
before reverting the exact owned rootfs overlay.

17 new behavioral tests plus 24 existing adbd tests PASS, 0 skip. Tests exercise
actual event loop and actual executor on filesystem fixtures: detach/attach,
unchanged healthy link, transient/hard reset, unknown/invalid read, ownership,
layout and boot/notes/direct/role drift, bind I/O failure, socket overflow,
service stop and an actual SIGTERM at successful unbind. These are host evidence,
not actual configfs/Type-C/FunctionFS/device qualification. Earlier15-test run
was before the two additional event/signal checks; it remains recorded. Syntax
check passes. No existing tests deleted/skipped/weakened and no routing change.
No new kernel build/full regression/Actions; source/build inputs are unchanged.

The earlier manual rebind also emitted a DWC3 ep0 dequeue diagnostic, recorded
in summary-after.json; do not suppress it or claim the kernel log was clean.
The controlled physical acceptance must capture whether this recurs and stop on
any new unclassified kernel error or lost rescue. Root cause/physical acceptance
remain open, and this is not deployment authorization for a stopped Test366.
Next independent sensor/native Escape registration must include this guard's
owned files/profile/rollback if selected, preserve existing interim-XKB removal
on the new driver, and retain the ordinary charging limits. SSC/rotation/full
port remain unfinished. Existing preflight GMU suspects remain open.
