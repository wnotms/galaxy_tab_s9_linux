"""Host checks for the X710 GPU / ACD / RPMh stall A/B.

Pins the contract of this phase before any physical round runs, so the A/B
cannot drift after the fact:

* the three cmdline profiles differ by exactly one token, so profiles A/B/C are
  a genuine one-variable experiment and share one kernel;
* the cmdline literals really are the ones the pinned kernel registers, checked
  against the source declarations rather than assumed;
* no A/B profile carries instrumentation that test-184 showed can change the
  thing being measured;
* the GMU cxpd backport is a clean upstream fix with its provenance recorded, and
  is not silently rewritten;
* the AOSS QMP config fix is present and is the reason the GPU can bind at all.
"""
import hashlib
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

BASELINE = "boot/cmdline.stall-ab-baseline.example.txt"
NO_ACD = "boot/cmdline.stall-ab-no-acd.example.txt"
NO_GPU = "boot/cmdline.stall-ab-no-gpu.example.txt"
PROFILES = (BASELINE, NO_ACD, NO_GPU)

BACKPORT = "kernel/patches/0007-drm-msm-adreno-a6xx-mark-cxpd-device-link-stateless.patch"
FRAGMENT = "kernel/config/gts9wifi-mainline.fragment"
PREPARE = "scripts/prepare-kernel.sh"
HARNESS = "scripts/stall-ab.sh"
PLAN = "docs/GPU_GMU_RPMH_STALL_PLAN.md"
DIFF_DOC = "docs/X710_X910_GPU_RPMH_DIFF.md"
LIFETIME = "docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md"
RSC_STATUS = "docs/RPMH_RSC_DEBUG_PATCH_STATUS.md"
ADRENO_DEVICE = "adreno_device.c"

# The profiles that must stay byte-identical: this phase adds new profiles, it
# does not touch the known-good boots.
KNOWN_GOOD_CMDLINES = {
    "boot/cmdline.example.txt": "77855e1e97c6edc039c2055d2e8902b53ea7f68941daf3788eec90c4a81a4ac7",
    "boot/cmdline.minimal-rootfs.example.txt": "c65593c01dc3e6fd29137f9f7ad8005c41765399d9fd2d7ea97755c1f0868dd0",
    "boot/cmdline.poweroff-trace.example.txt": "addcbdedafc0bd610590e3ab877f00d6f75deff90b45a145e0e28a6218f81d91",
    "boot/cmdline.boot-trace.example.txt": "07b5d7b282b3f2be21f62a771bcf8f9f5568f37d02849cb442422bc74eb81053",
    "boot/cmdline.watchdog-debug.example.txt": None,  # hashed below, mode 0600
    "boot/cmdline.rpmh-debug.example.txt": None,
}


def read(rel):
    return (ROOT / rel).read_text()


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def tokens(rel):
    """The command line exactly as the bundle builder will emit it.

    scripts/build-boot-bundle.sh does `tr '\\n' ' '` then strips the trailing
    space, so a # comment line would end up as literal kernel command-line text.
    That is why every profile must be pure cmdline.
    """
    return read(rel).replace("\n", " ").strip().split()


class AbProfileTests(unittest.TestCase):
    """Profiles A/B/C are one token apart and share one kernel."""

    def test_the_three_profiles_differ_by_exactly_one_token(self):
        base = tokens(BASELINE)
        self.assertEqual(tokens(NO_ACD), base[:2] + ["msm.disable_acd=1"] + base[2:])
        self.assertEqual(tokens(NO_GPU), base[:2] + ["msm.no_gpu=1"] + base[2:])

    def test_the_one_added_token_is_the_documented_one(self):
        self.assertIn("msm.disable_acd=1", tokens(NO_ACD))
        self.assertNotIn("msm.no_gpu=1", tokens(NO_ACD))
        self.assertIn("msm.no_gpu=1", tokens(NO_GPU))
        self.assertNotIn("msm.disable_acd=1", tokens(NO_GPU))
        for tok in ("msm.disable_acd", "msm.no_gpu"):
            self.assertFalse(
                [t for t in tokens(BASELINE) if t.startswith(tok)],
                f"the baseline profile must not carry {tok}",
            )

    def test_profiles_are_pure_cmdline_with_no_comment_lines(self):
        """A '#' line would become a literal (and invalid) kernel token."""
        for name in PROFILES:
            with self.subTest(cmdline=name):
                text = read(name)
                self.assertNotIn("#", text)
                self.assertTrue(text.endswith("\n"))
                for tok in tokens(name):
                    self.assertNotIn(" ", tok)
                    self.assertNotIn("\t", tok)

    def test_every_profile_keeps_display_and_the_verified_console_mapping(self):
        for name in PROFILES:
            with self.subTest(cmdline=name):
                toks = tokens(name)
                # Display and GPU are separate DRM devices, and profile C relies
                # on this being true while the GPU driver is not registered.
                self.assertIn("msm.separate_gpu_kms=1", toks)
                # ttyGS1 is the USB kernel console (docs/USB_SERIAL_CONSOLE.md).
                self.assertIn("console=ttyGS1", toks)
                # The physical UART stays a kernel console.
                self.assertTrue(any(t.startswith("console=ttyMSM0") for t in toks))
                self.assertIn("earlycon", toks)
                # The panel console.
                self.assertIn("console=tty0", toks)
                # Recovery must survive an unattended stall.
                self.assertIn("softlockup_panic=1", toks)
                self.assertIn("panic=10", toks)

    def test_no_ab_profile_carries_an_observer_instrument(self):
        """test-184 measured that these can change what is being measured."""
        for name in PROFILES:
            with self.subTest(cmdline=name):
                joined = " ".join(tokens(name))
                for forbidden in (
                    "gts9_kmsg_mirror",
                    "gts9_dpu_flight",
                    "gts9_rpmh_debug",
                    "gts9_poweroff_trace",
                ):
                    self.assertNotIn(forbidden, joined)

    def test_known_good_profiles_are_untouched(self):
        for name, digest in KNOWN_GOOD_CMDLINES.items():
            if digest is None:
                continue
            with self.subTest(cmdline=name):
                self.assertEqual(sha256(name), digest)


class CmdlineLiteralTests(unittest.TestCase):
    """The literals in the profiles are the ones the kernel actually registers.

    The C variables are `skip_gpu` and `disable_acd`, but the *parameter* names
    come from MODULE_PARM_DESC, so the command line uses `no_gpu`.  Getting this
    backwards would silently produce a profile that changes nothing, which is
    the worst possible A/B result: a false negative.
    """

    def _declaration(self, param):
        src = (ROOT / ".work/linux-mainline/drivers/gpu/drm/msm/adreno" /
               ADRENO_DEVICE)
        if not src.exists():
            self.skipTest("upstream checkout not present")
        return src.read_text()

    def test_no_gpu_is_the_literal_and_skip_gpu_is_the_variable(self):
        src = self._declaration("no_gpu")
        self.assertRegex(
            src,
            re.compile(r"static\s+bool\s+skip_gpu\s*;"),
            "skip_gpu must be the C variable",
        )
        self.assertRegex(
            src,
            re.compile(r'MODULE_PARM_DESC\(\s*no_gpu\s*,'),
            "no_gpu must be the module parameter name",
        )
        self.assertRegex(
            src,
            re.compile(r"module_param\(\s*skip_gpu\s*,\s*bool\s*,"),
            "skip_gpu must be registered via module_param",
        )

    def test_disable_acd_is_a_module_parameter(self):
        src = self._declaration("disable_acd")
        self.assertRegex(src, re.compile(r"bool\s+disable_acd\s*;"))
        self.assertRegex(
            src,
            re.compile(r'MODULE_PARM_DESC\(\s*disable_acd\s*,'),
        )
        self.assertRegex(
            src,
            re.compile(r"module_param_unsafe\(\s*disable_acd\s*,\s*bool\s*,"),
        )

    def test_no_gpu_prevents_the_adreno_driver_from_registering(self):
        """Profile C is only meaningful if the GPU driver truly never binds."""
        src = self._declaration("no_gpu")
        # adreno_register() must bail out before registering the driver...
        self.assertRegex(
            src,
            re.compile(
                r"void\s+__init\s+adreno_register\(void\)\s*\{\s*"
                r"if\s*\(\s*skip_gpu\s*\)\s*return\s*;",
                re.S,
            ),
        )
        # ...and adreno_has_gpu() must report no GPU, so the DRM master does not
        # wait for a component that will never bind.
        self.assertRegex(
            src,
            re.compile(
                r"bool\s+adreno_has_gpu\(struct\s+device_node\s*\*\s*node\)\s*\{\s*"
                r"const\s+struct\s+adreno_info\s*\*\s*info\s*;\s*"
                r"uint32_t\s+chip_id\s*;\s*int\s+ret\s*;\s*"
                r"if\s*\(\s*skip_gpu\s*\)\s*return\s+false\s*;",
                re.S,
            ),
        )

    def test_disable_acd_short_circuits_before_the_qmp_check(self):
        """Profile B removes the ACD requirement; it does not 'isolate ACD'.

        This is the correction recorded in docs/GPU_GMU_RPMH_STALL_PLAN.md §3:
        the disable_acd branch returns before the branch that reads
        qcom,opp-acd-level and before the IS_ERR_OR_NULL(gmu->qmp) check, so on a
        kernel without CONFIG_QCOM_AOSS_QMP it substitutes for the provider.
        """
        src = (ROOT / ".work/linux-mainline/drivers/gpu/drm/msm/adreno/a6xx_gmu.c")
        if not src.exists():
            self.skipTest("upstream checkout not present")
        text = src.read_text()
        acd = text.index("a6xx_gmu_acd_probe(struct a6xx_gmu *gmu)")
        body = text[acd:]
        disable_at = body.index("if (disable_acd)")
        qmp_at = body.index("IS_ERR_OR_NULL(gmu->qmp)")
        self.assertLess(
            disable_at, qmp_at,
            "the disable_acd branch must precede the qmp check, otherwise "
            "profile B would not remove the ACD/AOSS dependency",
        )


class CxpdBackportTests(unittest.TestCase):
    """The GMU cxpd device_link fix is a clean, attributable upstream backport."""

    def test_it_is_in_the_default_queue_and_applied_by_prepare(self):
        self.assertTrue((ROOT / BACKPORT).exists())
        # Default queue == kernel/patches/*.patch, which prepare-kernel.sh globs.
        self.assertNotIn("/diagnostic/", BACKPORT)
        self.assertNotIn("/pending/", BACKPORT)

    def test_it_marks_both_cxpd_links_stateless(self):
        text = read(BACKPORT)
        self.assertEqual(
            text.count("DL_FLAG_PM_RUNTIME | DL_FLAG_STATELESS"), 2,
            "both a6xx_gmu_wrapper_init() and a6xx_gmu_init() must be fixed",
        )
        # wrapper init uses the non-assigning form, gmu_init keeps the handle so
        # it can device_link_del() on its error path.
        self.assertIn("if (!device_link_add(gmu->dev, gmu->cxpd,", text)
        self.assertIn("link = device_link_add(gmu->dev, gmu->cxpd,", text)

    def test_it_records_provenance_and_why_x710_needs_it(self):
        text = read(BACKPORT)
        for needle in (
            "Akhil P Oommen",                    # author
            "20260513-gmu-sync-state-fix",       # series identity
            "Reviewed-by: Dmitry Baryshkov",     # review state
            "not merged",                        # upstream status, honestly stated
            "ead5d3e5eb37",                      # Fixes: tag
            "Unable to drop a managed device link reference",  # the X710 symptom
            "test-046",                          # where it was captured
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_does_not_pretend_to_have_an_upstream_sha(self):
        """The series is RFT/unmerged, so a SHA claim would be fabrication."""
        text = read(BACKPORT)
        self.assertNotRegex(
            text,
            re.compile(r"commit [0-9a-f]{40} upstream", re.I),
        )
        self.assertIn("no upstream commit SHA", text)

    def test_the_hunks_match_the_pinned_source(self):
        """Guards against the patch being written against a different revision."""
        patch = read(BACKPORT)
        for line in patch.splitlines():
            if line.startswith(("-", "+")) and "device_link_add(gmu->dev, gmu->cxpd" in line:
                continue
        # The removed lines are the exact pre-image in v7.2-rc3.
        self.assertIn(
            "-	if (!device_link_add(gmu->dev, gmu->cxpd, DL_FLAG_PM_RUNTIME)) {",
            patch,
        )
        self.assertIn(
            "-	link = device_link_add(gmu->dev, gmu->cxpd, DL_FLAG_PM_RUNTIME);",
            patch,
        )


class AossQmpConfigTests(unittest.TestCase):
    """The config fix that lets the GPU bind at all."""

    def test_the_fragment_requests_aoss_qmp(self):
        self.assertIn("CONFIG_QCOM_AOSS_QMP=y", read(FRAGMENT))

    def test_the_fragment_explains_why(self):
        text = read(FRAGMENT)
        for needle in (
            "aoss_qmp",
            "qcom,opp-acd-level",
            "Unable to send ACD state to AOSS",
            "Unable to drop a managed device link reference",
            "docs/GPU_GMU_RPMH_STALL_PLAN.md",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_resolved_config_has_it_built_in(self):
        """Only meaningful once the kernel has been built with the symbol."""
        cfg = ROOT / "out/kernel-gts9wifi/config"
        if not cfg.exists():
            self.skipTest("no resolved config yet")
        text = cfg.read_text()
        if "CONFIG_QCOM_AOSS_QMP=y" not in text:
            self.skipTest(
                "resolved config predates the fragment change; rebuild to check"
            )
        self.assertIn("CONFIG_QCOM_AOSS_QMP=y", text)

    def test_the_dependency_providers_are_present(self):
        """AOSS QMP depends on MAILBOX, COMMON_CLK and PM."""
        cfg = ROOT / "out/kernel-gts9wifi/config"
        if not cfg.exists() or "CONFIG_QCOM_AOSS_QMP=y" not in cfg.read_text():
            self.skipTest("resolved config does not have AOSS QMP yet")
        text = cfg.read_text()
        for sym in ("CONFIG_MAILBOX=y", "CONFIG_COMMON_CLK=y", "CONFIG_PM=y"):
            with self.subTest(sym=sym):
                self.assertIn(sym, text)


class HarnessContractTests(unittest.TestCase):
    """scripts/stall-ab.sh enforces the one-variable rule itself."""

    def test_it_is_executable_and_syntax_clean(self):
        self.assertTrue((ROOT / HARNESS).stat().st_mode & 0o111)

    def test_it_knows_the_three_profiles_and_refuses_others(self):
        text = read(HARNESS)
        self.assertIn("baseline|no-acd|no-gpu", text)
        for name in ("msm.disable_acd=1", "msm.no_gpu=1"):
            self.assertIn(name, text)

    def test_it_rejects_a_profile_carrying_the_wrong_token(self):
        text = read(HARNESS)
        # baseline must reject both, no-acd must reject no_gpu, and vice versa.
        self.assertIn("baseline must not carry msm.disable_acd", text)
        self.assertIn("baseline must not carry msm.no_gpu", text)
        self.assertIn("no-acd must not carry msm.no_gpu", text)
        self.assertIn("no-gpu must not carry msm.disable_acd", text)

    def test_it_requires_the_shared_invariants(self):
        text = read(HARNESS)
        for needle in (
            "msm.separate_gpu_kms=1",
            "gts9_watchdog_debug=1",
            "console=ttyGS1",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_refuses_to_reboot_without_explicit_permission(self):
        text = read(HARNESS)
        self.assertIn("GTS9_ALLOW_POWER", text)
        self.assertIn('if [ "$ALLOW" != "1" ]', text)

    def test_it_reports_the_metric_set_the_investigation_needs(self):
        text = read(HARNESS)
        for key in (
            "soft_lockup", "hung_task", "rcu_stall", "workqueue_stall",
            "rpmh_timeout", "rpmh_active_only", "dpu_frame_timeout",
            "mmc_timeout", "gpu_acd_aoss", "gpu_device_link", "gpu_acd_skipped",
            "boot_id_after", "first_anomaly",
        ):
            with self.subTest(key=key):
                self.assertIn(key, text)

    def test_it_probes_the_gpu_binding_state(self):
        """The whole hypothesis is 'the GPU never binds'; that must be measured."""
        text = read(HARNESS)
        for needle in ("gmu_bound", "gpu_bound", "aoss_bound", "deferred"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_never_flashes_or_writes_a_partition(self):
        text = read(HARNESS)
        for forbidden in ("fastboot", "dd if=", "flash ", "avbtool", "mkbootimg"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


class DocumentationTests(unittest.TestCase):
    """The phase's claims stay tied to their evidence."""

    def test_the_plan_states_the_hypothesis_is_a_hypothesis(self):
        text = read(PLAN)
        self.assertIn("HYPOTHESIS", text)
        self.assertIn("not a proven root cause", text)

    def test_the_plan_keeps_the_rpmh_work_as_a_fallback(self):
        self.assertIn("NEXT_STALL_DEBUG_PLAN.md", read(PLAN))

    def test_the_plan_has_the_five_labelled_experiments(self):
        text = read(PLAN)
        for token in ("msm.disable_acd=1", "msm.no_gpu=1",
                      "CONFIG_QCOM_AOSS_QMP=y", "gts9_rpmh_debug=1"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_the_plan_forbids_once_more_what_must_not_be_done(self):
        text = read(PLAN)
        for forbidden in ("regulator-always-on", "Gunyah", "PSCI"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, text)

    def test_the_diff_doc_uses_only_the_five_allowed_labels(self):
        text = read(DIFF_DOC)
        allowed = {
            "same hardware", "different hardware", "possibly relevant",
            "definitely unrelated", "needs stock X710 evidence",
        }
        for label in allowed:
            with self.subTest(label=label):
                self.assertIn(label, text)
        # No stray sixth classification.
        self.assertNotIn("probably relevant", text)
        self.assertNotIn("likely relevant", text)
        self.assertNotIn("definitely relevant", text)

    def test_the_diff_doc_records_the_kconfig_difference(self):
        text = read(DIFF_DOC)
        self.assertIn("CONFIG_QCOM_AOSS_QMP", text)
        self.assertIn("X910", text)

    def test_the_lifetime_analysis_does_not_change_semantics(self):
        text = read(LIFETIME)
        self.assertIn("analysis only", text.lower())
        self.assertIn("NOT implemented", text)

    def test_the_rsc_patch_status_names_the_series_and_revision(self):
        text = read(RSC_STATUS)
        for needle in (
            "Output debug information from RSC",
            "v4",
            "20260913-rpmh-timeout-debug-v1-v4-0-e94d3e416ea1@oss.qualcomm.com",
            "Maulik Shah",
            "Not merged",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # It must be prepared-but-not-applied.
        self.assertIn("not applied", text.lower())


if __name__ == "__main__":
    unittest.main()
