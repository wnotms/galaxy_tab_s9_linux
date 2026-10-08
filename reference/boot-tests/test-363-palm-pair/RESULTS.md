# Test363 installation result

The registered installation gate completed on the exact Test362 boot. The
two optional modules, paired loader, and systemd unit were copied with the
registered hashes. The currently loaded ordinary FTS and Wacom drivers were
left untouched; `gts9-touch.service` remains active in this boot but is
disabled for the next boot, while `gts9-palm.service` is enabled and remains
inactive. No module was unloaded, no service was started, and no reboot or
partition write was performed.

This is an installation result only. Test363's fresh-boot pair binding and
owner-provided pen/palm event capture remain pending.
