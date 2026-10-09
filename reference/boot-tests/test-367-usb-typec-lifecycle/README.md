# Test367 — same-boot USB Type-C lifecycle

Purpose: test the missing cable/configfs lifecycle boundary on the already
running accepted Test331 software. Owner physically unplugged the PC cable and
asked to fix reconnect without response. This test does not flash/reboot, start
SSC, change the kernel/DT/modules, change adbd, alter charging policy, request
PPS or enable the pump. Native Escape remains compiled for the next **kernel**
test; current interim XKB mapping and default GNOME remain unchanged.

## Baseline and attribution

Exact Test331 machine, release/config/notes and boot78ec1906 are frozen in
registration.json. Wi-Fi is10.49.219.210, authenticated through local OpenSSH
with native Windows TCP; a different host subnet is not by itself a failure.
Type-C is Sink/Device, DCC is off, direct charge is disabled. Preserve the full
existing kernel journal including GPU HFI and manual-rebind ep0 errors. The
registration freezes the **counts and full text** of pre-existing priority0..3
entries from archived evidence; a new occurrence of any of them still stops.
This is not a clean-kernel acceptance or a resolution of Test366's GMU stop.
Test366 remains closed and cannot be retried by this runner.

There is no flashing or charging experiment. SOC20..100 is admitted for this
same-boot, non-flashing USB test only, with Good/present pack,10..<42°C and
actual VBAT3.4..<4.44V. The sensor/kernel flashing SOC20..85 gate is unchanged.
No load is added to accelerate discharge. No charger connection in this test.

## One registered sequence

1. Read-only preflight: full kernel JSON, exact identity, battery, failed units,
   GNOME/adbd/SSH, gadget binding, roles, Windows USB/PnP; all new destinations
   absent. Verify the current cable is physically unplugged and battery is
   discharging. Save complete source-attributed journals and baseline cursors.
2. After committed/pushed registration and host qualification, install exactly
   three initially absent files listed in files.json, with a durable ownership
   ledger before the first file write. Reject symlinks/pre-existing unknowns.
   Start once using a distinct transient unit with RuntimeMaxSec1200 and
   Restart=no. The ordinary unit is installed but **not enabled or started**.
3. Confirm one initial stable-detached unbind and responsive same-boot Wi-Fi.
   Owner reconnects PC once. Observe30s, require one bind, Windows noCode43,
   ADB shell same machine/boot and device usb0/NCM address. Host NCM TCP is
   separate optional evidence under the owner's device-completion criterion.
4. Owner unplugs once for at least15s: partner absent, online0, discharging,
   exactly one additional unbind, Wi-Fi/GNOME responsive, no identity change.
5. Owner reconnects once:30s, exactly one additional bind, ADB and device NCM,
   no new fault. Preserve complete final kernel and unit JSON, raw Windows
   enumeration and ADB output. This proves a bounded cable cycle, not all USB
   faults, charger→PC, suspend or future boots. Persistent enablement requires
   separately recording the successful result and owned enabled-link change.

The host runner reads complete journals at boundaries, not every second. The
helper itself waits for real kernel uevents and one-second consistent state;
no idle I2C/ADB polling, repeated bounce or modification of the healthy link.

## First failure and rollback

Immediately record first-failure.json on a new priority<=3 kernel error (even
the same ep0 text), CPU/panic signature, Code43, role/kernel/boot/layout drift,
lost rescue, failed evidence collection, new failed unit, or unexpected/repeated
write. No retry or second start. Full original journals retain source timestamps
and boot IDs; no grep-only evidence. Failed host probes remain recorded.

Stop the transient service first; its finally path restores **only its own**
empty UDC to the original controller. Verify original binding/identity, then
remove only exact hash/mode/owner-verified installed files and ledger-owned
temporary copies. Refuse unknown edits. Retain transaction ledger and original
evidence; created empty parent directories may remain. No partition/module
rollback is needed because none changed. If Wi-Fi or kernel sysfs write hangs,
report the recovery gap; do not blind reboot, restart or enable diagnostics.
The20minute service backstop also stops/restores rather than retries. Normal
endpoint stays GNOME. No GPU error is hidden or labeled fixed to advance SSC.

## Local validation

Run the new transaction/attribution suite plus the existing lifecycle and actual
adbd suites. No test routing change, rebuild or Actions; unchanged kernel
qualification is reused and new physical behavior has not passed until recorded.
Host mock results are not a claim of working configfs/FunctionFS on hardware.
