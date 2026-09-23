import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PoweroffTraceProfileTests(unittest.TestCase):
    def test_default_cmdline_does_not_enable_diagnostics(self):
        cmdline = (ROOT / "boot/cmdline.example.txt").read_text()
        self.assertNotIn("gts9_poweroff_trace=", cmdline)
        self.assertNotIn("gts9_boot_trace_console=1", cmdline)

    def test_diagnostic_cmdline_keeps_serial_as_console_device(self):
        cmdline = (ROOT / "boot/cmdline.poweroff-trace.example.txt").read_text()
        self.assertIn("gts9_boot_trace_console=1", cmdline)
        self.assertIn("gts9_poweroff_trace=1", cmdline)
        consoles = [word for word in cmdline.split() if word.startswith("console=")]
        self.assertEqual(consoles, ["console=tty0", "console=ttyMSM0,115200n8"])

    def test_kernel_patch_is_opt_in_and_marks_psci_boundary(self):
        prepare = (ROOT / "scripts/prepare-kernel.sh").read_text()
        patch = (ROOT / "kernel/patches/diagnostic/0020-gts9-poweroff-path-trace.patch").read_text()
        self.assertIn('poweroff_trace=${GTS9_POWEROFF_TRACE:-0}', prepare)
        self.assertIn('if [ "$poweroff_trace" = 1 ]; then', prepare)
        self.assertIn('early_param("gts9_poweroff_trace"', patch)
        self.assertIn("GTS9_POWER_OFF: PSCI SYSTEM_OFF call", patch)
        self.assertIn("GTS9_POWER_OFF: PSCI SYSTEM_OFF returned", patch)


if __name__ == "__main__":
    unittest.main()
