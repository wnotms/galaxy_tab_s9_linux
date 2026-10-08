# SSC reverse-RPC trace preparation after Test365

Read-only current-X710 vendor RFSA audit: 66 regular/link inventory entries, all approved roots checked, no oemconfig.so. Original stock DSP inventory also lacks it. Treat Test365's lookup message as an unresolved lookup, not proof of a missing required library; do not invent/copy a binary from another device.

Reuse the exact prepared Fedora X710 hexagonrpc 0.4.0 plus its existing Samsung registry/buffer patches. Build only that userspace component with upstream hexagonrpcd_verbose=true, preserve the accepted package/source trees and versions. No kernel diagnostics or protocol policy changes. A later registered single boot can reveal reverse-RPC methods/file access plus QRTR service presence, then stop on the first failure; do not merely expand the old discovery window or repeat its unchanged profile.

Owner explicitly requests next physical test also include the compiled EF-DX710 Escape driver. Use out/kernel-x710-esc-driver for that next candidate, with exact new kernel notes/config/modules, same DTB, early signed ADSP firmware and paired input loader qualification. Remove only the interim gts9:swap_escape_grave XKB option for the new driver and restore it on Test331 rollback. Preserve ordinary GNOME startup at the healthy endpoint. This is not permission to enable PPS/pump or raise current.

Before the next registration fix the reused rollback slot bug: Test365's frozen Test364 helper checked a Test364 slot. A new independently tested parameterized recovery path must verify the actual namespace slot and original manifest before partition writes. Keep historical failed results and frozen runners unchanged.

This directory is offline preparation only; no firmware/binary installed and no ADSP/SSC activation. Next physical scope, native loader identities and guardian/recovery registration are pending, not PASS.
