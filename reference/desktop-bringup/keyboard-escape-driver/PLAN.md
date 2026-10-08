# EF-DX710 driver-level Esc / grave swap — offline candidate

Owner requests the accepted GNOME-only swap be implemented in the driver. Change only the native keyboard driver used by CONFIG_KEYBOARD_SAMSUNG_POGO=y; the imported vendor implementation remains reference-only. The existing model admission accepts only EF-DX710 (0x02).

At IRQ packet delivery, translate KEY_GRAVE -> KEY_ESC and KEY_ESC -> KEY_GRAVE identically for press and release. Leave MCU packets, validation, all other keys, LEDs, reset/power, connection and PM logic unchanged. Input-core pressed-key state stores the translated code, so the unchanged detach/error/suspend release path operates on logical pressed keys. Do not add a userspace grab daemon or alter keyboard firmware.

Extend the existing extracted actual C packet harness: both press/release pairs, all valid Linux keycodes unchanged apart from the two requested keys, malformed packet rejection before translated output. Run existing startup and suspend tests. Reuse current native-SoCinfo source/build directories, JOBS=8/shared ccache and sm5440-fedora ordinary profile; preserve exact Test331/Test365 formal artifacts. New output goes to out/kernel-x710-esc-driver. Only driver source changes relative to the qualified native provider; config and DTB must remain exact. Its existing QCOM_SOCINFO=y remains the only config difference versus installed Test331, not an added change here.

No device deployment/reboot/charging changes in this task. The tablet keeps the physically accepted ms GNOME XKB swap until a registered driver-candidate deployment. Before that new driver's first desktop use remove only gts9:swap_escape_grave from ms's xkb-options (preserve other options). The kernel translation otherwise combined with the old XKB option would cancel the intended swap. Use exact new input-module/provider pairing and loader identities; do not relax accepted loader gates.

Future physical acceptance: kernel/boot/modules identity and rescue, raw event2 plain Esc emits KEY_ESC and Fn+Esc emits KEY_GRAVE (both edges), GDM and text console Escape behavior, GNOME plain Esc cancel and Fn+Esc grave/Shift+Fn+Esc tilde, Ctrl+Alt+T unchanged, no stuck key after keyboard detach. Rollback restores accepted Test331 boot/modules and reapplies the current accepted XKB option. No PPS/pump/new current scope.

Tests/build are scoped to the actual keyboard change under current owner workflow; no full historical regression, Actions or firmware writes.
