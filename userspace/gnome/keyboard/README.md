# EF-DX710 Esc preference in GNOME Wayland

The owner's normal top-left key emits grave; Fn+Esc provides Escape. The
`gts9:swap_escape_grave` option swaps the corresponding XKB ESC and TLDE keys.
Plain Esc then cancels, Fn+Esc enters grave (`), Shift+Fn+Esc enters tilde (~).
All other compiled US key symbols remain equal to the original keymap.

This uses libxkbcommon's documented custom-option mechanism:
https://xkbcommon.org/doc/1.5.0/md_doc_user_configuration.html
The local `rules/evdev` includes `%S/evdev`, leaving standard rules intact.
The deployed files belong to user ms under `~/.config/xkb`; existing GNOME
input sources and other XKB options are preserved. It applies to keyboards in
that user's GNOME Wayland session. GDM login, text consoles, kernel events and
keyboard firmware retain their existing mapping.

`validate.py <isolated-tree>` compiles both baseline and modified keymaps and
checks that only ESC/TLDE key symbols differ, including the shifted grave
symbol. Native validation runs before `apply.py` installs anything in the
active user tree. Apply requires root, an exact expected boot ID, an active ms
session bus, the reviewed US source and an absent custom XKB tree. Existing
custom trees are rejected rather than overwritten. A new evidence directory
stores before/after settings, native validation and the owned-file hashes.

On the qualified device, deploy these four small files to one directory and run:

```sh
python3 apply.py --boot-id <current-boot-uuid> --evidence <new-evidence-directory>
```

No reboot or GDM restart is required. Verify physically in a terminal and a
menu. To undo, restore the recorded original xkb-options using ms's session
bus, then remove only the two owned files after checking their recorded hashes.
Remove newly empty parent directories with `rmdir`; preserve unrelated files.
Use `gsettings get org.gnome.desktop.input-sources xkb-options` before restoring
if later edits have added options, and remove just `gts9:swap_escape_grave`
instead of overwriting those later settings.

The qualification and actual device settings are archived in
`reference/desktop-bringup/keyboard-escape-swap/`. No kernel/charging/input
transport changes, new packages or full host regression are part of this task.
