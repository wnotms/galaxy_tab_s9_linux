# GNOME Escape swap — physically confirmed, interim userspace implementation

Same Debian boot 78ec1906-4713-4837-9acc-fe245647d7cf. Native and host libxkbcommon compilation passed: only ESC/TLDE symbol lists changed, existing US layout and other keys retained. ms's gts9:swap_escape_grave option is enabled and source/files read back exactly. GDM, paired input, SSH and ADB remain active with zero failed units. The owner confirms plain Esc closes a menu and Fn+Esc enters grave. Shifted grave is validated as tilde by the native compiler, not separately physically confirmed.

The initial background raw-key capture returned empty files and is not hardware-code evidence; retained without a fabricated pass. Physical GNOME behavior is confirmed separately after activation.

Persistent configuration applies to ms's GNOME Wayland session; firmware, GDM and Linux consoles remain unchanged. Subsequently the owner requests a driver implementation. This accepted mapping stays active while the driver change is prepared; it must be removed when the new driver boots, before testing, to avoid a double swap. No kernel deployed by this stage.

Python syntax plus native/host exact keymap comparison executed; no unrelated unit suite/full build/Actions. Original settings and owned-file hashes are archived for reversal.
