# Test250 registration: unchanged production warm-reboot stability

## One question

While the accepted Test249 production software remains unchanged, do 20
consecutive ordinary Debian warm reboots expose CPU non-response, panic,
RCU/CSD/soft-lockup or another startup stability failure? This is bounded
regression of the warm-reboot path, not a performance test, failure-rate
estimate or new root-cause experiment. No cold, battery-only or Type-C power
transition is included.

## Locked baseline and permitted action

The accepted source is Test249 `RESULTS.md` and `SHA256.json`, not the older
Test245–248 next-step notes or Test249's pre-run registration. Linux remains
the pinned 7.2-rc3 build, `CONFIG_HVC_DCC=n`, with the production boot and
vendor_boot pair and its 181-file module directory. The Test249 final embedded
config SHA-256 is `95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`;
the kernel notes SHA-256 is
`dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`.
The five partition and 181 module hashes are loaded from the manifest-verified
Test249 final files, never guessed from a build directory. Test249's exact
config identity is the gate; `HVC_DRIVER` need not appear as an unset Kconfig
line. The DCC write symbols, `/dev/hvc0`, `/sys/class/tty/hvc0` and active
`serial-getty@hvc0.service` must be absent. Runtime watchdog, soft watchdog,
softlockup panic, panic and ramoops ECC remain production zeros. Temporary
pseudo-NMI, CSD, last-activity, BBM and ECC diagnostics remain absent.

No kernel, config, DTB, modules, rootfs service, cmdline, watchdog, panic,
USB gadget, power, regulator, clock, OPP, CPU-idle or GPU change is permitted.
No image is built or flashed. The runner writes evidence only on the host;
its sole device-changing command is the owner's requested `systemctl reboot`
once per round after a clean source-boot gate. There is no rollback action
because nothing is flashed or reconfigured. If the device no longer matches
Test249, stop without repair or overwrite.

## Registered execution

Use `scripts/production-reboot-stability.sh preflight` to record the current
boot ID, uname, cmdline, uptime, embedded config, kernel notes, full five
partition hashes, all 181 module hashes, DCC/diagnostic absence, kernel
journal, failed units, Windows ADB, USB gadget/NCM state, Windows PnP state,
SSH banner and authenticated read-only shell. This registration, runner and
host tests must be committed and pushed to `origin/test` before any reboot.
The accepted preflight must be committed and pushed to `origin/test`, and it
must refer to the same boot that starts round 01. A stale or changed boot
stops before any reboot.

Use `scripts/production-reboot-stability.sh run` for exactly **20 rounds**.
For each round, capture the current boot's identity, journal and boot list,
then issue one ordinary `systemctl reboot`. A disconnected command alone is
not a successful reboot. The new Debian boot ID must differ, and persistent
journal history must show exactly one new boot after the source boot. Source
and new-boot journals are saved separately. The new boot must first answer
ADB by uptime 60 s and remain observable until at least uptime **150 s**,
with 5 s identity polls and a live kernel-journal follow.
Live complete journal rows are checked at every poll; a fault stops observation
without waiting for 150 s. Boot attribution and the just-ended target's full
shutdown journal are checked as soon as the new boot answers. Full journals
must contain the source-time-zero Linux-version record, not only later rows.
Windows USB problem codes are checked periodically during the window.
ADB wait is bounded to 180 s. On expiry, preserve host USB/PnP and any reachable device evidence
and stop. No round may be repeated or evidence overwritten automatically.

Each `round-NN/` retains `before-boot-id.txt`, `after-boot-id.txt`,
`boots-before.txt`, `boots-after.txt`, `uname.txt`,
`cmdline.txt`, `uptime.txt`, full `kernel-journal.txt`, full
`kernel-journal-json.txt` with source timestamps, `systemd-failed.txt`,
`dcc-state.txt`, `adb-state.txt`, `ssh-state.txt`, `usb-state.txt`, Windows
USB/banner captures, command status files and `verdict.json`. The source
boot's snapshots use `before-`; unprefixed snapshots refer to the new boot.
The source boot's final journals are `ended-target-kernel-journal-json.txt`
and `ended-target-kernel-journal.txt`; the new
boot's complete journal and live follow are separate files.

Only an attributed boot with the same production config/notes, DCC absent,
150 s responsive window, complete source-timestamped kernel journal, no
kernel failure/suspect, no failed systemd unit, Windows ADB and SSH/NCM
available is `clean`. Kernel CPU-stall, RCU/CSD, panic, Oops, hung-task and
workqueue-lockup signatures are failures. New priority-3/error messages,
unexpected backtraces or missing evidence are suspect. The exact previously
accepted Test249 priority-3 messages are retained as known baseline warnings;
the known `aux_bridge` missing-PS5169 and `regulator_ignore_unused` warnings
are not treated as DCC failures. Test249's specific `update_config` clock
warning trace is also distinguished from an unexpected new backtrace. Raw
journals are always saved; any allowlisted warning is counted in the verdict.

Windows NCM/TCP is tried at most three times, 10 s apart, without changing
the USB configuration. First failure and recovery timestamps and recovery
duration are recorded. An initial failure that recovers in the same boot is
`usb-transient`, **not clean**, and stops the series. Windows Code43 stops the
series and triggers Windows PnP plus device-side gadget/DWC3 capture where
possible; it is not called a CPU wedge. ADB and SSH both unavailable,
unexplained reboot, nonmatching identity, incomplete attribution or any
other unclassified suspect also stops on the first occurrence. No automatic
diagnostic profile is enabled.

If all 20 rounds are clean, a separate final read-only acceptance repeats
boot ID, uptime, all five partition hashes, embedded config, notes, all 181
module hashes, DCC absence, complete journal, systemd, ADB and NCM/SSH gates.
`summary.json` and `RESULTS.md` record the bounded conclusion. Test251 may be
proposed there for cold/power-path coverage, but must not be run in Test250.

Test247 proves one natural CPU4 DCC TX-busy spinlock path; Test250 cannot
prove that all historical wedges shared it or that future failures are
impossible. On first non-clean result, preserve that boot and decide any new
diagnostic design only after offline review.
