# Optional persistent X710 desktop touch

Test357 accepted this byte-identical Fedora X710 module on exact Test331 after
checking all 37 imported CRCs against its Image and normal-loader ABI/BTF gates.
This loader pins that module, embedded config and kernel notes. It skips other
kernels (including Test348), other boards and SM5440 experiment/`lpcharge=1`
command lines. Same release/vermagic alone is insufficient. Kernel signature,
version and BTF enforcement are not bypassed. The unsigned external module
retains its recorded O/E taint; no firmware update, S Pen or double-tap wake.

This is optional desktop integration, not part of the generic rootfs installer.
Install the qualified `.ko` at `/usr/local/lib/gts9-desktop/fts1ba90a.ko`, `load.py`
at `/usr/local/libexec/gts9-touch`, and the unit in `/etc/systemd/system/`.
Then daemon-reload and enable `gts9-touch.service`. Its Wants link belongs to
**gdm.service**, so text-only boots do not request it, and failure does not block
rescue or GDM. Existing GDM masks/default target remain unchanged. Keep the
owned directory/files root-owned and not writable by ordinary users.

Run the loader without `--load` for a read-only check. With `--load`, a qualified
unbound client gets at most one ordinary insmod and five seconds of passive
probe observation. An already bound input gets no insmod/sysfs writes. This
already-loaded path does not cryptographically attest the memory contents of
an arbitrary pre-existing module; Test358 uses Test357's known one-load boot.
Missing/corrupt module or failed probe on the approved kernel is an error;
unavailable/unqualified kernel identity is a safe skip. No automatic retries,
force unload, regulator cycling or reboot. Journal contains the JSON verdict.

Rollback: disable `gts9-touch.service` and remove only these three owned files
and the empty owned directory. Do not unload the live driver as a packaging
shortcut; its removal and suspend remain unqualified. Future GDM-triggered
loading after a real boot is a separate acceptance step; enabling the unit in
an already-loaded boot does not prove that path works on a reboot.

Test348 remains unused. Stop desktop for its future freshly registered
admission; its kernel identity is not allowed by this loader. No charging,
kernel, DTS, default module directory or USB/ADB configuration changes here.
