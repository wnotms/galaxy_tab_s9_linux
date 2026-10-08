# Test363 — pair bound; pen position and palm behavior accepted

The registered installation gate completed on the exact Test362 boot. The
two optional modules, paired loader, and systemd unit were copied with the
registered hashes. The currently loaded ordinary FTS and Wacom drivers were
left untouched; `gts9-touch.service` remains active in this boot but is
disabled for the next boot, while `gts9-palm.service` is enabled and remains
inactive. No module was unloaded, no service was started, and no reboot or
partition write was performed.

After the owner confirmed a manual reboot, the same SSH host key matched at
10.175.236.134. New boot `28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af` retained exact
Test331 config and kernel notes. Both input modules were absent before the one
service start. Wacom then paired FTS loaded successfully, exposing Wacom
`event4` and FTS `event5`. The full before/after kernel journals are preserved
in `activation.stdout`; the final journal and raw input are in
`capture-evidence.tar.gz`.

GNOME was started once using Test360's temporary-mask procedure; all three
historical GDM masks were restored without stopping the desktop. The two-input
non-grabbing collector (PID 1860, start ticks 20817) completed after the owner
response, in 67.126 seconds. It recorded 11,859 pen events / 3,980 frames and
297 touch events / 53 frames. Six pen-proximity enter/leave pairs ended out of
range; all eight finger contacts ended released. No new finger tracking ID
started during the observed pen-proximity intervals, and finger contacts
occurred after pen removal. The owner confirmed accurate pen positioning,
palm suppression, and restored finger touch. These observations support that
bounded position/palm result; input absence alone is not proof of suppression
without the owner's attempted touch.

No pen-tip, pressure-change, or side-button event was observed. The owner then
clarified that a third-party pen was used and the tip was not pressed; tip and
pressure testing will happen later. This explains the missing test coverage;
it does not establish the pen's pressure/button capability or a driver failure.
Do not start another capture until the owner is ready. Suspend/calibration
extremes remain untested.

Final boot ID unchanged; GDM/pair service active, no failed unit. Pack 63%,
24.2 C, Good, Discharging. The nine new kernel records are expected module,
query, input and GPU firmware messages (including known unsigned-module taint),
with no new CPU/GPU/probe fault. No kernel/config/DTS/181-module-directory/
charging/USB/partition change or reboot command occurred.

Host tests/build `executed: false` for this evidence-only physical stage; reuse
the unchanged 27 affected loader/input tests and existing W=1 pair builds.
The three physical evidence scripts passed Python syntax checks. Full port and
Test348 remain incomplete.
