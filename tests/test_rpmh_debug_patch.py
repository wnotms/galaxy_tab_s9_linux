"""Host checks for the opt-in RPMh timeout diagnostic (patch 0021).

The diagnostic is the one new variable test-186 introduces, so its contract is
pinned here: it stays opt-in, it changes no RPMh semantics, it captures the
fields the stall investigation needs, and a normal build never contains it.
"""
import pathlib
import re
import tempfile
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
        # The verdict is the classifier's branch, and the harness must not keep
        # a second, divergent notion of "first anomaly".
        self.assertIn("classify-round.sh", harness)
        self.assertNotIn("first_anomaly()", harness)


if __name__ == "__main__":
    unittest.main()


class DecisionTreeClassifierTests(unittest.TestCase):
    """The classifier must read the pre-agreed tree, not invent a story.

    It is exercised on synthetic captures so the branches are pinned before any
    real log exists - the point of fixing the tree in advance.
    """

    ROUND = ROOT / "reference/boot-tests/test-186-20260924T230000Z"

    def classify(self, name):
        import subprocess
        out = subprocess.run(
            ["sh", str(self.ROUND / "classify-round.sh"),
             str(self.ROUND / "fixtures" / name)],
            text=True, capture_output=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = {}
        for line in out.stdout.splitlines():
            key, _, value = line.partition("=")
            if key and value:
                got[key] = value.strip()
        return got

    def test_quiet_capture_is_not_reproduced(self):
        self.assertEqual(self.classify("no-anomaly.log")["branch"], "no-anomaly")

    def test_programmed_without_completion_points_at_rsc_tcs_irq(self):
        got = self.classify("programmed-no-completion.log")
        self.assertEqual(got["branch"], "rpmh-programmed-no-completion")
        self.assertEqual(got["matched_send"].split()[0], "1")
        self.assertIn("matched_done=0", got["matched_send"])
        # The dump instant is the timeout; the send was ~10 s earlier, which is
        # the RPMH_TIMEOUT_MS value in rpmh.c.
        self.assertEqual(got["rpmh_timeout_ts"], "14.270200")

    def test_earlier_soft_lockup_makes_rpmh_the_victim(self):
        got = self.classify("victim.log")
        self.assertEqual(got["branch"], "victim-other-anomaly-earlier")
        self.assertEqual(got["soft_lockup_ts"], "13.400000")
        self.assertEqual(got["rpmh_timeout_ts"], "14.270100")

    def test_late_completion_branch_exists_and_wins(self):
        text = (self.ROUND / "fixtures" / "programmed-no-completion.log").read_text()
        text = text.replace(
            "[   20.000000] [drm:dpu_encoder_frame_done_timeout:2731] *ERROR* enc35 frame done timeout",
            "[   15.100000] gts9-rpmh: LATE COMPLETION for a request that already timed out (msg=00000000deadbeef) - the rpmh_write_batch() lifetime hazard is real")
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "late.log"
            path.write_text(text)
            import subprocess
            out = subprocess.run(["sh", str(self.ROUND / "classify-round.sh"), str(path)],
                                 text=True, capture_output=True, check=False)
        self.assertIn("branch=rpmh-completed-late", out.stdout)

    def test_the_harness_records_the_branch_it_gets(self):
        harness = (self.ROUND / "rpmh-stall-capture.sh").read_text()
        self.assertIn("classify-round.sh", harness)
        self.assertIn("round-$i-branch.txt", harness)
        self.assertIn('echo "branch=$verdict"', harness)
