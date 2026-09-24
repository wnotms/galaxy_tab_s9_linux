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
        # The mirror must never write to the login shell's port.
        self.assertIn("gts9-kmsg-console /dev/ttyGS1", code_only(read(MIRROR_UNIT)))

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

    def test_ttygs0_is_handed_to_a_dedicated_unit_not_masked(self):
        helper = read(ENABLE_UNITS)
        unit = read(ACM_GETTY_UNIT)
        # The generic instance's enable link goes away...
        self.assertIn("rm -f \"$etc_dir/getty.target.wants/serial-getty@ttyGS0.service\"", helper)
        # ... but nothing masks ttyGS0, and only ttyMSM0 is masked.
        self.assertNotIn("serial-getty@ttyGS0.service\" ]", helper)
        masks = re.findall(r"ln -s /dev/null \"\$etc_dir/([^\"]+)\"", helper)
        self.assertEqual(masks, ["serial-getty@ttyMSM0.service"])
        # The replacement starts after the gadget exists, with autologin, and
        # carries no device dependency of its own.
        self.assertIn("After=gts9-usb-acm.service", unit)
        self.assertIn("--autologin root", unit)
        self.assertNotIn("dev-ttyGS0.device", code_only(unit))

    def test_ttymsm0_stays_a_kernel_console(self):
        """Suppressing the userspace getty must not touch the kernel console."""
        helper = code_only(read(ENABLE_UNITS))
        self.assertNotIn("console=ttyMSM0", helper)
        for name in ("boot/cmdline.minimal-rootfs.example.txt",):
            self.assertIn("console=ttyMSM0,115200n8", read(name))
            self.assertIn("earlycon", read(name))

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
