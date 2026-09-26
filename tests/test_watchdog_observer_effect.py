import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

APPLIER = "rootfs-overlay/usr/libexec/gts9-watchdog-debug"
APPLIER_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-watchdog-debug.service"
MIRROR = "rootfs-overlay/usr/libexec/gts9-kmsg-console"
MIRROR_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-kmsg-console.service"
FLIGHT_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-dpu-flight.service"
ENABLE_UNITS = "rootfs-overlay/usr/libexec/gts9-enable-units"
ACM_GETTY_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-acm-getty.service"

WATCHDOG_FLAG = "gts9_watchdog_debug=1"
MIRROR_FLAG = "gts9_kmsg_mirror=1"
FLIGHT_FLAG = "gts9_dpu_flight=1"


def read(rel):
    return (ROOT / rel).read_text()


def code_only(text):
    """Directives/commands only: the comments in these files explain the very
    mistakes the tests check for, so prose must not satisfy or defeat a check."""
    return "\n".join(
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


class WatchdogObserverEffectTests(unittest.TestCase):
    """The instrumentation must not load the system it is measuring.

    Measured 2026-09-24: every one of the watchdog report's 28 lines carried the
    same journal timestamp [4.646574] while the unit's ExecMainExit was at
    155.87 s, i.e. the helper was blocked ~151 s writing the same text to
    /dev/console -> tty0 -> fbcon -> DRM.  These tests pin the fixes.
    """

    def test_applier_unit_is_journal_only(self):
        unit = read(APPLIER_UNIT)
        self.assertIn("StandardOutput=journal\n", unit)
        self.assertNotIn("journal+console", code_only(unit))

    def test_applier_does_not_print_the_whole_report_by_default(self):
        applier = read(APPLIER)
        # The full report is written to a file and only `status` cats it.
        status_branch = code_only(applier[applier.index("status)") :])
        apply_branch = code_only(applier[applier.index("apply)") : applier.index("off)")])
        self.assertIn('cat "$REPORT"', status_branch)
        self.assertNotIn('cat "$REPORT"', apply_branch)
        self.assertIn("summary_line", apply_branch)
        # ... and the summary really is one short line.
        summary = applier[applier.index("summary_line() {") :]
        summary = summary[: summary.index("\n}")]
        self.assertEqual(summary.count("echo "), 1)

    def test_every_step_has_begin_end_and_monotonic_duration(self):
        applier = read(APPLIER)
        self.assertIn('trace "BEGIN $label"', applier)
        self.assertIn('trace "END $label"', applier)
        self.assertIn("duration_ms=$duration", applier)
        self.assertIn("start_ms=$start end_ms=$end", applier)
        # Time comes from /proc/uptime, never from the wall clock.
        self.assertIn("/proc/uptime", applier)
        self.assertNotIn("date +%s", applier)

    def test_trace_lives_in_run_and_is_archived_once(self):
        applier = read(APPLIER)
        self.assertIn("TRACE=/run/gts9-watchdog-debug.trace", applier)
        self.assertIn("TRACE_ARCHIVE=/var/log/gts9-watchdog-debug.trace", applier)
        # One copy after the run, i.e. no fsync per sysctl.
        copies = re.findall(r'cp "\$TRACE" "\$TRACE_ARCHIVE"', applier)
        self.assertEqual(len(copies), 3)  # apply, off, status
        # No per-sysctl fsync/sync: the only persistence is that single copy.
        self.assertNotIn("\nsync\n", code_only(applier))
        self.assertNotIn("fsync", code_only(applier))

    def test_three_instrumentation_switches_are_independent(self):
        applier = code_only(read(APPLIER))
        mirror = code_only(read(MIRROR))
        flight = read(FLIGHT_UNIT)
        self.assertIn(WATCHDOG_FLAG, applier)
        self.assertNotIn(MIRROR_FLAG, applier)
        self.assertNotIn(FLIGHT_FLAG, applier)

        self.assertIn(MIRROR_FLAG, mirror)
        self.assertNotIn(WATCHDOG_FLAG, mirror)
        self.assertIn(f"ConditionKernelCommandLine={MIRROR_FLAG}", read(MIRROR_UNIT))
        # The mirror must never write to /dev/console: that is the blocking
        # writer docs/BOOT_CONSOLE_BLOCK.md describes.  Since 2026-09-26 there is
        # no login shell on the gadget and no ttyGS kernel console either, so the
        # port is now chosen for the host's first COM handle rather than to keep
        # printk off a shell's port - but /dev/console must stay out of it, and
        # the mirror itself must stay off the USB console path entirely.
        mirror_unit = code_only(read(MIRROR_UNIT))
        self.assertIn("gts9-kmsg-console /dev/ttyGS0", mirror_unit)
        self.assertNotIn("/dev/console", mirror_unit)
        self.assertNotIn("/dev/console", mirror)

        self.assertIn(f"ConditionKernelCommandLine={FLIGHT_FLAG}", flight)

    def test_known_good_profiles_enable_none_of_them(self):
        for name in ("boot/cmdline.example.txt", "boot/cmdline.minimal-rootfs.example.txt",
                     "boot/cmdline.poweroff-trace.example.txt", "boot/cmdline.boot-trace.example.txt"):
            text = read(name)
            with self.subTest(cmdline=name):
                for flag in (WATCHDOG_FLAG, MIRROR_FLAG, FLIGHT_FLAG):
                    self.assertNotIn(flag, text)

    def test_tty1_is_never_touched_by_the_tty_policy(self):
        helper = read(ENABLE_UNITS)
        self.assertNotIn("getty@tty1", helper)
        self.assertIn("serial-getty@ttyMSM0.service", helper)

    def test_every_serial_getty_is_masked_and_none_is_enabled(self):
        """The policy changed on 2026-09-26: everything serial is masked.

        It used to hand ttyGS0 to a dedicated gts9-acm-getty.service and mask only
        ttyMSM0.  Both are gone now - the tablet is reached over ssh - so the
        helper must mask all three names and enable no serial login at all.
        """
        helper = read(ENABLE_UNITS)
        # The removed unit's enable link goes away, and its name is masked so a
        # stale copy in /etc (which wins over /usr/lib) cannot start it.
        self.assertIn(
            'rm -f "$etc_dir/multi-user.target.wants/gts9-acm-getty.service"', helper)
        self.assertIn('ln -sfn /dev/null "$etc_dir/gts9-acm-getty.service"', helper)
        # No serial getty instance is enabled, and every one is masked.
        for dev in ("ttyGS0", "ttyMSM0"):
            self.assertIn(
                f'rm -f "$etc_dir/getty.target.wants/serial-getty@{dev}.service"', helper)
            self.assertIn(f'ln -sfn /dev/null "$etc_dir/serial-getty@{dev}.service"', helper)
        masks = sorted(re.findall(r'ln -sfn /dev/null "\$etc_dir/([^"]+)"', helper))
        self.assertEqual(masks, ["gts9-acm-getty.service",
                                 "serial-getty@ttyGS0.service",
                                 "serial-getty@ttyMSM0.service"])
        # The unit that used to carry the autologin is gone from the overlay.
        self.assertFalse((ROOT / ACM_GETTY_UNIT).exists(),
                         "the ttyGS0 autologin getty is the 90 s poweroff")

    def test_no_serial_console_survives_on_a_known_good_cmdline(self):
        """Suppressing the userspace getty is not enough: the kernel console went too.

        This test used to assert the opposite - that ttyMSM0 plus earlycon stayed
        on the command line.  Both serial debug consoles were removed on
        2026-09-26 (docs/BOOT_CONSOLE_BLOCK.md, docs/SHUTDOWN_DELAY.md), so the
        assertion is inverted: exactly one console, and it is the panel.
        """
        helper = code_only(read(ENABLE_UNITS))
        self.assertNotIn("console=ttyMSM0", helper)
        for name in ("boot/cmdline.minimal-rootfs.example.txt",
                     "boot/cmdline.example.txt"):
            with self.subTest(cmdline=name):
                toks = read(name).split()
                self.assertIn("console=tty0", toks)
                self.assertEqual([t for t in toks if t.startswith("console=")],
                                 ["console=tty0"])
                for gone in ("console=ttyMSM0,115200n8", "console=ttyGS1", "earlycon"):
                    self.assertNotIn(gone, toks)

    def test_pstore_backend_and_records_are_reported_separately(self):
        applier = read(APPLIER)
        self.assertIn("PSTORE_BACKEND=ramoops-registered", applier)
        self.assertIn("pstore_backend=$PSTORE_BACKEND", applier)
        self.assertIn("pstore_records=$PSTORE_RECORDS", applier)
        self.assertIn("Registered ramoops as persistent store backend", applier)
        # An empty /sys/fs/pstore must not be reported as "no backend".
        self.assertNotIn('pstore_backend=absent (/sys/fs/pstore empty', applier)

    def test_a_helper_failure_cannot_block_the_boot(self):
        unit = read(APPLIER_UNIT)
        applier = read(APPLIER)
        self.assertIn("TimeoutStartSec=30", unit)
        self.assertIn("Type=oneshot", unit)
        self.assertIn("SuccessExitStatus=", unit)
        self.assertNotIn("Requires=", unit)
        self.assertIn("exit 0", applier)
        self.assertIn("set -u", applier)
        self.assertNotIn("set -e", applier)


if __name__ == "__main__":
    unittest.main()
