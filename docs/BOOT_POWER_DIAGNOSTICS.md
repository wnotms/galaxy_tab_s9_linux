# Debian boot and power-off diagnostics

## Correction after test 179 (2026-09-24): the platform does power the tablet off

Text further down that treats the power-off path as unproven, or that reads a
missing `Power down` line as evidence about `PSCI SYSTEM_OFF`, is superseded.
The corrected statement is:

> A previous `systemctl`/`poweroff` path stopped at the final framebuffer, but
> the owner has since verified that `shutdown` can physically power the tablet
> off.  Therefore the platform is known to possess at least one working
> shutdown path.  The remaining issue is to identify why `poweroff` and
> `shutdown` differ.

Test 179 then answered that remaining question on hardware, from fresh boots,
with the kernel power-off trace enabled (`gts9_poweroff_trace=1`) and
`console=tty0` so the panel carries the shutdown messages:

| Test | Command | `boot_id` before | USB gone → back (host clock) | `boot_id` after | `lpcharge=1` | Result |
|---|---|---|---|---|---|---|
| P4 | `poweroff` | `60fb1021…` | 00:32:33.6 → 00:32:43.0 | `bec55a95…` | 13 params | PASS |
| P1 | `shutdown -P now` | `bec55a95…` | 00:35:16.6 → 00:35:24.8 | `84a628e5…` | 13 params | PASS |
| P2 | `shutdown now` | `84a628e5…` | 00:38:14.0 → 00:38:22.4 | `6ae34442…` | 13 params | PASS |
| P3 | `systemctl poweroff` | `6ae34442…` | 00:41:11.9 → 00:41:20.1 | `a4a65a66…` | 13 params | PASS |
| P5 | `shutdown` | `a4a65a66…` | 00:45:09.2 → 00:45:17.4 | `42efa64f…` | 13 params | PASS |

`lpcharge=1` is the bootloader's own record that this start was a
charger-triggered one, i.e. a start after the platform lost power; every plain
reboot in the same session (the TWRP `reboot system` and the owner's forced
restart) carried `lpcharge=0`.  Each run also shows the full systemd power-off
sequence in the previous boot's persistent journal
(`Reached target poweroff.target` → `Shutting down.` →
`systemd-shutdown[1]: Syncing filesystems and block devices.`) and a
`/var/log/gts9-last-poweroff-stage` marker whose recorded `boot_id` matches the
boot that was shut down.

All five entry points are the same program.  `/sbin/shutdown`,
`/usr/sbin/shutdown`, `/sbin/poweroff` and `/usr/sbin/poweroff` are symlinks to
`/usr/bin/systemctl` (identical md5 `2c2515eeb6b923cbb70bee173180bf3d`), and
systemd's `shutdown(8)` documents `-P/--poweroff` as the default action, so the
four spellings select the same `poweroff.target`.  The only measured difference
is timing: plain `shutdown` uses the sysvinit default of one minute
(`Shutdown scheduled for …, use 'shutdown -c' to cancel.`, power off 63.5 s
after the command) while the other four act within about three seconds.

Consequence for this repository: there is no evidence for a kernel-side
power-off defect, and no PMIC, PSCI, PON, SPMI or `pshold` change is justified
by it.  The earlier "poweroff stops at a blinking cursor" observation belongs to
an older image and session (test 172 is the record of that image), and it does
not reproduce with the current image set.  Historical test records are left
unchanged: test 172 recorded what that particular image did, and later physical
runs showed `shutdown` powering the tablet off normally.

## What current evidence says

The device can boot the current mainline kernel into Debian when Type-C is
connected. In that boot, the Qualcomm SD host appeared at about 0.47 seconds,
the microSD card at about 0.67 seconds, and `/dev/mmcblk1p1` was mounted as the
root filesystem at about 2.13 seconds. The regulator summary showed the SD
controller's 1.8 V `vqmmc` and 3.0 V `vmmc` consumers enabled. This only
describes that successful boot; it does not establish what happens on a
battery-only cold boot.

The reported flashing cursor does not identify a boot stage. The existing
initramfs waits up to 15 seconds for `/dev/mmcblk1p1`, then keeps PID 1 in a
rescue shell if the card, ext4 mount, init binary, or `switch_root` check fails.
The display also has a known cold-boot recovery path. A cursor alone therefore
cannot distinguish an initramfs handoff failure from a display that did not
finish coming up.

The current kernel reports PSCI 1.1 from firmware and has
`CONFIG_ARM_PSCI_FW=y`. Its `psci_sys_poweroff()` invokes PSCI
`SYSTEM_OFF`; arm64 reaches that callback from `machine_power_off()`. The
runtime has no `/sys/firmware/efi`, and the kernel says UEFI services are
unavailable, so EFI runtime power-off and EFI pstore are not active paths.
`CONFIG_POWER_RESET_QCOM_PON=y` populates PMIC power-key children but is not a
system power-off callback. No `qcom,pshold` node or `POWER_RESET_MSM` handler is
present in this build.

The previous boot's persistent journal ends with `systemd-shutdown` syncing
filesystems and sending SIGTERM. That journal boundary does not prove whether
the final shutdown program reached the kernel. The current `/sys/fs/pstore`
is empty and the live device tree has no ramoops node, so there is no confirmed
kernel-persistent trace for the failing attempt. Earlier test 010 recorded an
owner-observed physical power-off from a BusyBox initramfs. That establishes
that an earlier image on this device could power off, but it does not test the
current Debian shutdown path or identify the present cursor state.

**Superseded by test 179**: on the current image the Debian shutdown path does
reach the kernel and the platform does lose power, for all four entry points;
see the correction section at the top of this file.

Tests 168-169 add a useful physical A/B. In test 168, Debian recorded entry to
`systemd-poweroff.service`, then a new boot ID appeared after the owner saw the
tablet turn off and start again with Type-C still connected. In test 169, the
owner removed Type-C after shutdown: the tablet stayed off, a short power-key
press with Type-C disconnected did not start it, and reconnecting Type-C
started it automatically. This strongly supports VBUS insertion as the cause
of the automatic start. It is consistent with Linux having reached a real
power-off state, but there is no battery-current measurement or direct PSCI
trace, so the low-level call itself remains unproven.

**Superseded by test 179** (see the correction section at the top): the
charger-triggered start after each of the four power-off entry points is now
recorded by the bootloader itself as `lpcharge=1`, which is positive evidence
that power was removed, and the owner observed the panel going fully dark with
the charging screen before each restart.  The automatic restart with Type-C
attached is normal Samsung behaviour, not a power-off failure.

The source-level path is clear. systemd's final poweroff invokes Linux
`kernel_power_off()`, which runs shutdown preparation, migrates to the reboot
CPU, shuts down syscore, emits `Power down`, and enters arm64
`machine_power_off()`. That calls `do_kernel_power_off()`. The PSCI probe logs
firmware version 1.1 and the SMC conduit; `psci_0_2_set_functions()` installs
`psci_sys_poweroff()` in the legacy `pm_power_off` slot, and
`psci_sys_poweroff()` invokes `PSCI_0_2_FN_SYSTEM_OFF`. The generic poweroff
code wraps that legacy callback in a temporary default-priority sys-off
handler when it runs. The arm64 path stops secondary CPUs before dispatching
the sys-off chain. The kernel does not query `PSCI_FEATURES(SYSTEM_OFF)` in
this path: PSCI `SYSTEM_OFF` is part of the v0.2 function set, and Linux calls
it without checking the return value. `psci_sys_poweroff()` discards the SMC
return value, so a returned error is not reported and no Qualcomm fallback is
tried by that callback. The logged PSCI/SMCCC versions prove the conduit was
discovered, not that this particular `SYSTEM_OFF` call succeeded.
With `CONFIG_HIBERNATION=y`, Linux can also register a higher-priority PSCI
`SYSTEM_OFF2` handler if `PSCI_FEATURES(SYSTEM_OFF2)` advertises hibernate-off;
that callback is gated on entering hibernation and returns through the normal
handler chain for an ordinary poweroff.

There is no competing Qualcomm power-off handler in this DT. The
`qcom,pmk8350-pon` MFD driver populates the PMK8550 power-key/resin child and
registers reboot-mode handling, but it has no power-off callback. Its reboot
mode writer only touches SDAM when a configured mode matches the reboot
command; the DTS has recovery and bootloader modes but no `normal` mapping, so
the standard null poweroff command does not request an SDAM mode write. The
PMK8550 PWRKEY variant also sets `supports_ps_hold_poff_config = false`, so it
does not register the legacy PS_HOLD reboot notifier. The runtime tree has no
`qcom,pshold` node, so the MSM PS_HOLD power-off driver is not active. UEFI
runtime services are absent and there is no ramoops backend. COM17 is the USB
ACM gadget, while the kernel console is `ttyMSM0`; therefore the lack of
`Power down` on COM17 is not evidence that the kernel did not reach the PSCI
callback.

The test-169 screen after VBUS reconnect shows `GTS9 mainline: early display
console ready` and `GTS9 mainline: console on the AMSA10FA01 panel`. COM17 did
not provide a Debian login prompt. This proves kernel and panel-console startup
but not microSD discovery, root mount, `switch_root`, or systemd. The
stage-instrumented initramfs bundle has been built and validated but was not
flashed for this test, so the exact stop point remains unknown.

The two visible lines also bracket a large section of initramfs diagnostics.
After the second marker, `/init` reads DRM, backlight, framebuffer, Pogo, USB,
interrupt, regulator, clock, and block-device state before attempting the
microSD handoff. A read of one of those interfaces could leave the display
showing the last marker without reaching the rescue shell. To localize this
without changing normal boots, `/init` accepts the opt-in
`gts9_boot_trace_console=1` argument and prints each report section's begin/end
marker to tty0; the normal cmdline does not enable it. A separate
`boot/cmdline.boot-trace.example.txt` is provided for assembling a diagnostic
candidate. The end marker includes the report command's exit status. This
instrumentation does not skip or reorder any report command.

The board DTS binds the microSD controller's `vmmc` to PM8550B L9B
(`vreg_l9b_2p9`) and `vqmmc` to L8B (`vreg_l8b_1p8`). On a prior successful
Type-C-connected Debian boot both consumers were enabled. The same DTS fixes
DWC3 to peripheral mode because the SM5714 Type-C controller has no working
mainline role-switch integration; Type-C attach is therefore not shown to
toggle the microSD regulator through the Linux USB role path. This does not
rule out a PMIC/boot-firmware VBUS side effect, and there is no matching
battery-only regulator snapshot yet.

The owner also reported that a short power-key press turned the screen off and
a second short press restored the screen and keyboard. The journal for that
boot confirms `PM: suspend entry (deep)` and `PM: suspend exit`, so the
power-key suspend/resume path completed. See test 166. Test 169 separately
reports that a short power-key press did not start the tablet while Type-C was
disconnected after poweroff; this is a battery-only startup result, not a
suspend/resume result. It was only a short press, so it does not establish
whether a sustained power-key hold starts the tablet on battery.

## Diagnostic changes

The initramfs now writes `GTS9_BOOT_STAGE=...` and `GTS9_BOOT_FAIL=...` to
`/dev/kmsg` at the userspace, framebuffer-control, microSD, mount, and rootfs
handoff boundaries. If handoff fails and tty1 is available, the rescue screen
shows the failure reason and last completed stage. The framebuffer stage means
the blank-control interface exists; it does not claim the panel is physically
lit.

After the root filesystem mounts, each stage atomically updates
`/var/log/gts9-last-boot-stage` with the boot ID, command line, rootfs state,
MMC devices, SD regulator consumers, and recent MMC log messages. Debian
systemd units then append `systemd-basic` and the tty1 getty result. If a boot
fails before the card can be mounted, that file cannot be updated; compare its
boot ID with the current boot before treating it as evidence for that attempt.

The optional Debian power-off marker is
`/var/log/gts9-last-poweroff-stage`. Its unit runs immediately before
`systemd-poweroff.service`, after `umount.target`, and atomically replaces the
marker file. A matching boot ID proves only that systemd reached that final
service. The subsequent standard systemd shutdown path performs its own
filesystem sync; the marker service adds no extra sync. The record does not
prove that the kernel called PSCI `SYSTEM_OFF` or that PMIC power was removed.

Install the Debian-side units and the existing short-power-key suspend policy
on a mounted Debian root filesystem with:

```sh
sudo scripts/install-rootfs-diagnostics.sh /path/to/debian-rootfs
```

The rootfs copy is separate from the initramfs build. Nothing in this change
alters regulator voltages, charger settings, SM5714/PTN3222 state, the SD
power sequence, display timing, or the kernel power-off handler.

## Next hardware observations

The notes in this section were written while test 172's candidate was on the
device and are kept as the record of that session.  Test 179 later ran the
power-off A/B on the current image; its numbers are in the correction section
at the top and in `reference/boot-tests/test-179-20260924T000935Z/`.

Two host-built bundles are available locally. `out/boot-power-diag` passed
validation with rootfs stage markers; it was not flashed during test 169. The
newer `out/boot-power-trace` also passed
`scripts/validate-boot-bundle.sh`, using
`boot/cmdline.boot-trace.example.txt`. Its `init_boot.img` contains the opt-in
tty0 report trace and its `vendor_boot.img` carries the diagnostic cmdline. The
new bundle has SHA-256 values:

```text
boot.img       a9d44cc746c2fdcc17e0040ec6b42120d82ba0b271c42fa2bd62e61d4d435ace
init_boot.img  7d934eac278f9818132764215110b7c58226a31831ca7a7f86ffdc0a7244b24c
vendor_boot.img 762032503b38a134863b8cb047127390165fc9f20763a010fe1893ad3aeba247
dtbo.img       c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
vbmeta.img     b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4
```

Relative to the earlier local `out/boot-power-diag` bundle, only init_boot
and vendor_boot differ; the kernel and DTB payloads are unchanged. The
repository-generated vbmeta disables AVB and must not replace the device's
existing vbmeta. Preserve current partition backups and verify read-back hashes
before any device test.

The device is still at the early-display screen, so the added trace has not yet
been observed. On the next authorized boot, record which
`GTS9_BOOT_REPORT_BEGIN` marker is last on the panel; a missing matching END
marker will identify the report read that failed to return. If every report
finishes, the rootfs stage markers will distinguish MMC wait, root mount, and
handoff. First reproduce with Type-C connected, then compare a controlled
battery-only start. For poweroff, the systemd marker already proves entry into
the final service; a direct kernel trace still requires a usable `ttyMSM0`
capture or a separately validated persistent-kernel-log mechanism. Do not
infer a microSD or regulator fault from this screen alone.

During this session the owner reconfirmed that the panel still showed the
same two early-console lines. A read-only COM17 capture attempt opened the
port for six seconds and received no matching boot-stage or rootfs lines. This
does not reveal the stalled command because this boot lacks the opt-in report
trace. The supplied photo has the same image hash recorded for test 169, so it
adds no new boot-stage evidence. The next meaningful read is from a boot using
the staged `gts9_boot_trace_console=1` initramfs; do not infer a new failure
from the silent serial interval alone.

For a later poweroff trial, the diagnostic-only
`kernel/patches/diagnostic/0020-gts9-poweroff-path-trace.patch` can be enabled
with `GTS9_POWEROFF_TRACE=1` during an isolated kernel build and the
`boot/cmdline.poweroff-trace.example.txt` profile. With the command-line flag
also enabled, it records Linux shutdown boundaries, sys-off callback symbols
and priorities, and the point immediately before PSCI `SYSTEM_OFF`; if the SMC
returns, it records the return value. It flushes that last marker before
entering firmware and can add up to one second to the diagnostic attempt. The
patch is not part of the default queue, does not alter the poweroff handler,
and has not been flashed or tested on the device. A pre-call marker proves the
Linux callback reached the SMC boundary, not that firmware powered the device
off.

Test 179 has since exercised it on hardware: the flashed `boot` partition
(`822ca9dc…`) was already a `GTS9_POWEROFF_TRACE=1` build, and the only change
was a rebuilt `vendor_boot` whose command line adds `gts9_poweroff_trace=1`
and `console=tty0`, so every trace line reaches the panel as well as the
`sec_log` ring.  One limitation matters for reading the result: the `sec_log`
ring lives in DRAM, so a *successful* power off destroys the copy.  The trace
is only recoverable after a power-off attempt that leaves the SoC running (and
then only through TWRP's `/proc/last_kmsg`); the panel is the working sink for
a successful one, and the ABL `lpcharge=` flag is the host-visible proof that
power was actually removed.

The separate host-built `out/boot-poweroff-trace` bundle passed
`scripts/validate-boot-bundle.sh` against its diagnostic cmdline and matching
kernel output. Its kernel release is `7.2.0-rc3-gts9wifi-dirty`; image hashes
are:

```text
boot.img       822ca9dcf404de83e79f085a5509ec761bf0234359a5fae166c5d1c849e1df86
init_boot.img  7d934eac278f9818132764215110b7c58226a31831ca7a7f86ffdc0a7244b24c
vendor_boot.img 09bd4bea84d5a0477652002f6e4cd66091b4536f1cd7eb3d5d1a5bf45b2eb61b
dtbo.img       c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3
vbmeta.img     b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4
```

Only `boot.img`, `init_boot.img`, and `vendor_boot.img` contain the diagnostic
kernel, initramfs, and cmdline. The generated `vbmeta.img` disables AVB and
must not replace the device's existing vbmeta. The bundle is local and has not
been flashed.

Do not change the SD rails, PMIC/charger configuration, USB PHY, or display
sequence based only on the cursor. The next change should follow a stage or
kernel trace that localizes the failing transition.
