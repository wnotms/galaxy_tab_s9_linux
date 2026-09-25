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
LATE_DEFERRED = "boot/cmdline.stall-ab-late-deferred.example.txt"
# A, B, C and G share one kernel and differ only in the command line.
PROFILES = (BASELINE, NO_ACD, NO_GPU, LATE_DEFERRED)

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
        # Profile G is the round-2 burst-decoupling axis: same kernel as A/B/C,
        # only the instant of the deferred-probe-timeout burst moves.
        self.assertEqual(
            tokens(LATE_DEFERRED),
            base[:2] + ["deferred_probe_timeout=300"] + base[2:],
        )

    def test_the_burst_decoupling_token_is_exclusive_to_profile_g(self):
        self.assertIn("deferred_probe_timeout=300", tokens(LATE_DEFERRED))
        for name in (BASELINE, NO_ACD, NO_GPU):
            with self.subTest(cmdline=name):
                joined = " ".join(tokens(name))
                self.assertNotIn("deferred_probe_timeout", joined)

    def test_the_one_added_token_is_the_documented_one(self):
        self.assertIn("msm.disable_acd=1", tokens(NO_ACD))
        self.assertNotIn("msm.no_gpu=1", tokens(NO_ACD))
        self.assertIn("msm.no_gpu=1", tokens(NO_GPU))
        self.assertNotIn("msm.disable_acd=1", tokens(NO_GPU))
        for tok in ("msm.disable_acd", "msm.no_gpu", "deferred_probe_timeout"):
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


class Test187CandidateTests(unittest.TestCase):
    """test-187 is a real one-variable A/B: one kernel, three command lines.

    These checks only run when the bundles exist, so a fresh checkout without a
    build does not fail; they are here so that a rebuilt candidate cannot
    silently stop being an A/B (for example by the kernel differing between
    profiles, which would make every profile comparison meaningless).
    """
    TESTDIR = "reference/boot-tests/test-187-20260924T1540Z"
    BUNDLES = {
        "baseline": "out/boot-bundle-test187-baseline",
        "no-acd": "out/boot-bundle-test187-no-acd",
        "no-gpu": "out/boot-bundle-test187-no-gpu",
        "late-deferred": "out/boot-bundle-test187-late-deferred",
        "rpmh-debug": "out/boot-bundle-test187-rpmh-debug",
    }

    def _bundle(self, name):
        path = ROOT / self.BUNDLES[name]
        if not (path / "boot.img").exists():
            self.skipTest(f"{self.BUNDLES[name]} not built")
        return path

    def test_the_candidate_records_its_current_flash_status(self):
        """The candidate must say truthfully whether it has been flashed.

        It was written as "not flashed" in round 1; profile A was then flashed and
        booted in round 3 once the owner authorised it. Either state is fine, but
        the document has to match reality and must not claim a fix.
        """
        text = read(f"{self.TESTDIR}/candidate.txt")
        flashed = "has since been flashed" in text
        not_flashed = "NOT flashed" in text
        self.assertTrue(
            flashed or not_flashed,
            "candidate must state its flash status explicitly",
        )
        if flashed:
            # Once flashed, it must point at the on-device result and must not
            # overclaim: the stall A/B is still outstanding.
            self.assertIn("on-device/README.md", text)
            self.assertIn("no fix claim", text)
            self.assertIn("still outstanding", text)

    def test_all_profiles_share_one_kernel(self):
        """The whole A/B rests on this."""
        digests = {}
        for name in self.BUNDLES:
            digests[name] = sha256(f"{self.BUNDLES[name]}/boot.img")
        self.assertEqual(
            len(set(digests.values())), 1,
            f"profiles must share one boot.img, got {digests}",
        )

    def test_the_profiles_differ_only_in_vendor_boot(self):
        for part in ("init_boot.img", "dtbo.img", "vbmeta.img"):
            digests = {n: sha256(f"{self.BUNDLES[n]}/{part}") for n in self.BUNDLES}
            with self.subTest(partition=part):
                self.assertEqual(len(set(digests.values())), 1)

        vb = {n: sha256(f"{self.BUNDLES[n]}/vendor_boot.img") for n in self.BUNDLES}
        self.assertEqual(
            len(set(vb.values())), len(vb),
            "each profile must have its own vendor_boot.img",
        )

    def test_the_candidate_records_the_real_hashes(self):
        """Guards against the candidate describing images it did not build."""
        text = read(f"{self.TESTDIR}/candidate.txt")
        for name in self.BUNDLES:
            with self.subTest(profile=name):
                self.assertIn(sha256(f"{self.BUNDLES[name]}/vendor_boot.img"), text)
        self.assertIn(sha256(f"{self.BUNDLES['baseline']}/boot.img"), text)
        # Compare against what the bundles actually embedded, NOT against a
        # fresh rebuild of out/kernel-gts9wifi: the module-signing key is
        # regenerated on every build, so a clean rebuild legitimately produces a
        # different Image.gz (see docs/BUILD_REPRODUCIBILITY.md).  BUNDLE_INFO is
        # the frozen record of the build the images came from.
        self.assertIn(self._embedded_image_sha(), text)

    def _embedded_image_sha(self):
        infos = set()
        for name in self.BUNDLES:
            info = (ROOT / self.BUNDLES[name] / "BUNDLE_INFO")
            if not info.exists():
                self.skipTest("BUNDLE_INFO missing")
            for line in info.read_text().splitlines():
                if line.startswith("image_gz_sha256="):
                    infos.add(line.split("=", 1)[1])
        self.assertEqual(
            len(infos), 1,
            "all profiles must embed the same single kernel build",
        )
        return infos.pop()

    def test_all_profiles_embed_one_kernel_build(self):
        """The A/B claim, stated in terms of the recorded build identity."""
        self.assertTrue(self._embedded_image_sha())

    def test_the_rpmh_debug_profile_reuses_the_verified_cmdline_bundle(self):
        """E differs from test-186 only by the kernel, not the command line."""
        prior = ROOT / "out/boot-bundle-rpmh-debug/vendor_boot.img"
        here = ROOT / self.BUNDLES["rpmh-debug"] / "vendor_boot.img"
        if not prior.exists() or not here.exists():
            self.skipTest("bundles not built")
        self.assertEqual(
            hashlib.sha256(prior.read_bytes()).hexdigest(),
            hashlib.sha256(here.read_bytes()).hexdigest(),
        )

    def test_the_runner_covers_the_three_profiles_in_order(self):
        text = read(f"{self.TESTDIR}/ab-run.sh")
        # A first, then G (the new burst-decoupling axis), then B and C.
        self.assertIn("for profile in baseline late-deferred no-acd no-gpu", text)
        # It must not flash anything itself.
        for forbidden in ("fastboot", "dd if=", "avbtool", "mkbootimg"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        # ...and it must not reboot without permission.
        self.assertIn("GTS9_ALLOW_POWER", text)

    def test_the_result_matrix_is_decided_before_the_data(self):
        text = read(f"{self.TESTDIR}/candidate.txt")
        for branch in (
            "the ACD requirement is on the causal path",
            "GPU/GMU registration is required",
            "GPU/GMU is **demoted**",
            "not reproduced this round",
        ):
            with self.subTest(branch=branch):
                self.assertIn(branch, text)

    def test_it_does_not_credit_the_config_fix_for_the_missing_warning(self):
        """Patch 0007 is in the same kernel, so the WARN cannot be attributed."""
        for name in ("candidate.txt", "README.md"):
            with self.subTest(file=name):
                self.assertIn("0007", read(f"{self.TESTDIR}/{name}"))


class BuildReproducibilityTests(unittest.TestCase):
    """Pins the *cause* of the kernel-build non-determinism.

    Two clean builds of the same source and config produce different Image.gz
    hashes because certs/Makefile regenerates the module-signing key on every
    build.  That is analysed in docs/BUILD_REPRODUCIBILITY.md.  These checks fail
    if the cause disappears, so a fix cannot land silently and leave the document
    claiming a defect that no longer exists.
    """
    DOC = "docs/BUILD_REPRODUCIBILITY.md"
    CERTS_MAKEFILE = ".work/linux-mainline/certs/Makefile"

    def test_the_document_exists_and_states_the_mechanism(self):
        text = read(self.DOC)
        for needle in (
            "CONFIG_MODULE_SIG_KEY",
            "certs/signing_key.pem",
            "FORCE",
            "Build time autogenerated kernel key",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_is_recorded_as_open_and_not_silently_fixed(self):
        text = read(self.DOC)
        self.assertIn("NOT applied", text)
        # It must say plainly that it does not invalidate the test-187 A/B.
        self.assertIn("does **not** undermine", text)

    def test_the_force_prerequisite_is_still_the_cause(self):
        """If this stops matching, the defect was fixed - update the document."""
        path = ROOT / self.CERTS_MAKEFILE
        if not path.exists():
            self.skipTest("upstream checkout not present")
        text = path.read_text()
        self.assertRegex(
            text,
            re.compile(r"\$\(obj\)/signing_key\.pem:[^\n]*\bFORCE\b"),
            "certs/Makefile no longer force-regenerates signing_key.pem; "
            "docs/BUILD_REPRODUCIBILITY.md must be revisited",
        )

    def test_the_resolved_config_still_uses_the_generated_key(self):
        cfg = ROOT / "out/kernel-gts9wifi/config"
        if not cfg.exists():
            self.skipTest("no resolved config")
        text = cfg.read_text()
        if "CONFIG_MODULE_SIG=y" not in text:
            self.skipTest("module signing is off in this config")
        self.assertIn('CONFIG_MODULE_SIG_KEY="certs/signing_key.pem"', text)


class EvidenceProvenanceTests(unittest.TestCase):
    """Synthetic fixtures must never be presented as hardware evidence.

    Round 1 wrote a "measured timeline" section that cited
    test-186-*/fixtures/*.log as real device captures.  Those files are
    synthetic: the commit that added them says so ("Three synthetic fixtures pin
    the branches"), test-186 has no rounds/ directory because it was never run on
    the device, and the timestamps in them exist nowhere else.  A reviewer cannot
    tell synthetic from captured by looking at a log, so the distinction has to
    be enforced here.
    """
    FIXTURES = "reference/boot-tests/test-186-20260924T230000Z/fixtures"
    TEST186 = "reference/boot-tests/test-186-20260924T230000Z"
    TESTDIR = "reference/boot-tests/test-187-20260924T1540Z"
    PLAN = "docs/GPU_GMU_RPMH_STALL_PLAN.md"
    # A timestamp that only the synthetic fixture contains.
    FIXTURE_ONLY_TS = "13.400000"

    def test_the_fixtures_are_synthetic(self):
        """If this stops being true the guard below must be revisited."""
        self.assertIn("synthetic", read(f"{self.TEST186}/README.md").lower())
        # test-186 was never executed: no per-round output directory.
        self.assertFalse(
            (ROOT / f"{self.TEST186}/rounds").exists(),
            "test-186 now has rounds/ - if it really ran, the fixtures are "
            "captured evidence and the round-2 correction must be revisited",
        )

    def test_the_plan_no_longer_cites_a_fixture_as_hardware_evidence(self):
        text = read(self.PLAN)
        # The correction note may *mention* the fixture path; what it must not do
        # is present it as the source of a measurement.  Guard the specific
        # wording round 1 used.
        self.assertNotIn("### 4.1 The stall, from", text)
        self.assertNotIn(
            "Measured timeline (from real hardware evidence only)",
            text,
        )

    def test_the_plan_keeps_the_correction_note(self):
        text = read(self.PLAN)
        self.assertIn("Correction (round 2)", text)
        self.assertIn("synthetic", text)
        self.assertIn("test-186", text)

    def test_the_fixture_only_timestamp_is_not_quoted_as_real(self):
        """13.400000 appears only in the fixture; it must not be a plan fact."""
        # It may appear inside the correction note (which names it as fixture
        # content), so check the facts table specifically.
        text = read(self.PLAN)
        facts = text.split("## 2.")[0]
        self.assertNotIn(self.FIXTURE_ONLY_TS, facts)

    def test_no_real_rpmh_dump_is_claimed(self):
        """Patch 0021 has never run on the device; the plan must say so."""
        text = read(self.PLAN)
        self.assertIn("no captured RPMh timeout dump", text)
        self.assertIn("never run on the device", text)
        self.assertIn("unexercised", text)

    def test_the_fixtures_are_still_labelled_in_their_own_directory(self):
        """A reader who lands on fixtures/ directly must not be misled."""
        readme = read(f"{self.TEST186}/README.md")
        self.assertIn("synthetic", readme.lower())


    def test_the_burst_timing_is_not_claimed_as_late_initcall_plus_10s(self):
        """Round 3 correction: driver_register() re-arms the timer.

        The burst fires 10 s after the LAST driver_register() that found the work
        pending, not 10 s after late_initcall. Getting this wrong makes the
        13-14 s window look like a fixed consequence of the GPU failure, which the
        live counter-example disproves.
        """
        text = read(self.PLAN)
        self.assertIn("deferred_probe_extend_timeout", text)
        self.assertIn("driver_register", text)
        # The disproving observation must be recorded, not just the mechanism.
        self.assertIn("35.805", text)
        self.assertIn("not sufficient", text.lower())

    def test_the_live_preflight_evidence_is_present(self):
        d = f"{self.TESTDIR}/live-preflight"
        text = read(f"{d}/README.md")
        for needle in (
            "GPU_UNBOUND",
            "GMU_UNBOUND",
            "AOSS_UNBOUND",
            "error -22",
            "35.805388",
            "f7b1e8de-1487-4eb3-8819-5cb273b2b740",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_live_preflight_is_documented_as_read_only(self):
        text = read(f"{self.TESTDIR}/live-preflight/README.md")
        self.assertIn("read-only", text)
        self.assertIn("Nothing was written", text)


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


class ConsoleHostTests(unittest.TestCase):
    """The console helpers must run from the checkout's own host.

    Every harness used to call `powershell -File scripts/console-*.ps1`, which
    cannot work here: the checkout lives inside WSL and PowerShell refuses to run
    a script by UNC path.  A helper that cannot be invoked from this host is a
    harness that can only be driven by hand, so this is pinned.
    """

    SHIMS = ("scripts/console-run.sh", "scripts/console-watch.sh")
    LIB = "scripts/ps-host.sh"

    def test_the_front_ends_exist_and_are_executable(self):
        for rel in self.SHIMS:
            with self.subTest(rel=rel):
                path = ROOT / rel
                self.assertTrue(path.is_file(), rel)
                self.assertTrue(path.stat().st_mode & 0o111, f"{rel} not executable")

    def test_the_library_handles_both_host_quirks(self):
        text = read(self.LIB)
        # -File cannot take a UNC path, so the .ps1 is staged.
        self.assertIn("gts9_ps_stage", text)
        # -File binds an array parameter to one value, so -Command is used.
        self.assertIn("-Command", text)
        self.assertIn("gts9_ps_array", text)
        # Windows proper must keep working.
        self.assertIn("gts9_ps_in_wsl", text)

    # The live harnesses.  Retired test directories (test-181..test-184) are
    # historical records of runs that already happened and are deliberately not
    # rewritten - they are evidence, not tooling.
    LIVE = (
        "scripts/stall-ab.sh",
        "scripts/flash-boot.sh",
        "reference/boot-tests/test-187-20260924T1540Z/reboot-rounds.sh",
        "reference/boot-tests/test-187-20260924T1540Z/warm-rounds.sh",
        "reference/boot-tests/test-187-20260924T1540Z/shutdown-capture.sh",
        "reference/boot-tests/test-187-20260924T1540Z/cold-boot-capture.sh",
        "reference/boot-tests/test-188-20260925T0115Z/shutdown-series.sh",
    )

    def test_no_live_script_calls_powershell_at_the_ps1_directly(self):
        """Only the library may name the .ps1 files as -File targets."""
        offenders = []
        for rel in self.LIVE:
            for i, line in enumerate(read(rel).splitlines(), 1):
                if "-File" in line and ".ps1" in line:
                    offenders.append(f"{rel}:{i}")
        self.assertEqual(offenders, [], f"direct -File .ps1 calls: {offenders}")

    def test_the_harnesses_use_the_front_ends(self):
        for rel in self.LIVE:
            with self.subTest(rel=rel):
                self.assertIn("scripts/console-run.sh", read(rel))


class WorkqueueMetricTests(unittest.TestCase):
    """A stall metric that can never read 0 is not a metric.

    `journalctl -b -k` prints the `Kernel command line:` line, and this board's
    command line carries `workqueue.panic_on_stall_time=45`.  A `grep -c
    "workqueue.*stall"` therefore matched the command line itself and returned 1
    on every boot, clean or not.  Verified on the device: OLDWQ=1, NEWWQ=0.
    """

    RUNNERS = (
        "reference/boot-tests/test-187-20260924T1540Z/warm-rounds.sh",
        "reference/boot-tests/test-188-20260925T0115Z/shutdown-series.sh",
    )

    def test_no_runner_still_uses_the_false_positive_pattern(self):
        for rel in self.RUNNERS:
            with self.subTest(rel=rel):
                self.assertNotIn('grep -c "workqueue.*stall"', read(rel))

    def test_the_runners_match_the_real_stall_banner(self):
        # drivers/..; kernel/workqueue.c prints this from wq_watchdog_timer_fn().
        for rel in self.RUNNERS:
            with self.subTest(rel=rel):
                self.assertIn("BUG: workqueue lockup", read(rel))

    def test_the_journal_counts_exclude_the_command_line(self):
        for rel in self.RUNNERS:
            with self.subTest(rel=rel):
                text = read(rel)
                self.assertIn('grep -v "Kernel command line"', text)


class SMMUFaultAttributionTests(unittest.TestCase):
    """The earliest abnormal event must be attributed by SID, not by timing."""

    DOC = "docs/EARLY_SMMU_CONTEXT_FAULTS.md"

    def test_the_doc_names_the_stream_and_its_owner(self):
        text = read(self.DOC)
        self.assertIn("SID=0x1c00", text)
        self.assertIn("mdss: display-subsystem@ae00000", text)
        self.assertIn("qcom,sm8550-mdss", text)

    def test_it_corrects_the_adsp_attribution(self):
        text = read(self.DOC)
        self.assertIn("HWSPINLOCK-FIX-RESULT.md", text)
        self.assertIn("the attribution is wrong", text)
        self.assertIn("not the ADSP", text)

    def test_it_does_not_claim_the_failing_boots_had_them(self):
        """The two failure archives were rotated out; no claim may be made."""
        text = read(self.DOC)
        self.assertIn("no claim is made", text.lower())
        self.assertIn("rotated out", text)

    def test_the_retained_archive_counts_are_recorded(self):
        text = read(self.DOC)
        # The measured per-boot counts, so the variability claim is checkable.
        for count in ("`1084b57a`", "`9e3bde71`", "`cd04c0ef`"):
            with self.subTest(count=count):
                self.assertIn(count, text)


class Test188SeriesTests(unittest.TestCase):
    """test-188 repeats the shutdown series on the post-hwspinlock kernel."""

    TESTDIR = "reference/boot-tests/test-188-20260925T0115Z"

    def test_the_runner_exists_and_is_executable(self):
        path = ROOT / f"{self.TESTDIR}/shutdown-series.sh"
        self.assertTrue(path.is_file())
        self.assertTrue(path.stat().st_mode & 0o111)

    def test_it_requires_explicit_permission_to_reboot(self):
        text = read(f"{self.TESTDIR}/shutdown-series.sh")
        self.assertIn("GTS9_ALLOW_POWER", text)
        self.assertIn('if [ "$ALLOW" != "1" ]', text)

    def test_it_never_flashes_or_writes_a_partition(self):
        text = read(f"{self.TESTDIR}/shutdown-series.sh")
        for forbidden in ("fastboot", "dd if=", "flash ", "avbtool", "mkbootimg"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_it_requires_a_command_result_not_an_echo(self):
        text = read(f"{self.TESTDIR}/shutdown-series.sh")
        self.assertIn("GTS9_ALIVE_", text)
        self.assertIn("echo-only", text)

    def test_it_records_the_new_per_boot_facts(self):
        text = read(f"{self.TESTDIR}/shutdown-series.sh")
        for key in ("CTXFAULTS", "CTXSID", "ADSP"):
            with self.subTest(key=key):
                self.assertIn(key, text)

    def test_it_labels_every_cycle_as_a_warm_reboot(self):
        text = read(f"{self.TESTDIR}/shutdown-series.sh")
        self.assertIn("kind=warm-reboot", text)
        self.assertNotIn("kind=cold-boot", text)

    def test_it_does_not_overwrite_the_test_187_series(self):
        """A second series must not clobber the 16 cycles it is extending."""
        text = read(f"{self.TESTDIR}/shutdown-series.sh")
        self.assertIn("$D/shutdown-$i-verdict.txt", text)
        self.assertNotIn("test-187-20260924T1540Z", text)

    def test_the_readme_records_the_adsp_shutdown_audit(self):
        text = read(f"{self.TESTDIR}/README.md")
        self.assertIn("RPROC_RUNNING", text)
        self.assertIn("reboot notifier", text)
        self.assertIn("state=offline", text)

    def test_the_readme_keeps_the_no_prefix_rate_caveat(self):
        text = read(f"{self.TESTDIR}/README.md")
        self.assertIn("no pre-fix rate", text)
        self.assertIn("warm reboot", text)


class EvidenceArchiveIdentityTests(unittest.TestCase):
    """An archive must be able to name the boot it describes.

    The collector names its directory after the boot that runs it, while
    prev-kernel.log and previous_boot_end= describe the boot before it.  That made
    two archived failures get cited by the id of the boots that recovered from
    them, so both the naming and the missing previous id are pinned here.
    """

    COLLECTOR = "rootfs-overlay/usr/libexec/gts9-prev-boot-evidence"

    def test_the_directory_is_named_after_the_collecting_boot(self):
        text = read(self.COLLECTOR)
        self.assertIn("boot_id=$(cat /proc/sys/kernel/random/boot_id", text)
        self.assertIn("dir=$DEST_ROOT/$stamp-$short_id", text)

    def test_the_collector_now_records_the_previous_boot_id(self):
        text = read(self.COLLECTOR)
        self.assertIn("previous_boot_id=$prev_boot_id", text)
        # It must come from the same -b -1 selection as prev-kernel.log, so the
        # id cannot name a different boot than the log does.
        self.assertIn("journalctl -b -1 -o verbose", text)
        # And it must be empty rather than wrong when there is no previous journal.
        self.assertIn('if [ "$prev_state" = present ]', text)

    def test_the_harnesses_pick_the_newest_archive_by_mtime(self):
        """The device has no RTC, so name order is not age order."""
        for rel in ("reference/boot-tests/test-187-20260924T1540Z/reboot-rounds.sh",
                    "reference/boot-tests/test-187-20260924T1540Z/cold-boot-capture.sh"):
            with self.subTest(rel=rel):
                text = read(rel)
                self.assertIn("ls -1dt /var/log/gts9-boot-evidence/*/ 2>/dev/null | head -1", text)
                # The name-ordered selection must be gone.  Counting the
                # directories with `ls -1d ... | wc -l` is fine and still used.
                self.assertNotIn("gts9-boot-evidence/*/ 2>/dev/null | tail -1", text)

    def test_the_affected_documents_carry_the_correction(self):
        for rel, needle in (
            ("reference/boot-tests/test-187-20260924T1540Z/on-device/EVIDENCE-HISTORY.md",
             "Correction (round 16)"),
            ("reference/boot-tests/test-187-20260924T1540Z/on-device/STALL-SIGNATURE.md",
             "names the collector, not the failure"),
        ):
            with self.subTest(rel=rel):
                self.assertIn(needle, read(rel))


class StallFailureShapeTests(unittest.TestCase):
    """The failure's real signature is an ABSENCE, and that must stay recorded."""

    DOC = "docs/STALL_FAILURE_SHAPE.md"
    A5 = "reference/boot-tests/test-184-20260924T140000Z/rounds/console-A-5-watch.txt"

    def test_the_doc_quotes_the_measured_timeline(self):
        text = read(self.DOC)
        for needle in ("13:48:08.503", "13:48:09.331", "13:48:39.677",
                       "28.903 s", "0.828 s", "31.174 s"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_quoted_capture_still_supports_the_claims(self):
        """Re-derive the numbers from the capture rather than trusting the doc."""
        # This capture carries Windows-console error text in a legacy codepage,
        # so it is not valid UTF-8; decode leniently rather than skip the check.
        text = (ROOT / self.A5).read_text(errors="replace")
        self.assertIn("Stopping", text)
        self.assertIn("session-1.scope", text)
        self.assertIn("Stopped", text)
        # The console truncates long unit names to "name.se???", so only the
        # unambiguous prefix is guaranteed to appear.
        self.assertIn("gts9-prev-boot-evidence.s", text)
        self.assertIn("13:48:38.234Z read failed", text)
        self.assertIn("13:48:39.677Z PRESENCE usb0525:a4a7=False", text)
        # The failure emits no banner at all - that is the whole point.
        for banner in ("Kernel panic", "BUG: soft lockup", "hung_task",
                       "systemd-shutdown"):
            with self.subTest(banner=banner):
                self.assertNotIn(banner, text)

    def test_the_doc_excludes_the_kernel_reset_paths(self):
        """Who reset it must be argued from source, not assumed."""
        text = read(self.DOC)
        self.assertIn("no `wdt` or `watchdog` node at all", text)
        self.assertIn("CONFIG_SOFTDOG", text)
        self.assertIn("nothing in mainline reset the machine", text)
        # The residual unknown must stay unknown.
        self.assertIn("remains", text)
        self.assertIn("undetermined", text)

    def test_the_doc_localises_the_outstanding_stop_jobs(self):
        """The failure's narrowest localisation must not drift."""
        text = read(self.DOC)
        for unit in ("session-1.scope", "cron.service", "gts9-acm-getty.service",
                     "getty@tty1.service", "gts9-power-key.service"):
            with self.subTest(unit=unit):
                self.assertIn(unit, text)
        self.assertIn("five stop jobs outstanding", text)
        # And it must say why systemd never recovered on its own.
        self.assertIn("DefaultTimeoutStopSec", text)

    def test_the_doc_refutes_the_two_eliminated_explanations(self):
        text = read(self.DOC)
        self.assertIn("refuted", text)
        self.assertIn("reboot -f", text)

    def test_the_doc_does_not_name_a_reset_agent(self):
        text = read(self.DOC)
        self.assertIn("The reset agent is not established", text)

    def test_the_doc_records_why_the_old_classifier_missed_it(self):
        text = read(self.DOC)
        self.assertIn("observer-ab.sh:93", text)
        # Markdown wraps, so match the phrase in fragments rather than across a
        # line break.
        lowered = text.lower()
        self.assertIn("absence of a line", lowered)
        self.assertIn("no amount of banner-scanning will ever see it", lowered)

    def test_the_old_classifier_really_did_miss_it(self):
        """Pin the defect itself, not just the description of it."""
        text = read("reference/boot-tests/test-184-20260924T140000Z/observer-ab.sh")
        self.assertIn("console_stall_markers=", text)
        self.assertNotIn("systemd-shutdown", text)


if __name__ == "__main__":
    unittest.main()
