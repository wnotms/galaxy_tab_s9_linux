"""Host checks for the opt-in RPMh timeout diagnostic (patch 0021).

The diagnostic is the one new variable test-186 introduces, so its contract is
pinned here: it stays opt-in, it changes no RPMh semantics, it captures the
fields the stall investigation needs, and a normal build never contains it.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH = ROOT / "kernel/patches/diagnostic/0021-gts9-rpmh-timeout-state-dump.patch"
README = ROOT / "kernel/patches/diagnostic/README.md"
PREPARE = ROOT / "scripts/prepare-kernel.sh"
CMDLINE = ROOT / "boot/cmdline.rpmh-debug.example.txt"
FRAGMENT = ROOT / "kernel/config/gts9wifi-mainline.fragment"


def patch_text():
    return PATCH.read_text()


class RpmhDebugPatchTests(unittest.TestCase):
    def test_patch_touches_only_the_rpmh_files(self):
        files = re.findall(r"^\+\+\+ b/(\S+)$", patch_text(), re.M)
        self.assertEqual(sorted(files), [
            "drivers/soc/qcom/rpmh-internal.h",
            "drivers/soc/qcom/rpmh-rsc.c",
            "drivers/soc/qcom/rpmh.c",
        ])

    def test_it_is_opt_in_at_build_time_and_at_runtime(self):
        self.assertIn("rpmh_debug=${GTS9_RPMH_DEBUG:-0}", PREPARE.read_text())
        self.assertIn('0021-gts9-rpmh-timeout-state-dump.patch', PREPARE.read_text())
        self.assertIn("early_param(\"gts9_rpmh_debug\"", patch_text())
        self.assertIn("gts9_rpmh_debug", CMDLINE.read_text())
        # The default build is the fragment: the diagnostic must not be a
        # Kconfig symbol there, only a patch that has to be asked for.
        self.assertNotIn("RPMH_DEBUG", FRAGMENT.read_text())

    def test_the_heavy_instrumentation_is_off_in_the_test_186_profile(self):
        cmdline = CMDLINE.read_text()
        self.assertIn("gts9_rpmh_debug=1", cmdline)
        self.assertIn("gts9_watchdog_debug=1", cmdline)
        self.assertIn("console=ttyGS1", cmdline)
        self.assertNotIn("gts9_kmsg_mirror", cmdline)
        self.assertNotIn("gts9_dpu_flight", cmdline)
        self.assertNotIn("gts9_poweroff_trace", cmdline)
        # bring-up consoles stay
        self.assertIn("console=ttyMSM0,115200n8", cmdline)
        self.assertIn("earlycon", cmdline)

    def test_dump_captures_the_fields_the_investigation_needs(self):
        text = patch_text()
        for needle in (
            "dev_name(dev)",              # calling device (rpmh.c side)
            "rsc=%s",                     # RSC controller name
            "state=%u",                   # RPMh state
            "cmds=%u",                    # batch command count
            "addr=0x%08x data=0x%08x wait=%u",   # per-command detail
            "tcs_in_use=0x%08lx",         # in-use bitmap
            "irq_status=0x%08lx",         # RSC IRQ status
            "irq_enable=0x%08x",          # IRQ mask for the decision tree
            "cmd_enable=0x%08x",          # per-TCS registers
            "wait_for_cmpl=0x%08x",
            "msgid=0x%08x",
            "holder_tcs=%d group=%d",     # still stashed in tcs->req[]?
            "ring_summary",               # send without completion?
            "matched_send=%d matched_done=%d",
            "LATE COMPLETION",            # the lifetime hazard, reported only
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_reports_the_lifetime_hazard_without_changing_it(self):
        text = patch_text()
        # The strongest available invariant: the patch only *adds* lines. It
        # cannot have rewritten the warning, the free, the return path or the
        # timeout value, and it cannot have introduced lifetime management.
        removed = [line for line in text.splitlines()
                   if line.startswith("-") and not line.startswith("---")]
        self.assertEqual(removed, [], f"patch removes upstream lines: {removed}")
        # ... and it does report the hazard rather than hiding it.
        self.assertIn("LATE COMPLETION", text)
        self.assertIn("lifetime hazard is real", text)
        # Nor may it add its own lifetime management.
        for forbidden in ("kref", "refcount", "rcu_head", "del_timer", "cancel_work"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_no_continuous_output_on_the_normal_path(self):
        text = patch_text()
        # Printk only inside the dump path and the late-completion report.
        added_prints = [line for line in text.splitlines()
                        if line.startswith("+") and "pr_err" in line]
        self.assertTrue(added_prints)
        # Bounded: one dump of a known shape, not a per-event stream.
        self.assertLessEqual(len(added_prints), 20)
        # And the hot paths carry at most a single gated branch each.
        self.assertIn("if (unlikely(gts9_rpmh_debug))", text)
        self.assertIn("if (unlikely(gts9_rpmh_debug_enabled()))", text)
        # No tracing/file I/O was invented; the existing tracepoints are reused.
        self.assertNotIn("trace_printk", text)
        self.assertNotIn("trace_array", text)
        self.assertNotIn("filp_open", text)
        self.assertNotIn("schedule_work", text)

    def test_the_diagnostic_is_documented_as_diagnostic_only(self):
        text = README.read_text()
        self.assertIn("0021-gts9-rpmh-timeout-state-dump.patch", text)
        self.assertIn("GTS9_RPMH_DEBUG=1", text)
        self.assertIn("LATE COMPLETION", text)
        self.assertIn("no per-event print", text)
        self.assertIn("Diagnostic only, no behaviour change", PATCH.read_text())

    def test_the_capture_harness_matches_the_dump_prefix(self):
        harness = (ROOT / "reference/boot-tests/test-186-20260924T230000Z"
                   / "rpmh-stall-capture.sh").read_text()
        self.assertIn("gts9-rpmh: TIMEOUT", harness)
        self.assertIn("ring_summary", harness)
        self.assertIn("holder_line", harness)
        self.assertIn("not-reproduced", harness)


if __name__ == "__main__":
    unittest.main()
