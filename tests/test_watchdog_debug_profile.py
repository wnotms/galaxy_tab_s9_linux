import hashlib
import re
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

# The profiles that must stay exactly as they were: this change adds a *new*
# profile, it does not touch the known-good boot.
KNOWN_GOOD_CMDLINES = {
    "boot/cmdline.example.txt": "40c7d153b0bb74931297b1c300392406a664b2a34fedc517ca5a0b2df3ee8e03",
    "boot/cmdline.minimal-rootfs.example.txt": "0d5904d95d761819002bba1e4f04d4210a31dce702bb5d16487744e6d2651ea4",
    "boot/cmdline.poweroff-trace.example.txt": "d7d07e45166c5f3934d1fb8a8f36ec3d07d7a523a7f7296bd9582e22f7f403e0",
    "boot/cmdline.boot-trace.example.txt": "f3aa80f29bbdd0b29f9dc727408c04cae38dd53b17b6d02e6356e2cf484d4dc7",
}

DEBUG_CMDLINE = "boot/cmdline.watchdog-debug.example.txt"
DEBUG_FLAG = "gts9_watchdog_debug=1"

# Parameters that may only ever appear in the watchdog debug profile's command
# line.  These have real early parameters in this kernel.
CMDLINE_PROFILE_ONLY = (
    "softlockup_panic=",
    "workqueue.panic_on_stall_time=",
    DEBUG_FLAG,
)

# Knobs with *no* early parameter in this kernel: kernel/hung_task.c registers
# none for hung_task_panic/hung_task_timeout_secs, and watchdog.c registers none
# for softlockup_all_cpu_backtrace.  They can only be armed from the runtime
# applier, so they must never be written into a command line where they would
# look effective but be ignored.
RUNTIME_ONLY = (
    "kernel.hung_task_panic",
    "kernel.hung_task_timeout_secs",
    "kernel.softlockup_all_cpu_backtrace",
    "workqueue.panic_on_stall",
)

APPLIER = "rootfs-overlay/usr/libexec/gts9-watchdog-debug"
COLLECTOR = "rootfs-overlay/usr/libexec/gts9-prev-boot-evidence"
APPLIER_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-watchdog-debug.service"
COLLECTOR_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-prev-boot-evidence.service"
DTS = "kernel/dts/sm8550-samsung-gts9wifi.dts"


def read(rel):
    return (ROOT / rel).read_text()


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


class WatchdogDebugProfileTests(unittest.TestCase):
    """Phase 1 of the X710 stall-recovery work: software watchdogs only."""

    def test_no_profile_asks_for_nowatchdog(self):
        """`nowatchdog` is ABL's, and the debug profile must undo it at runtime.

        The vendor_boot command line cannot remove it: ABL appends its own tail
        (msm_rtb.enable=0 nowatchdog ...) after the values built here, and the
        kernel only offers off switches (nowatchdog, nosoftlockup).  So no
        profile may *add* it, and the debug profile must re-arm the detector
        through /proc/sys/kernel/watchdog instead.
        """
        for name in list(KNOWN_GOOD_CMDLINES) + [DEBUG_CMDLINE]:
            with self.subTest(cmdline=name):
                self.assertNotIn("nowatchdog", read(name))
        applier = read(APPLIER)
        self.assertIn("/proc/sys/kernel/watchdog", applier)
        self.assertIn("proc_watchdog_update", applier)

    def test_known_good_profiles_are_unchanged(self):
        for name, digest in KNOWN_GOOD_CMDLINES.items():
            with self.subTest(cmdline=name):
                self.assertEqual(sha256(name), digest)
                text = read(name)
                self.assertNotIn(DEBUG_FLAG, text)
                for param in CMDLINE_PROFILE_ONLY:
                    self.assertNotIn(param, text)

    def test_debug_profile_keeps_the_panic_reboot(self):
        debug = read(DEBUG_CMDLINE)
        self.assertIn("panic=10", debug)
        self.assertNotIn("panic=0", debug)
        # panic=10 is what turns a detected stall into an unattended reboot;
        # every known-good profile keeps its own value untouched.
        self.assertIn("panic=", debug)

    def test_watchdog_parameters_live_only_in_the_debug_profile(self):
        debug = read(DEBUG_CMDLINE)
        for param in CMDLINE_PROFILE_ONLY:
            with self.subTest(param=param):
                self.assertIn(param, debug)
        for name in KNOWN_GOOD_CMDLINES:
            text = read(name)
            for param in CMDLINE_PROFILE_ONLY:
                with self.subTest(cmdline=name, param=param):
                    self.assertNotIn(param, text)

    def test_runtime_only_knobs_are_not_pretended_on_the_command_line(self):
        """The hung-task detector has no early parameter in this kernel.

        Writing `hung_task_panic=1` into a command line would look authoritative
        in a record and do nothing at all, so the applier owns these knobs and
        no cmdline file may mention them.
        """
        applier = read(APPLIER)
        for knob in RUNTIME_ONLY:
            with self.subTest(knob=knob):
                self.assertIn(knob, applier)
        for name in list(KNOWN_GOOD_CMDLINES) + [DEBUG_CMDLINE]:
            text = read(name)
            for knob in ("hung_task_panic", "hung_task_timeout_secs"):
                with self.subTest(cmdline=name, knob=knob):
                    self.assertNotIn(knob, text)

    def test_before_the_image_is_flashed_the_applier_is_inert(self):
        """The unit is enabled everywhere; without the flag it must do nothing.

        That is what keeps the profile out of the known-good boot: the applier
        checks the command line first and exits 0 without touching a sysctl.
        """
        applier = read(APPLIER)
        self.assertIn("gts9_watchdog_debug=1", applier)
        self.assertIn("has_flag", applier)
        self.assertIn("not on the command line; nothing to do", applier)
        self.assertIn("--force", applier)  # bring-up override, documented

    def test_no_guessed_hardware_or_watchdog_dts_node(self):
        """Phase 1 is software only: no MMIO, no new device-tree node."""
        for name in (APPLIER, COLLECTOR):
            text = read(name)
            for forbidden in ("devmem", "/dev/mem", "i2cset", "i2cget", "0x1c", "regmap"):
                with self.subTest(file=name, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)
        dts = read(DTS)
        for forbidden in ("watchdog@", "wdt@", "qcom,kpss-wdt", "qcom,msm-watchdog"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, dts)

    def test_runtime_watchdog_is_not_armed_by_default(self):
        """No unit may pet or require /dev/watchdog0 before it has been proven.

        /dev/watchdog0 does not exist on this port (no qcom_wdt instance,
        CONFIG_SOFT_WATCHDOG is not set), so RuntimeWatchdogSec would either be
        a no-op or, worse, a boot-blocking failure.  Probing for the device is
        fine - writing to it, or asking systemd to arm it, is not.
        """
        import re

        for name in (APPLIER, COLLECTOR, APPLIER_UNIT, COLLECTOR_UNIT):
            with self.subTest(file=name):
                text = read(name)
                self.assertIsNone(
                    re.search(r">\s*/dev/watchdog", text),
                    f"{name} writes to a watchdog device",
                )
                self.assertNotIn("RuntimeWatchdogSec", text)
                self.assertNotIn("RebootWatchdogSec", text)
        self.assertFalse((ROOT / "rootfs-overlay/etc/systemd/system.conf.d").exists())
        # The collector is expected to *report* the device's absence.
        self.assertIn("/dev/watchdog*", read(COLLECTOR))

    def test_a_profile_failure_cannot_block_the_boot(self):
        """The applier is best-effort: oneshot, after local-fs, exit 0 always."""
        applier = read(APPLIER)
        self.assertIn("exit 0", applier)
        self.assertIn("set -u", applier)
        self.assertNotIn("set -e", applier)
        # Unsupported knobs are reported, not fatal.
        self.assertIn("unsupported", applier)
        unit = read(APPLIER_UNIT)
        self.assertIn("Type=oneshot", unit)
        self.assertIn("WantedBy=multi-user.target", unit)
        self.assertIn("SuccessExitStatus=", unit)
        self.assertIn("TimeoutStartSec=", unit)
        # A failure in a multi-user.target unit cannot hold up sysinit/basic.
        self.assertNotIn("Before=sysinit.target", unit)
        self.assertNotIn("Before=basic.target", unit)
        self.assertNotIn("Requires=", unit)

    def test_stall_thresholds_stay_in_the_documented_window(self):
        """30-60 s: long enough for boot latency, short enough to be unattended."""
        applier = read(APPLIER)
        self.assertIn("HUNG_TASK_TIMEOUT=45", applier)
        self.assertIn("WQ_PANIC_ON_STALL_TIME=45", applier)
        for tiny in ("=1 ", "=2 ", "=3 "):
            self.assertNotIn(f"HUNG_TASK_TIMEOUT{tiny}", applier)
            self.assertNotIn(f"WQ_PANIC_ON_STALL_TIME{tiny}", applier)
        # panic_on_stall is the cumulative counter and must stay off: a stall
        # hunt must not reboot on the first transient workqueue report.
        self.assertIn("parameters/panic_on_stall 0", applier)

    def test_evidence_collector_targets_the_previous_boot(self):
        collector = read(COLLECTOR)
        self.assertIn("journalctl -b -1", collector)
        self.assertIn("verdict.txt", collector)
        self.assertIn("stream-prev-tail.txt", collector)
        # It must run before the trace recorder rotates its own files.
        self.assertIn("Before=multi-user.target gts9-dpu-flight.service", read(COLLECTOR_UNIT))

    def test_pstore_records_are_archived_every_boot(self):
        """The panic report only exists in pstore, so it must be copied early.

        journald is not running when the kernel panics; the ramoops console
        buffer is the only place the report survives the reset, and pstore
        records disappear as soon as a reader deletes them.
        """
        collector = read(COLLECTOR)
        self.assertIn("/sys/fs/pstore", collector)
        self.assertIn("pstore_records=", collector)
        self.assertIn("pstore_panic_lines=", collector)

    def test_ramoops_region_is_stock_evidence_not_a_guess(self):
        """The pstore carve-out address and size come from the live X710 tree.

        reference/stock's decompiled live DTS reserves 0x8_80900000 for 2 MiB
        as sec_pmsg_region and binds samsung,pstore_pmsg to it; the mainline
        ramoops node reuses exactly that reservation.
        """
        dts = read(DTS)
        self.assertIn('compatible = "ramoops";', dts)
        self.assertIn("ramoops@880900000", dts)
        self.assertIn("reg = <0x8 0x80900000 0x0 0x200000>;", dts)
        # The three sub-buffers must fit the 2 MiB carve-out exactly once.
        sizes = [
            int(v, 16)
            for v in re.findall(r"^\s*(?:record|console|pmsg)-size = <0x([0-9a-f]+)>;", dts, re.M)
        ]
        self.assertEqual(len(sizes), 3)
        self.assertLessEqual(sum(sizes), 0x200000)
        # And the node must say where the numbers came from.
        self.assertIn("7bf40be5", dts)  # live DTS digest, in the comment
        # The old sec-pmsg node name must be gone, not duplicated.
        self.assertNotIn("sec-pmsg@880900000", dts)

    def test_sec_log_console_stays(self):
        """ramoops is added alongside Samsung's ring, not instead of it."""
        dts = read(DTS)
        self.assertIn("sec-log@880200000", dts)
        self.assertIn("samsung,gts9wifi-sec-kernel-log", dts)


if __name__ == "__main__":
    unittest.main()
