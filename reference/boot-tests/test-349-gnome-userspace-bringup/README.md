# Test349 — GNOME userspace and bounded GPU/Wayland bring-up

Owner requested GPU/desktop work **during** the discharge wait, selected GNOME
and allowed Fedora/Samsung references. This is independent of the still unused
Test348 PPS grant. The earlier assistant-created after-Test348 ordering was too
broad: the charging candidate stays frozen, while this separately registered
test adds desktop userspace to current normal Test331. No charging or USB logic
is changed. Register/commit/push before the first device write.

Read-only preflight passed on boot `be1baaaa47fc41f582558f7092c01653`: exact
config/notes/all five partitions/original181 modules, DCC absent, charging test
opt-ins false, zero failed units, 38 protected gts9 helpers/units hashed and
authenticated Wi-Fi rescue. USB is physically unplugged. Battery95%,31.6C,
Discharging; root filesystem has104GB free. Full raw kernel JSON is retained.

Use the verified single archive: 368 new Debian packages and three same-model
GPU firmware files, with the qualified installer. One installation attempt;
no upgrade/removal/index update, existing files preserved, all GDM entry points
masked and temporary service policy restored. Log actual package transaction
and the new rootfs state; do not claim an unchanged original Test331 rootfs.

If installation passes with protected files unchanged, allow one Vulkan identity
probe (30s bound), then one controlled GDM start and60s observation. Confirm the
actual hardware renderer and ask for a physical screen observation. A merely
active service or software renderer is not graphical acceptance. No benchmark,
stress load, touch module load, kernel/config/DT change, flash, reboot, USB
reconfiguration, PPS or pump activation is included.

First new CPU/kernel/GPU fault, lost rescue, unknown identity, new serious failed
unit, package drift or pack>=42C stops. Preserve raw before/after journals and
transaction evidence. Stop GDM where responsive and retain its masks; no blind
retry or automatic apt removal. If the system is unresponsive, request manual
recovery with available evidence. This stage does not replace the installed
boot/modules or their rollback files.

End on the same normal Test331 boot with GDM masked/inactive. Natural battery
observation can continue, explicitly including this ordinary userspace setup
activity rather than presenting it as an idle-power test. Before Test348, admit
a fresh candidate boot with desktop inactive and the same charging artifacts,
limits and critical gts9 files. Its eventual exact331 restoration/TWRP endpoint
remains unchanged. See `registration.json` and the Test348 parallel addendum.

Offline qualification is reused: installer27 tests, touch8 tests (module not
loaded here), complete381-member archive verification and packaged entrypoint
cache validation. Registration/docs: unit tests/build/full regression
**executed:false**; relevant source/assets are unchanged. No GitHub Actions.
