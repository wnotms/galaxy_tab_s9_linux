# Default GNOME login and terminal shortcut

Owner explicitly requests future ordinary boots start the graphical interface and reports Ctrl+Alt+T does not launch a terminal. Apply on the exact restored Test331 boot `78ec1906-4713-4837-9acc-fe245647d7cf`, after successful partition/module/config/notes recovery. GDM and touch/pen were already physically accepted. This is userspace startup configuration, no new hardware/kernel profile.

Read-only diagnosis: graphical.target is already the default, but all three GDM entry points persistently point to /dev/null. GNOME Console `/usr/bin/kgx` 48.0.1 is installed. User ms has an empty media-keys custom-keybindings list. Remove only these reviewed GDM masks, restore the display-manager link, retain graphical.target, enable the accepted palm+pen paired loader, start it before GDM. The paired loader must pass its existing kernel/module identity gate. Preserve the existing power-key backlight-only service, password login, SSH/ADB and charging policy.

Configure only ms's dedicated gts9-terminal custom shortcut to launch /usr/bin/kgx with Ctrl+Alt+T; append its path without replacing other custom shortcuts. Save previous values and systemd links. Do not change unrelated keyboard shortcuts or enable automatic login.

Verify same boot, active GDM/input/rescue, persistent startup links, exact shortcut readback and session/kernel journal. No reboot solely to retest previously accepted graphics; actual future-boot and physical keypress confirmation remain pending. If startup fails, stop GDM and inspect the first failure; do not change kernel or retry flashes.

Rollback: stop GDM; restore only the recorded GDM mask/link states and previous default target; remove the dedicated shortcut path from the collection and restore its three previous values. Preserve unrelated current bindings. This returns to the prior text-only test guard if needed.

Validation: Python syntax and focused source review. No new kernel build/full host regression for reversible low-impact userspace settings. Archive native before/after and service evidence; no Actions.
