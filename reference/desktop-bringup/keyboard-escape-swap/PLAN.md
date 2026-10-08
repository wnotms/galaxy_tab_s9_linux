# Esc / Fn+Esc preference

Owner requests swapping ordinary top-left grave and Fn+Esc escape. Native keyboard is Samsung Book Cover Keyboard Slim EF-DX710, bus0018 vendor04e8 producta035, event2 on I2C5/0x2a. Driver forwards MCU Linux keycodes; it has no scan-code remap table. No kernel change needed for the current GNOME Wayland session.

Use a user-specific libxkbcommon option, keeping the existing US input source. User ms has no existing xkb-options or custom XKB tree. Add ~/.config/xkb/rules/evdev (include the system rules) and symbols/gts9; append gts9:swap_escape_grave to ms's options. Swap only ESC/TLDE symbols, preserving Shift+Fn+Esc as tilde. This is the ms GNOME/Wayland keymap, not a firmware, Linux console or GDM login change. Other keyboards used within that same session share the keymap.

Validate the native compiled keymap before activation: exact two changed keys and all other key symbols equal; preserve source/options and original paths for rollback. Do not change kernel, firmware, charging, GDM startup or Ctrl+Alt+T. No reboot, new packages or full regression. Source reference: https://xkbcommon.org/doc/1.5.0/md_doc_user_configuration.html (custom options/rules inclusion).

Initial evtest background process ended with empty output; not raw-key evidence. Owner pressed the requested keys but the failed host capture does not prove codes. Existing owner's reported behavior plus compiled mapping must be verified by physical post-change confirmation. Preserve this capture defect.

Rollback: restore recorded original ms xkb-options and remove only these new owned files (provided their hashes still match). Preserve unrelated options/input sources. New scoped evidence and a physical check conclude this userspace change.
