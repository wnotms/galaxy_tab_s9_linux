# Test358 — optional persistent GNOME touch

Test357's owner confirmed position/direction/desktop and raw two-touch release
checks. On the same exact331 boot, install only a hash-bound copy of that `.ko`,
the qualified loader, and its optional systemd unit. Module stays outside the
181 matched module directory. Enable through gdm.service.wants; leave GDM masks
and default target unchanged. Text-mode startup has no new touch dependency.

The loader pins full embedded config, notes and module SHA, board/release/arch,
and the unique existing DT client. Any SM5440 experimental cmdline or lpcharge=1
skips before loading. Test348's notes differ, so it cannot load there. Approved
new load uses only ordinary insmod, at most once, and passive async probe wait.
No force/version/signature/BTF bypass, firmware update, sysfs mutation or unload.

This physical scope **does not load the module again**: preflight requires the
known Test357 loaded/bound input, healthy battery and same boot. Start the new
service once and require already-loaded/zero-insmod, active GNOME/SSH, unchanged
three GDM masks and no new kernel fault/failed unit. If a target already exists,
stop before writing; do not replace somebody else's file. No flash/reboot.
Future real-boot/GDM-triggered loading needs separate acceptance; current start
does not prove reboot persistence. Rollback disables the optional unit and
removes only its owned files; do not unload the live driver as a shortcut.

17 affected tests passed: real pinned artifacts, sysfs fixture identity/safety,
one-shot/failure/timeout/boot-change/already-loaded behavior and actual systemd
syntax. Preserve initial host fixture bug and before-install missing-target
verdict (zero insmod). Read-only check against the existing Test357 module then
passed. Existing 8 actual-C decoder and W=1 module build qualification reused;
kernel rebuild/full-suite/routing change executed:false. No CI.

348 grant unused; stop desktop and freshly admit its eventual charging scope.
Its active artifacts/provider and production331 rollback remain protected even
though historical10-round window is now349–358. No new image/build tree.
