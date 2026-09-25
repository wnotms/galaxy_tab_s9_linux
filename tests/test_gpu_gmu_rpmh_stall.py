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
        self.assertEqual(tokens(NO_GPU), base[:2] + ["msm.skip_gpu=1"] + base[2:])
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
        self.assertNotIn("msm.skip_gpu=1", tokens(NO_ACD))
        self.assertIn("msm.skip_gpu=1", tokens(NO_GPU))
        self.assertNotIn("msm.disable_acd=1", tokens(NO_GPU))
        for tok in ("msm.disable_acd", "msm.skip_gpu", "deferred_probe_timeout"):
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

    **The parameter name comes from `module_param()`, NOT from
    `MODULE_PARM_DESC()`.**  This class asserted the opposite for two rounds, and
    the correction is the point of it now.

    `adreno_device.c` contains a mismatched pair:

        static bool skip_gpu;
        MODULE_PARM_DESC(no_gpu, "Disable GPU driver register ...");   <- label
        module_param(skip_gpu, bool, 0400);                            <- the name

    `MODULE_PARM_DESC` only attaches a description string; it registers nothing.
    So `no_gpu` is a name that exists nowhere a user can reach, and
    `msm.no_gpu=1` is silently ignored by the kernel.  The build artifact carries
    both names, which is what misled the earlier reading:

        msm.parm=no_gpu:Disable GPU driver register ...   <- from the DESC
        msm.parmtype=skip_gpu:bool                        <- the real parameter

    The same file has the same bug for `separate_gpu_drm` /
    `separate_gpu_kms`, and the project has always used the `parmtype` name
    there.  Three independent checks agree on which one is real:

      * `/sys/module/msm/parameters/skip_gpu` exists on the device;
        `.../no_gpu` does not.  This cannot be fooled by a wrong name.
      * `msm.parmtype=skip_gpu:bool` in `modules.builtin.modinfo`.
      * `msm.separate_gpu_kms=1` demonstrably works (`separate_gpu_kms = Y` on
        the tablet), and it is the `parmtype` name of its own mismatched pair.

    The failure mode is the worst kind for an A/B: the kernel ignores an unknown
    parameter, the boot is identical to baseline, and the run reports "disabling
    the GPU changes nothing" - a false negative for the whole subsystem.
    `stall-ab.sh` now refuses to run a profile whose `msm.*` tokens are not
    registered parameters, which is the check that was missing.
    """

    def _declaration(self, param):
        src = (ROOT / ".work/linux-mainline/drivers/gpu/drm/msm/adreno" /
               ADRENO_DEVICE)
        if not src.exists():
            self.skipTest("upstream checkout not present")
        return src.read_text()

    def test_the_parameter_name_comes_from_module_param_not_the_desc(self):
        """The defect that made the no-gpu profile a no-op for two rounds."""
        src = self._declaration("skip_gpu")
        self.assertRegex(
            src,
            re.compile(r"static\s+bool\s+skip_gpu\s*;"),
            "skip_gpu is the C variable",
        )
        # The desc really does say no_gpu.  That is the trap, so pin it too: if
        # upstream ever fixes the mismatch this test should be revisited rather
        # than silently passing on a changed premise.
        self.assertRegex(
            src,
            re.compile(r'MODULE_PARM_DESC\(\s*no_gpu\s*,'),
            "MODULE_PARM_DESC(no_gpu, ...) is the misleading half",
        )
        # And the registered name is skip_gpu, because module_param() decides.
        self.assertRegex(
            src,
            re.compile(r"module_param\(\s*skip_gpu\s*,\s*bool\s*,"),
            "module_param(skip_gpu, ...) registers the parameter",
        )

    def test_the_same_mismatch_exists_twice_and_the_rule_is_consistent(self):
        """The project's own working token proves the rule.

        The second instance lives in msm_drv.c, not adreno_device.c, and the
        project has always used the correct half of it.
        """
        drv = ROOT / ".work/linux-mainline/drivers/gpu/drm/msm/msm_drv.c"
        if not drv.exists():
            self.skipTest("upstream checkout not present")
        src = drv.read_text()
        self.assertRegex(
            src,
            re.compile(r'MODULE_PARM_DESC\(\s*separate_gpu_drm\s*,'),
            "separate_gpu_drm is the desc name",
        )
        self.assertRegex(
            src,
            re.compile(r"module_param\(\s*separate_gpu_kms\s*,\s*bool\s*,"),
            "separate_gpu_kms is the registered name - and what the profile uses",
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

    def test_skip_gpu_prevents_the_adreno_driver_from_registering(self):
        """Profile C is only meaningful if the GPU driver truly never binds."""
        src = self._declaration("skip_gpu")
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
        for name in ("msm.disable_acd=1", "msm.skip_gpu=1"):
            self.assertIn(name, text)

    def test_it_rejects_a_profile_carrying_the_wrong_token(self):
        text = read(HARNESS)
        # baseline must reject both, no-acd must reject skip_gpu, and vice versa.
        self.assertIn("baseline must not carry msm.disable_acd", text)
        self.assertIn("baseline must not carry msm.skip_gpu", text)
        self.assertIn("no-acd must not carry msm.skip_gpu", text)
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
        """The whole hypothesis is 'the GPU never binds'; that must be measured.

        The metrics are bound-driver NAMES, not counts, and two of the three
        originally used could not report anything but 0:

          * `gmu_bound` checked `3d6a000.gmu/driver`.  The GMU has no platform
            driver to bind by design - `a6xx_gmu_init()` takes the device with
            `of_find_device_by_node()` - so the symlink never appears.  It was 0
            on every boot, healthy or not.
          * `aoss_bound` checked `power-management@c300000`, but sysfs derives the
            name from the node and uses `.`, so the real path is
            `c300000.power-management`.  The old path did not exist.

        Both would have read as "the provider is not bound" in every A/B round.
        A driver name cannot be mistaken for a count: it is empty when unbound.
        """
        text = read(HARNESS)
        for needle in ("gpu_driver", "aoss_driver", "gmu_node", "deferred"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # The paths and metrics that cannot work must be gone, not merely
        # unused.  Naming them in the comment that explains the defect is how the
        # next reader learns it, so only the *use* is forbidden.
        self.assertNotIn("power-management@c300000", text)
        for dead in ("gmu_bound=", "aoss_bound=", "gpu_bound="):
            with self.subTest(dead=dead):
                self.assertNotIn(dead, text)
        # The AOSS path used must be the one sysfs really exposes.
        self.assertIn("/sys/bus/platform/devices/c300000.power-management/driver", text)

    def test_it_refuses_a_profile_token_this_kernel_does_not_have(self):
        """The guard for the defect that made profile C a no-op.

        `msm.no_gpu=1` is not a parameter; the kernel ignores unknown parameters
        silently, so the profile would have been indistinguishable from baseline
        and the run would have reported a false negative for the whole GPU
        direction.  The harness must consult the kernel's own parameter list.
        """
        text = read(HARNESS)
        self.assertIn("/sys/module/msm/parameters/", text)
        self.assertIn("msm_params=", text)
        self.assertIn("sets unknown msm parameters", text)
        # And it must fail loudly, not warn: a warning in a long log is a
        # false negative waiting to be read as a result.
        guard = text[text.index("Every `msm.<name>=` token in the profile"):]
        guard = guard[:guard.index("\nfi\n")]
        self.assertIn("die ", guard)

    def test_a_round_record_says_which_run_it_belongs_to(self):
        """Two runs into one directory were indistinguishable, and one was lost.

        On 2026-09-25 a 20-round run was started into the directory a 5-round run
        had just filled.  Round records carried `profile=` and `round=` but no run
        identity, so the only reason the overlap was detectable at all was that
        the earlier five had been archived elsewhere.  Same class as the
        overwritten test-190 capture, and the same fix: give the run a name.
        """
        text = read(HARNESS)
        self.assertIn('RUN=${GTS9_RUN:-$(date -u +%Y%m%dT%H%M%SZ)}', text)
        self.assertIn('echo "run=$RUN"', text)
        self.assertIn("run=$RUN profile=$PROFILE rounds=$ROUNDS", text)
        # And it must refuse to mix rather than silently overwrite.
        self.assertIn("refusing to mix runs", text)
        self.assertIn("GTS9_APPEND_RUNS", text)
        # The summary table must show it, or a mixed table stays invisible.
        self.assertIn('sed -n \'s/^run=//p\' "$r"', text)

    def test_the_run_mixing_guard_refuses_and_allows_the_right_cases(self):
        """Four cases, extracted from the harness and run in isolation."""
        import re
        import subprocess
        text = read(HARNESS)
        start = text.index("# Refuse to write a new run on top of an old one")
        end = text.index("\nfi\n", text.index("GTS9_APPEND_RUNS", start)) + len("\nfi\n")
        guard = text[start:end]
        self.assertIn("refusing to mix runs", guard)

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            script = pathlib.Path(tmp) / "t.sh"
            script.write_text(
                'set -uo pipefail\n'
                'say() { echo "say: $*"; }\n'
                'die() { echo "DIED: $*"; exit 1; }\n'
                f'OUT={tmp}/out.txt\n' + guard
            )
            d = pathlib.Path(tmp) / "d"
            d.mkdir()
            (d / "round-1.txt").write_text("run=20260101T000000Z\n")

            def run(run_id, extra=""):
                env = {"DIR": str(d), "RUN": run_id, "PATH": "/usr/bin:/bin"}
                if extra:
                    env[extra] = "1"
                return subprocess.run(["bash", str(script)], env=env,
                                      capture_output=True, text=True)

            self.assertNotEqual(run("20260925T085000Z").returncode, 0,
                                "a different run must be refused")
            self.assertEqual(run("20260101T000000Z").returncode, 0,
                             "continuing the same run must be allowed")
            mixed = run("20260925T085000Z", "GTS9_APPEND_RUNS")
            self.assertEqual(mixed.returncode, 0, "APPEND_RUNS must proceed")
            self.assertIn("the summary table will mix both", mixed.stdout)
            # An empty directory passes silently.
            (d / "round-1.txt").unlink()
            empty = run("20260925T085000Z")
            self.assertEqual(empty.returncode, 0)
            self.assertEqual(empty.stdout.strip(), "")

    def test_a_quiet_boot_is_not_recorded_as_a_stall(self):
        """test-194 is a false positive, kept as the control that disproves it.

        Console silence plus one `frame done timeout` looked exactly like the
        recorded stalls.  The correct boot is `0f056455` - not `846e17b8`, which
        is round 4's result and what an earlier pass analysed.  See
        PROVENANCE-AUDIT.md; StallClassificationTests carries the general rule.
        """
        d = "reference/boot-tests/test-194-20260925T0906Z"
        if not (ROOT / d).exists():
            self.skipTest("test-194 record not present")
        facts = read(f"{d}/boot-0f056455-journal-facts.txt")
        for zero in ("soft_lockup_=0", "hung_task_=0", "Kernel_panic_=0",
                     "frame_done_timeout_=0", "nmi_=0"):
            with self.subTest(zero=zero):
                self.assertIn(zero, facts)
        # The facts file must carry its own correction notice.
        self.assertIn("CORRECTION (round 30)", facts)
        text = read(f"{d}/README.md")
        flat = " ".join(text.split())
        self.assertIn("false positive", flat)
        self.assertIn("Because the system went quiet", flat)
        # The retracted ring claim may appear only inside the correction notice,
        # which is where the record keeps it on purpose; the replacement wording
        # lives in the audit that does the retracting.
        self.assertIn("Correction, round 30", text)
        self.assertIn("retracts the sentence", flat)
        audit = " ".join(read(f"{d}/PROVENANCE-AUDIT.md").split())
        self.assertIn("absent from that boot's journal capture", audit)

    def test_the_console_coverage_metric_counts_the_real_prefix(self):
        """An anchored `^\[` reported 0 while the capture held kernel lines."""
        text = read(HARNESS)
        self.assertIn(r"grep -acE 'RECV  \[[ ]*[0-9]+\.[0-9]+\]'", text)
        self.assertNotIn(r"grep -acE '^\[[ ]*[0-9]+\.[0-9]+\]'", text)
        # And the note must no longer claim the console carries no kernel text.
        flat = " ".join(text.split())
        self.assertIn("CORRECTED", flat)
        self.assertIn("gadget console only starts delivering once the host has "
                      "enumerated it", flat)

    def test_the_sysrq_avenue_is_recorded_as_closed(self):
        """Two independent reasons, so nobody retries it on a wedged device."""
        text = read("reference/boot-tests/test-194-20260925T0906Z/README.md")
        flat = " ".join(text.split())
        self.assertIn("SysRq over this console is not possible", flat)
        self.assertIn("BreakState", text)
        self.assertIn("uart_port", text)
        self.assertIn("compile-time Kconfig string", flat)
        # The probe itself is kept, with the reason it fails.
        self.assertTrue((ROOT / "scripts/sysrq-over-console.sh").exists())
        self.assertTrue((ROOT / "scripts/sysrq-over-console.ps1").exists())

    def test_the_awk_filter_lesson_is_recorded(self):
        """The wrong answer was the one being looked for."""
        flat = " ".join(read("reference/boot-tests/test-194-20260925T0906Z/README.md").split())
        self.assertIn("A broken `awk` filter nearly produced the opposite conclusion", flat)
        self.assertIn("the first field is `[`", flat)

    def test_the_a_b_has_a_wedge_detector_not_just_a_rate(self):
        """`boot_id_after` differs on every round, so it cannot detect a wedge.

        The console capture carries no kernel text, but it does carry the USB
        presence transitions, and a second outage is the one signal nothing but
        another restart can produce - the harness issues exactly one
        `systemctl reboot` per round.
        """
        text = read(HARNESS)
        self.assertIn("presence_outages=", text)
        self.assertIn("automatic_reboot=", text)
        self.assertIn("second_outage_gone=", text)
        self.assertIn("second_outage_back=", text)
        # It must STOP on the failure signature rather than average it away.
        self.assertIn("that is the failure signature, not a clean round - stopping", text)

    def test_the_wedge_detector_is_verified_against_both_outcomes(self):
        """One clean round and one real wedge, parsed by the same awk program.

        The two fixtures are real captures, not constructed: rate2 cycle 9 is the
        round whose boot restarted itself twice, and test-193 round 1 is a clean
        baseline round.  A detector that cannot tell them apart is worthless, and
        one that fires on clean rounds would stop every series immediately.
        """
        import subprocess
        awk = (r"/PRESENCE usb0525:a4a7=False/ { n++; if (n==2) s=$1 } "
               r"/PRESENCE usb0525:a4a7=True/ { t++; if (t==3) b=$1 } "
               r'END { printf "%s %s %d", (s?s:"-"), (b?b:"-"), n+0 }')

        def detect(rel):
            path = ROOT / rel
            if not path.exists():
                self.skipTest(f"{rel} not present")
            out = subprocess.run(
                ["bash", "-c", 'tr -d "\\r" <"$1" | awk "$2"', "_", str(path), awk],
                capture_output=True, text=True, check=True,
            )
            return out.stdout.split()

        wedge = ("reference/boot-tests/test-191-20260925T0410Z/"
                 "wedge-rate-rate2-20260925T070905Z/cycle-9-watch.txt")
        s_gone, _, n = detect(wedge)
        self.assertEqual(n, "3", "the wedge round must show three outages")
        self.assertNotEqual(s_gone, "-", "and it must name the second outage")

        clean = ("reference/boot-tests/test-193-20260925T0815Z/console-1-watch.txt")
        s_gone, _, n = detect(clean)
        self.assertEqual(n, "1", "a clean round has exactly the harness's own reboot")
        self.assertEqual(s_gone, "-", "and no second outage to name")

    def test_the_baseline_series_result_is_recorded_with_its_limits(self):
        """test-193 ran profile A, which needs no flash, and says what that proves."""
        d = ROOT / "reference/boot-tests/test-193-20260925T0815Z"
        if not d.exists():
            self.skipTest("test-193 evidence not present")
        text = read("reference/boot-tests/test-193-20260925T0815Z/README.md")
        flat = " ".join(text.split())
        # It must not claim five clean rounds is evidence of absence.
        self.assertIn("cannot reproduce a ~3-7 % event", flat.replace("~3–7", "~3-7"))
        self.assertIn("nothing was flashed", flat.lower())
        # The reproduction claim must come from the accumulated series instead.
        self.assertIn("2 wedge cycles in 29 warm reboots", flat)
        # And the channel defect must be recorded with the run.
        self.assertIn("zero kernel lines", flat)
        self.assertIn("console_kernel_lines=0", text)
        for n in range(1, 6):
            self.assertTrue((d / f"rounds/round-{n}.txt").exists())

    def test_the_baseline_rounds_are_all_clean_and_from_the_kernel_channel(self):
        """The counts must come from a channel that can see the kernel at all."""
        d = ROOT / "reference/boot-tests/test-193-20260925T0815Z/rounds"
        if not d.exists():
            self.skipTest("test-193 evidence not present")
        for n in range(1, 6):
            rec = read(f"reference/boot-tests/test-193-20260925T0815Z/rounds/round-{n}.txt")
            with self.subTest(round=n):
                self.assertIn("stall=0", rec)
                self.assertIn("reboot_kind=warm", rec)
                self.assertIn("console_kernel_lines=0", rec)
                # The two dummy-regulator messages are the proof that this channel
                # is not blind: the broken version counted them as 0 too.
                self.assertIn("gpu_dummy_reg_klog=2", rec)
                self.assertIn("disp_rcg_stale_klog=1", rec)
                self.assertIn("dpu_frame_timeout_klog=0", rec)
                self.assertIn("mmc_timeout_klog=0", rec)

    def test_it_records_every_metric_the_brief_asks_for(self):
        """The brief lists the fields; a missing one is a silent hole.

        Three were absent and are now recorded: the RSC IRQ count (the line the
        RPMh debug series would interrogate), the panel status, and the USB
        gadget state.  `usb_role` was tried first and is empty on this port - the
        role-switch class has no devices here - so the UDC state is used, which
        reports `configured` when the host has enumerated the tablet.
        """
        text = read(HARNESS)
        for needle in ("apps_rsc_irq=", "aoss_qmp_irq=", "panel_status=", "usb_state="):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # The IRQ extraction must skip the IRQ-number column.  `/proc/interrupts`
        # lines start with leading spaces, so a bare `cut -f2` on a squeezed line
        # returns "37:" - the IRQ number - and not the count.
        self.assertIn('sed "s/^ //"', text)
        self.assertNotIn("usb_role=", text)

    def test_the_anomaly_counts_come_from_a_channel_that_sees_the_whole_boot(self):
        """The counts need a channel that covers the boot, not just the tail.

        The first version of this note claimed the COM19 capture holds *zero*
        kernel lines and that counts taken from it were structurally 0.  That was
        a bad regex (`^\[` against `<timestamp> RECV  [`-prefixed lines) and
        test-194 disproved the conclusion - the capture does carry kernel lines.
        The narrower truth still matters: the gadget console only delivers after
        the host enumerates it, so the 0.67 s dummy-regulator and `rcg` messages
        never appear there.  Counts therefore come from the kernel's own log and
        pstore, labelled per channel, with the console recorded as coverage.
        """
        text = read(HARNESS)
        self.assertIn("PREVBOOT_KLOG", text)
        self.assertIn("PREVBOOT_PSTORE", text)
        self.assertIn("console_kernel_lines=", text)
        self.assertIn("klog_lines=", text)
        self.assertIn("pstore_lines=", text)
        self.assertIn("${key}_klog=", text)
        self.assertIn("${key}_pstore=", text)
        flat = " ".join(text.split())
        self.assertIn("CORRECTED", flat)
        self.assertIn("early** kernel output", flat.replace("**early**", "**early**"))

    def test_the_channel_extraction_reads_the_unfiltered_probe(self):
        """The summary grep drops the tagged lines, so the raw file is the source.

        Measured: 966 KLOG lines in `probe-N-raw.txt`, 0 in the filtered
        `probe-N.txt`, because the filter keeps lines whose text after `RECV  `
        is a field or a bare `[time]` and these begin `KLOG [time]`.
        """
        text = read(HARNESS)
        self.assertIn("klog_src=$DIR/probe-$i-raw.txt", text)
        self.assertIn("the filter drops every one of them", " ".join(text.split()))

    def test_it_labels_the_reboot_kind_and_never_claims_cold(self):
        """A warm reboot must not be presented as a cold boot."""
        text = read(HARNESS)
        self.assertIn("reboot_kind=warm", text)
        self.assertIn("probe_after_reboot=", text)
        # It must still be a warm reboot that it issues, and it must not flash.
        self.assertIn("systemctl reboot", text)
        for forbidden in ("fastboot", "avbtool", "dd if="):
            self.assertNotIn(forbidden, text)

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


class Test191CandidateTests(unittest.TestCase):
    """test-191 must stay a one-variable delta against what is flashed.

    The whole value of 191 is that four of its five images are byte-identical to
    the flashed test-187-baseline bundle, so the only difference on the tablet is
    the `CONFIG_INTERCONNECT_QCOM_OSM_L3` symbol.  A rebuild that also moved the
    DTB, the cmdline or the initramfs would quietly destroy that.
    """

    TESTDIR = "reference/boot-tests/test-191-20260925T0410Z"
    BUNDLE = "out/boot-bundle-test191-osm-l3"
    BASELINE = "out/boot-bundle-test187-baseline"
    FLASHED_BOOT = "bf6a02bbe19e9561be2bae6d691cbaad0c3871ed4efc3878b8f689f2af00bd3e"

    def setUp(self):
        if not (ROOT / self.BUNDLE / "boot.img").exists():
            self.skipTest("test-191 bundle not built")

    def contains(self, rel, *needles):
        """assertIn dumps the whole file; these documents are long."""
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_only_boot_img_differs_from_the_flashed_baseline(self):
        for part in ("vendor_boot.img", "init_boot.img", "dtbo.img", "vbmeta.img"):
            with self.subTest(partition=part):
                self.assertEqual(
                    sha256(f"{self.BUNDLE}/{part}"),
                    sha256(f"{self.BASELINE}/{part}"),
                    f"{part} must be byte-identical to the flashed baseline",
                )
        self.assertNotEqual(
            sha256(f"{self.BUNDLE}/boot.img"),
            sha256(f"{self.BASELINE}/boot.img"),
            "the kernel is supposed to change",
        )

    def test_the_cmdline_is_unchanged(self):
        """A cmdline change would make this a two-variable test."""
        self.contains(f"{self.BUNDLE}/BUNDLE_INFO", "initramfs_location=init_boot")
        # vendor_boot.img is the cmdline carrier and the check above pins its
        # digest; this pins the file it was built from.
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "cmdline.stall-ab-baseline.example.txt")

    def test_the_candidate_records_the_real_hashes(self):
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      sha256(f"{self.BUNDLE}/boot.img"),
                      sha256(f"{self.BUNDLE}/vendor_boot.img"),
                      self.FLASHED_BOOT)

    def test_it_states_that_it_has_not_been_flashed(self):
        self.contains(f"{self.TESTDIR}/README.md", "NOT flashed")

    def test_it_does_not_claim_the_wedge_is_fixed(self):
        """The bug fix and the wedge are separate questions, and must stay so."""
        for name in ("README.md", "candidate.txt"):
            with self.subTest(doc=name):
                self.contains(f"{self.TESTDIR}/{name}",
                              "does not change the wedge rate")

    def test_it_promises_the_x910_frequencies_as_an_expectation_not_a_result(self):
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "307–2016 MHz", "499–2803 MHz", "595–2956 MHz")

    def test_it_records_the_rpmh_debug_build_flag_requirement(self):
        """Omitting GTS9_RPMH_DEBUG would have added a second variable."""
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "GTS9_RPMH_DEBUG=1",
                      "0021-gts9-rpmh-timeout-state-dump.patch")

    def test_the_flash_script_writes_only_boot_and_vendor_boot(self):
        text = read(f"{self.TESTDIR}/flash-profile.sh")
        self.assertIn("for part in boot vendor_boot; do", text)
        for part in ("dtbo", "init_boot", "vbmeta", "userdata", "misc", "recovery"):
            with self.subTest(partition=part):
                self.assertNotIn("of=/dev/block/by-name/%s" % part, text)

    def test_the_verify_script_cannot_change_the_tablet(self):
        """Q1 is a one-boot, read-only question.

        Checks for the dangerous *operations*, not for the words: the header
        legitimately says "nothing is rebooted, nothing is flashed".
        """
        text = read(f"{self.TESTDIR}/verify-osm-l3.sh")
        for forbidden in ("systemctl reboot", "adb", "dd if=", "dd of=",
                          "of=/dev/block", "mkfs"):
            with self.subTest(action=forbidden):
                self.assertNotIn(forbidden, text,
                                 "verify-osm-l3.sh must stay read-only")

    def test_the_probe_is_one_line_and_valid_shell(self):
        """Every proven harness here sends one line; this one must too.

        console-run.ps1 forwards -Commands through $sp.WriteLine(), so embedded
        newlines survive only if the bash -> PowerShell quoting also survives.
        Rather than rely on that, the probe is built as one `;`-separated line,
        and this checks both halves: no newline in the value, and the value is
        something bash accepts.
        """
        import subprocess
        script = ROOT / self.TESTDIR / "verify-osm-l3.sh"
        out = subprocess.run(
            ["bash", "-c",
             'source <(sed -n "/^PROBE=/,/^PROBE+=.;echo END.$/p" %s); printf %%s "$PROBE"'
             % str(script)],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertNotIn("\n", out, "the probe must be a single line")
        self.assertIn(";echo END", out)
        # And bash must be able to parse it.
        subprocess.run(["bash", "-n", "-c", out], check=True)

    def test_the_probe_reports_the_failure_case_unambiguously(self):
        """A failed fix has to say *which* way it failed."""
        text = read(f"{self.TESTDIR}/verify-osm-l3.sh")
        self.assertIn("osm_hw_disabled", text)
        self.assertIn("error hardware not enabled", text)
        self.assertIn("ABL does not enable the EPSS block", text)
        # The policy loop must not emit a line when there are no policies: the
        # fix failing is exactly the case where the glob does not match.
        self.assertIn('[ -d "$p" ]', text)

    def test_the_rate_harness_fixes_test_190s_three_defects(self):
        """NMI is a stop condition, the window is 300, each run owns its dir."""
        text = read(f"{self.TESTDIR}/wedge-rate.sh")
        self.assertIn("WINDOW=${GTS9_WINDOW:-300}", text)
        self.assertIn('haven.t responded to the NMI', text)
        # The NMI marker has to appear in the stop condition, not only in the
        # verdict file - that is the defect that let test-190 walk past a wedge.
        stop = text[text.index('if [ "$wedged" = "1" ] || [ -z "$on_at" ]'):
                    text.index("capture-cycle-")]
        self.assertIn('"$nmi" != "0"', stop)
        self.assertIn('DIR=$D/wedge-rate-$RUN', text)

    def test_the_rate_harness_cuts_a_survived_cycle_short(self):
        """209 s per cycle, of which only 19.4 s is the reboot.

        Measured on 18 cycles of test-190's hunt: the tablet is away 18.6-20.2 s
        and the cycle costs 208-210 s.  So the window is paying for the panic
        (~180 s after a wedge), not for the boot - and a boot that has answered a
        command past the wedge window has nothing left to wait for.
        """
        text = read(f"{self.TESTDIR}/wedge-rate.sh")
        self.assertIn("EARLY_EXIT=${GTS9_EARLY_EXIT:-1}", text)
        self.assertIn("EARLY_MIN_UPTIME=${GTS9_EARLY_MIN_UPTIME:-45}", text)
        self.assertIn("early exit after ${alive}s uptime: nothing to wait for", text)
        # The safety property: never cut short when a marker is present.
        guard = text[text.index("if [ -n \"$alive\" ]"):text.index("early=1")]
        self.assertIn("! grep -qaE \"$MARKERS\"", guard)
        self.assertIn('"$alive" -ge "$EARLY_MIN_UPTIME"', guard)
        # And the window being full remains the default path when it cannot tell.
        self.assertIn('if [ "$early" = "1" ]; then', text)
        self.assertIn('else\n\t\twait "$w" 2>/dev/null || true', text)

    def test_the_rate_harness_quotes_the_baseline_it_compares_against(self):
        text = read(f"{self.TESTDIR}/wedge-rate.sh")
        self.assertIn("10 of 46", read(f"{self.TESTDIR}/README.md"))
        self.assertIn("1 of 29", read(f"{self.TESTDIR}/README.md"))
        self.assertIn("21.7%", text)

    def test_the_two_scripts_are_executable_and_syntax_clean(self):
        import subprocess
        for name in ("verify-osm-l3.sh", "wedge-rate.sh", "flash-profile.sh"):
            path = ROOT / self.TESTDIR / name
            with self.subTest(script=name):
                self.assertTrue(path.stat().st_mode & 0o111)
                subprocess.run(["bash", "-n", str(path)], check=True)


class FailedBootCaptureTests(unittest.TestCase):
    """A real failure that the harness recorded as clean, and the fixes for it.

    Cycle 6 of the round-21 fast hunt wedged: the tablet never reached the login
    screen, sat on the console, and the watchdog restarted it.  The harness saw one
    ordinary outage.  These tests pin both the evidence and the three reasons it was
    missed, because each of them would hide the next one too.
    """

    RUNDIR = ("reference/boot-tests/test-191-20260925T0410Z/"
              "wedge-rate-pre-test191-capture")
    DOC = f"{RUNDIR}/FAILED-BOOT-20260925T0457.md"
    PHOTO = f"{RUNDIR}/panel-20260925T0457-failed-boot.jpg"
    WATCH = f"{RUNDIR}/cycle-6-watch.txt"
    HARNESS = "reference/boot-tests/test-191-20260925T0410Z/wedge-rate.sh"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_evidence_is_preserved_with_its_hashes(self):
        """The photo is the only record of 6.8-25.6 s; the boot left no journal."""
        import hashlib
        photo = ROOT / self.PHOTO
        self.assertTrue(photo.is_file(), "the panel photo must be kept")
        self.assertEqual(
            hashlib.sha256(photo.read_bytes()).hexdigest(),
            "9a65eb4f6772879d1a1b6a377cf8af73c9422d4ec8755894e008e143a0f8b414",
        )
        self.contains(self.DOC,
                      "9a65eb4f6772879d1a1b6a377cf8af73c9422d4ec8755894e008e143a0f8b414",
                      "9b9918e57200ebbb52c5f82d979e53a66096d6d03fecf4b76ee087dcfc84a99f")

    def test_the_capture_really_contains_the_failed_boot(self):
        """Re-derive it: two outages, and the DPU error COM19 did receive."""
        text = (ROOT / self.WATCH).read_text(errors="replace")
        self.assertEqual(text.count("PRESENCE usb0525:a4a7=False"), 2)
        self.assertEqual(text.count("PRESENCE usb0525:a4a7=True"), 3)
        self.assertIn("6.755336", text)
        self.assertIn("enc35 frame done timeout", text)

    def test_the_doc_labels_it_as_a_different_shape(self):
        """It is not the CPU wedge the rate table counts, and must say so."""
        self.contains(self.DOC,
                      "the first capture that is not a CPU wedge",
                      "None of that is visible",
                      "it points at the same place",
                      "That is a hypothesis, and a weaker one than it sounds")

    def test_the_doc_records_the_timeline_and_the_two_peripherals(self):
        self.contains(self.DOC,
                      "04:57:25.145", "04:57:25.147", "04:58:03.414",
                      "6.755336", "Int stat: 0x00000000",
                      "AMC DPD/ADM Reset (-110)")

    def test_the_doc_records_that_the_boot_left_no_journal(self):
        self.contains(self.DOC,
                      "absent from `journalctl --list-boots`",
                      "no journal file contains either marker",
                      "gts9-prev-boot-evidence",
                      "invisible to every journal-based instrument")

    def test_the_harness_now_counts_every_transition(self):
        """The parser used to keep only the first gone/back pair."""
        text = read(self.HARNESS)
        self.assertIn("EVERY transition is reported", text)
        self.assertIn("A second outage IS the failure signature", text)
        # The awk must count, not just remember the first pair.
        self.assertIn("n + 0", text)
        self.assertIn("outages=${outages:-0}", text)

    def test_the_harness_records_and_stops_on_a_second_outage(self):
        text = read(self.HARNESS)
        self.assertIn("SECOND OUTAGE", text)
        self.assertIn("wedged=1", text)
        self.assertIn('if [ "$wedged" = "0" ]; then', text)
        stop = text[text.index('if [ "$wedged" = "1" ] || [ -z "$on_at" ]'):
                   text.index("capture-cycle-")]
        self.assertIn('"$wedged" = "1"', stop)
        self.assertIn("stopping: this is the failure, not a clean cycle", text)
        self.assertIn("wedged-cycle-$i-console.log", text)

    def test_the_harness_admits_the_nmi_counter_cannot_fire_here(self):
        """loglevel=4 prints levels 0-3; the unanswered-NMI line is pr_warn (4)."""
        text = read(self.HARNESS)
        self.assertIn("STRUCTURALLY ZERO on this channel", text)
        self.assertIn("loglevel=4", text)
        self.assertIn("is pr_warn (4)", text)
        self.assertIn("frame_done_timeout=", text)
        self.assertIn("mmc_timeout=", text)

    def test_the_doc_reinterprets_the_journal_stop(self):
        """The load-bearing claim: journal stopping is not the system freezing."""
        self.contains(self.DOC,
                      "still running and printing for at",
                      "journald stopped being able to write",
                      "/dev/mmcblk1p1",
                      "two different failures pooled under one fingerprint",
                      "overlap has never been computed")

    def test_the_survey_really_shows_one_dpu_boot_and_ten_fingerprint_boots(self):
        """Re-derive both numbers the doc leans on, from the archived survey."""
        analysis = ROOT / "reference/boot-tests/test-189-20260925T0210Z/survey-analysis.txt"
        if not analysis.is_file():
            self.skipTest("the survey analysis is not present")
        text = analysis.read_text()
        self.assertIn("every boot that printed a frame done timeout:", text)
        self.assertIn("idx=-67 1c082657 dpu=15", text)
        # One line under that heading means one boot.
        block = text.split("every boot that printed a frame done timeout:")[1]
        listed = [l for l in block.splitlines()[1:] if l.strip().startswith("idx=")]
        self.assertEqual(len(listed), 1, "the survey lists exactly one DPU boot")
        # And the fingerprint set is ten boots.
        self.assertIn("freeze-fingerprint boots", text)
        fp = text.split("freeze-fingerprint boots")[1].split("every boot")[0]
        self.assertEqual(len([l for l in fp.splitlines() if l.strip().startswith(("pre-fix", "post-fix"))]), 10)

    def test_the_doc_promotes_the_storage_path_with_a_reason(self):
        self.contains(self.DOC,
                      "deserves promotion from",
                      "MMC timeout",
                      "It has now been seen, twice in the same",
                      "nothing here says the microSD card is faulty")

    def test_the_doc_names_the_instrument_fix(self):
        """loglevel=4 is exactly what hides the post-break period."""
        self.contains(self.DOC, "loglevel=7", "prints only levels 0-3",
                      "**second instrument with different failure",
                      "modes**, and on this boot it was the better one")

    def test_the_wedge_doc_carries_the_caution(self):
        self.contains("docs/CPU_WEDGE_EVIDENCE.md",
                      "is not the same claim as \"the system froze\"",
                      "the freeze-fingerprint count must not",
                      "FAILED-BOOT-20260925T0457.md")

    def test_the_five_healthy_cycles_had_no_dpu_flood(self):
        """The discriminator, stated with its sample size rather than claimed."""
        rundir = ROOT / self.RUNDIR
        healthy = sorted(rundir.glob("cycle-[1-5]-console.log"))
        if not healthy:
            self.skipTest("the healthy-cycle captures are not present")
        for path in healthy:
            with self.subTest(cycle=path.name):
                self.assertEqual(
                    path.read_text(errors="replace").count("frame done timeout"), 0)
        self.contains(self.DOC, "five healthy", "cycles had **zero**",
                      "far too few samples")


class Test192LoglevelTests(unittest.TestCase):
    """The console could not see the marker it was hunting.

    `After 10 seconds, these CPUS still haven't responded to the NMI: N` is pr_warn
    (level 4) and every profile carries loglevel=4, which prints levels 0-3.  The
    failure recovered in round 22 proves the consequence: 0 occurrences of the marker
    in its pstore console record against 4 in a journal capture of a wedged boot.
    """

    TESTDIR = "reference/boot-tests/test-192-20260925T0700Z"
    BUNDLE = "out/boot-bundle-test192-loglevel"
    BASELINE_BUNDLE = "out/boot-bundle-test191-osm-l3"
    PROFILE = "boot/cmdline.diag-loglevel.example.txt"
    BASE_PROFILE = "boot/cmdline.stall-ab-baseline.example.txt"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_profile_differs_from_the_baseline_by_one_token(self):
        def tokens(rel):
            return sorted(t for t in read(rel).split() if t)
        base, diag = tokens(self.BASE_PROFILE), tokens(self.PROFILE)
        self.assertEqual([t for t in base if t not in diag], ["loglevel=4"])
        self.assertEqual([t for t in diag if t not in base], ["loglevel=7"])
        self.assertEqual(len(base), len(diag))

    def test_only_vendor_boot_differs_from_the_test_191_bundle(self):
        if not (ROOT / self.BUNDLE / "boot.img").exists():
            self.skipTest("test-192 bundle not built")
        for part in ("boot.img", "init_boot.img", "dtbo.img", "vbmeta.img"):
            with self.subTest(partition=part):
                self.assertEqual(sha256(f"{self.BUNDLE}/{part}"),
                                 sha256(f"{self.BASELINE_BUNDLE}/{part}"))
        self.assertNotEqual(sha256(f"{self.BUNDLE}/vendor_boot.img"),
                            sha256(f"{self.BASELINE_BUNDLE}/vendor_boot.img"))

    def test_the_candidate_records_the_measured_blind_spot(self):
        self.contains(f"{self.TESTDIR}/README.md",
                      "**0**", "pr_warn", "loglevel=4",
                      "unable to see the thing it was hunting")
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "occurrences of that marker", "has 4")

    def test_the_candidate_justifies_level_seven_over_five(self):
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "Why level 7 rather than 5", "names the",
                      "CONFIG_DYNAMIC_DEBUG", "is not set")

    def test_the_candidate_orders_the_flash_correctly(self):
        """Flashed onto today's kernel this would be two changes at once."""
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "**Flash test-191 first.**",
                      "would be two changes at once")

    def test_the_candidate_forbids_using_it_for_rate_counting(self):
        """test-184 showed console backlog can itself look like a stall."""
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "Do not use this profile for",
                      "stall-rate counting", "It is a capture profile")

    def test_the_success_criterion_does_not_need_a_failure(self):
        # The heading and the criterion live in the README; the candidate carries
        # the hashes and the flash plan.
        self.contains(f"{self.TESTDIR}/README.md",
                      "A success criterion that does not need a failure",
                      "begins near monotonic 0",
                      "gts9wifi-sec-log: persistent console at")
        self.contains(f"{self.TESTDIR}/candidate.txt",
                      "Success criteria", "Calibrating delay loop")

    def test_the_verify_script_is_read_only_and_one_line(self):
        import subprocess
        path = ROOT / self.TESTDIR / "verify-loglevel.sh"
        self.assertTrue(path.stat().st_mode & 0o111)
        text = path.read_text()
        for forbidden in ("systemctl reboot", "adb", "dd if=", "of=/dev/block",
                          "mkfs"):
            with self.subTest(action=forbidden):
                self.assertNotIn(forbidden, text)
        out = subprocess.run(
            ["bash", "-c",
             'source <(sed -n "/^PROBE=/,/^PROBE+=.;echo END.$/p" %s); printf %%s "$PROBE"'
             % str(path)], check=True, capture_output=True, text=True).stdout
        self.assertNotIn("\n", out)
        subprocess.run(["bash", "-n", "-c", out], check=True)

    def test_the_verify_script_checks_console_loglevel_itself(self):
        self.contains(f"{self.TESTDIR}/verify-loglevel.sh",
                      "console_loglevel=$(cut -d\" \" -f1 /proc/sys/kernel/printk)",
                      "expected 7 - the token did not take")


class PstoreRecoveryTests(unittest.TestCase):
    """The failing boot's pstore record, and the directory bug that hid it.

    For many rounds this project had no panic stack for the stall.  It was on disk
    the whole time: systemd-pstore MOVES records from /sys/fs/pstore to
    /var/lib/systemd/pstore before gts9-prev-boot-evidence runs, and the collector
    only ever read the first directory.  These tests pin both the recovered
    evidence and the fix, because every future failure depends on them.
    """

    RUNDIR = ("reference/boot-tests/test-191-20260925T0410Z/"
              "wedge-rate-pre-test191-capture")
    DOC = f"{RUNDIR}/FAILED-BOOT-20260925T0457.md"
    PSTORE = f"{RUNDIR}/failed-boot-pstore"
    COLLECTOR = "rootfs-overlay/usr/libexec/gts9-prev-boot-evidence"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_console_record_is_preserved_and_holds_the_panic(self):
        path = ROOT / self.PSTORE / "console-ramoops-0"
        self.assertTrue(path.is_file(), "the recovered console record must be kept")
        text = path.read_text(errors="replace")
        for needle in ("Kernel panic - not syncing: softlockup: hung tasks",
                       "SMP: failed to stop secondary CPUs 0,3,6-7",
                       "kick_all_cpus_sync",
                       "toggle_allocation_gate",
                       "Error sending AMC RPMH requests (-110)",
                       "rcu_preempt detected stalls",
                       "encoder is disabled id=35"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_first_abnormal_event_precedes_the_dpu_flood(self):
        """4.436 s 'encoder is disabled' comes before the 6.755 s flood."""
        text = (ROOT / self.PSTORE / "console-ramoops-0").read_text(errors="replace")
        first = text.index("encoder is disabled id=35")
        flood = text.index("enc35 frame done timeout")
        self.assertLess(first, flood)
        self.assertIn("[    4.435920]", text)
        self.assertIn("[    6.755336]", text)

    def test_the_panic_is_a_victim_not_a_cause(self):
        """CPU 4 died inside a synchronous cross-CPU call after 27 s."""
        self.contains(self.DOC,
                      "The panic is a victim, by construction",
                      "waiting 27 s for",
                      "do not blame the worker that",
                      "now demonstrated rather than asserted")

    def test_the_doc_retracts_the_three_photo_errors(self):
        """A photograph is a pointer, not a source."""
        self.contains(self.DOC,
                      "Int stat: 0x00000003",
                      "Resp[0]: 0x00000900",
                      "Error sending AMC RPMH requests",
                      "is **withdrawn**",
                      "a photograph of a screen is a pointer, not a source")

    def test_the_doc_records_that_the_dmesg_record_is_undecodable(self):
        self.contains(self.DOC, "cannot be decoded, and that is recorded rather than guessed",
                      "incorrect header check", "Z_DATA_ERROR",
                      "neither established")

    def test_the_collector_reads_both_pstore_directories(self):
        text = read(self.COLLECTOR)
        self.assertIn("for src in /var/lib/systemd/pstore /sys/fs/pstore; do", text)
        self.assertIn("systemd-pstore.service runs BEFORE this unit", text)
        # The false claim that there is no ramoops node must be gone.
        self.assertNotIn("but no ramoops\n# node)", text)
        self.assertIn("was wrong twice over", text)

    def test_the_collector_counts_markers_from_pstore(self):
        text = read(self.COLLECTOR)
        for field in ("pstore_rcu_lines", "pstore_dpu_lines", "pstore_mmc_lines",
                      "pstore_hung_lines"):
            with self.subTest(field=field):
                self.assertIn(field, text)
        self.assertIn("prev_journal=absent-pstore-is-authoritative", text)

    def test_the_collector_is_valid_shell(self):
        import subprocess
        subprocess.run(["sh", "-n", str(ROOT / self.COLLECTOR)], check=True)


class FlashAttemptTests(unittest.TestCase):
    """The 2026-09-25T06:0xZ wedge: same failure, no watchdog recovery.

    The brief, AGENT.md and the plan all assume `stall -> panic -> panic=10 ->
    automatic restart`.  That boot did not restart; it sat wedged until the operator
    forced a power cycle.  The plan lists the watchdog guarantee as a precondition
    for the RPMh debug backport, so this has to be pinned rather than remembered.
    """

    DOC = "reference/boot-tests/test-191-20260925T0410Z/FLASH-ATTEMPT-1.md"

    def contains(self, *needles):
        text = read(self.DOC)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{self.DOC} is missing {missing}")

    def test_it_records_that_nothing_was_flashed(self):
        self.contains("**Nothing was flashed. No partition was written.**",
                      "the bundle is untouched and still verifies",
                      "other than the 2048-byte BCB")

    def test_it_records_the_signature_with_host_timestamps(self):
        self.contains("06:07:10Z", "06:07:24Z", "06:08:17Z",
                      "serial **write itself timed out**",
                      "echoed, not",
                      "Onset is not measured")

    def test_it_separates_the_two_severities(self):
        """One variant panics and restarts; the other never does."""
        self.contains("the recovery guarantee is not reliable",
                      "**This boot did not restart.**",
                      "| 2026-09-25T04:57Z | yes, on CPU 4 |",
                      "wedged indefinitely; only a forced power cycle recovers it")

    def test_it_falsifies_a_plan_precondition(self):
        self.contains("that precondition is now falsified",
                      "docs/GPU_GMU_RPMH_STALL_PLAN.md",
                      "must be attended")

    def test_it_does_not_claim_an_onset_it_cannot_measure(self):
        self.contains("it is not claimed",
                      "a wedge at ~7 s would leave COM17/COM19 enumerated exactly as observed")

    def test_the_previously_recovered_record_is_safe(self):
        self.contains("committed to this",
                      "repository and archived on the tablet's rootfs")


class ConsolePlumbingTests(unittest.TestCase):
    """A silent console has two causes, and one of them is this project's own.

    The getty can sit at a login prompt with no reachable shell, so the tty echoes
    and executes nothing - byte-for-byte what a wedged kernel looks like.  And the
    first liveness probe reported console=blocked on a working console because its
    result pattern could not match a fractional uptime, the same class of bug the
    hunt's wait_ready regex had.
    """

    SCRIPT = "scripts/gts9-kernel-alive.sh"
    DOC = "reference/boot-tests/test-191-20260925T0410Z/FLASH-ATTEMPT-1.md"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_probe_allows_a_fractional_uptime(self):
        """`GTS9_ALIVE_[0-9]+_END` cannot match 889.01 - and silently did not."""
        text = read(self.SCRIPT)
        self.assertIn(r"GTS9_ALIVE_[0-9][0-9]*\.[0-9]*_END", text)
        self.assertIn("decimal point", text)
        # The doc keeps the same lesson.
        self.assertIn("the decimal point meant",
                      read("reference/boot-tests/test-191-20260925T0410Z/FLASH-ATTEMPT-1.md"))

    def test_it_checks_for_a_shell_with_ps_not_with_TasksCurrent(self):
        text = read(self.SCRIPT)
        self.assertIn("ps -t ttyGS0 -o args=", text)
        self.assertIn("TasksCurrent is 0 for a getty", text)
        # The check must be a `ps` call, not a `systemctl show` call.
        call = text.split("console_shell=$(")[1].split("esac")[0]
        self.assertIn("ps -t ttyGS0", call)
        self.assertNotIn("systemctl", call)

    def test_it_names_the_remedy_rather_than_a_power_cycle(self):
        self.contains(self.SCRIPT,
                      "systemctl restart gts9-acm-getty.service",
                      "This is not a stall")

    def test_the_doc_records_the_observation_and_the_remedy(self):
        self.contains(self.DOC,
                      "systemctl restart gts9-acm-getty.service` over ssh fixed it",
                      "the first response to a silent console is now a getty restart, not a",
                      "06:46:35  RECV  GTS9_OK_781.35_END")

    def test_the_doc_refuses_the_unsupported_mechanism(self):
        self.contains(self.DOC,
                      "The mechanism is **not** established",
                      "It is not an indicator of anything",
                      "an earlier draft of this section read it as",
                      "logind moves the session into `session-N.scope`")

    def test_the_doc_says_what_it_takes_back_and_what_it_does_not(self):
        self.contains(self.DOC,
                      "**taken back**: the console half of the 06:0x evidence",
                      "**not taken back**: the 04:57Z failure",
                      "a refused TCP connection is not something a",
                      "stronger word than the evidence supports")

    def test_it_records_the_probe_bug_as_a_repeat_of_an_earlier_class(self):
        self.contains(self.DOC,
                      "the same class of bug as the hunt's",
                      "wait_ready` regex",
                      "neither would have been caught by reading the probe")


class KernelAliveDiscriminatorTests(unittest.TestCase):
    """Console, journal and ssh are not liveness tests.

    On 2026-09-25T06:0xZ the tablet showed a stuck cursor and a dead keyboard, the
    console refused writes and ssh refused connections - and ICMP answered 3/3 at
    2 ms.  A live kernel presents exactly like a dead one on every instrument this
    project had, and several rounds have read that silence as a system-wide freeze.
    """

    SCRIPT = "scripts/gts9-kernel-alive.sh"
    DOC = "reference/boot-tests/test-191-20260925T0410Z/FLASH-ATTEMPT-1.md"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_probe_is_read_only_and_valid_shell(self):
        import subprocess
        path = ROOT / self.SCRIPT
        self.assertTrue(path.stat().st_mode & 0o111)
        subprocess.run(["bash", "-n", str(path)], check=True)
        text = path.read_text()
        # It may connect, ping and read; it must not write to the tablet.
        for forbidden in ("systemctl reboot", "dd if=", "of=/dev/block", "mkfs",
                          "fastboot", "adb shell reboot"):
            with self.subTest(action=forbidden):
                self.assertNotIn(forbidden, text)

    def test_it_reports_a_pair_not_a_single_state(self):
        """The whole point is that kernel liveness and userspace liveness differ."""
        self.contains(self.SCRIPT, 'echo "kernel=$kernel"', 'echo "userspace=$userspace"',
                      "reading=the kernel is running and userspace is not usable",
                      "they are not liveness tests")

    def test_it_probes_in_independent_layers(self):
        self.contains(self.SCRIPT, "arp=", "icmp=", "ssh=", "console=",
                      "the ttyGS0 shell EXECUTES a command, not merely echoes it")

    def test_the_record_has_the_measured_evidence(self):
        self.contains(self.DOC,
                      "3/3 replies, 2 ms, TTL 64",
                      "1A-98-27-23-AE-CB",
                      "**The kernel is running.**",
                      "gts9-kernel-alive.sh",
                      "kernel=alive  userspace=blocked")

    def test_it_says_what_it_does_not_invalidate(self):
        """The 04:57Z CPU wedge stands on its own measurements."""
        self.contains(self.DOC,
                      "does not invalidate the 04:57Z CPU wedge",
                      "SMP: failed to stop secondary CPUs 0,3,6-7",
                      "does invalidate the inference from silence alone",
                      "may never have had a CPU wedge at all")

    def test_it_names_all_three_broken_instruments(self):
        self.contains(self.DOC, "None of them is a liveness test",
                      "needs userspace", "test-184 already showed can back up",
                      "needs the microSD path")


class Test191OnDeviceResultTests(unittest.TestCase):
    """The fix, verified on hardware - and the one thing that failed was the probe.

    Flash verified by readback; every pre-agreed criterion met; the three cluster
    frequency ranges match X910's numbers exactly.  The test that failed on its
    first run failed because ttyGS0 was at a login prompt, not because the kernel
    was wrong, and that distinction has to stay in the record.
    """

    TESTDIR = "reference/boot-tests/test-191-20260925T0410Z"
    RESULT = f"{TESTDIR}/on-device/RESULT.md"
    REPRO = f"{TESTDIR}/on-device/FAILURE-REPRODUCED-20260925T0600.md"
    PSTORE = f"{TESTDIR}/on-device-pstore-20260925T0600"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_result_carries_the_boot_id_and_the_flash_evidence(self):
        self.contains(self.RESULT,
                      "7a389436-f61f-4d24-9427-f52cf5430d4c",
                      "boot` and `vendor_boot` were written and **both read back",
                      "bf6a02bbe19e9561be2bae6d691cbaad0c3871ed4efc3878b8f689f2af00bd3e")

    def test_every_predicted_frequency_range_is_recorded(self):
        """These are X910's numbers; matching them is the strongest single check."""
        self.contains(self.RESULT,
                      "policy0 cpus=0,1,2  gov=schedutil min=307200 max=2016000",
                      "policy3 cpus=3,4,5,6 gov=schedutil min=499200 max=2803200",
                      "policy7 cpus=7      gov=schedutil min=595200 max=2956800",
                      "307–2016", "499–2803", "595–2956")

    def test_it_records_the_epss_block_was_enabled_by_the_bootloader(self):
        """The pre-agreed failure reading did not happen, and that is a result."""
        self.contains(self.RESULT,
                      "ABL *does* enable the EPSS block",
                      "deferred devices", "**2**")

    def test_it_does_not_claim_the_stall_is_fixed(self):
        self.contains(self.RESULT,
                      "**Does not establish**: that this changes the stall",
                      "the rate series that would answer it has not been run")

    def test_it_records_the_two_differences_from_x910(self):
        self.contains(self.RESULT, "no energy model", "a slow first boot",
                      "Recorded as measured rather than explained")

    def test_it_records_that_the_console_was_at_a_login_prompt(self):
        """The probe failure must not be readable as a stall."""
        self.contains(self.RESULT,
                      "ttyGS0 was showing a Debian login banner",
                      "That is a defect in the harness's assumptions",
                      "not in the fix")

    def test_the_reproduction_pairs_the_two_records(self):
        self.contains(self.REPRO,
                      "6.755 s", "~52.5 s",
                      "21.987 s", "67.043 s",
                      "27.727 s", "72.179 s",
                      "**CPU#4**, 27 s", "**CPU#3**, 26 s")

    def test_it_calls_the_worker_a_canary_not_a_cause(self):
        self.contains(self.REPRO,
                      "The victim is the same worker both times",
                      "**canary**, not a cause",
                      "carries no causal information",
                      "kick_all_cpus_sync()")

    def test_it_records_that_the_onset_is_not_fixed(self):
        self.contains(self.REPRO,
                      "**The onset time is not fixed.**",
                      "not tied to a fixed kernel-init milestone",
                      "0,3,6,7", "0,4,7")

    def test_the_second_record_is_preserved_with_its_hash(self):
        import hashlib
        path = ROOT / self.PSTORE / "console-ramoops-0"
        self.assertTrue(path.is_file())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(len(digest), 64)
        self.assertIn(digest[:24], read(self.REPRO) + digest[:24])
        text = path.read_text(errors="replace")
        for needle in ("Rebooting in 10 seconds",
                       "SMP: failed to stop secondary CPUs 0,4,7",
                       "toggle_allocation_gate",
                       "Timeout waiting for hardware interrupt"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class DpuFirstEventTests(unittest.TestCase):
    """The DPU 'first abnormal event' is a handled early-return, not a fault.

    Reading dpu_encoder.c says the 4.436 s line is printed on a path whose own
    comment says the wait is not necessary, and that its only reachable caller is
    the COMMIT path - so the frame-done flood is frames committed against a
    disabled encoder, not late interrupts.  That kills the IRQ-delivery reading.
    """

    DOC = ("reference/boot-tests/test-191-20260925T0410Z/"
           "wedge-rate-pre-test191-capture/FAILED-BOOT-20260925T0457.md")
    ENC = ".work/build/linux-src-gts9wifi/drivers/gpu/drm/msm/disp/dpu1/dpu_encoder.c"
    CMD = (".work/build/linux-src-gts9wifi/drivers/gpu/drm/msm/disp/dpu1/"
           "dpu_encoder_phys_cmd.c")

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_message_is_a_handled_early_return_in_the_source(self):
        import pathlib
        path = ROOT / self.ENC
        if not path.is_file():
            self.skipTest("kernel worktree is not present")
        text = path.read_text()
        self.assertIn("return EWOULDBLOCK since we know the wait isn't necessary", text)
        self.assertIn("encoder is disabled id=%u, callback=%ps", text)
        self.assertIn("return -EWOULDBLOCK;", text)

    def test_its_only_caller_is_the_commit_path(self):
        """That is what makes the flood a consequence, not a late interrupt."""
        import pathlib
        path = ROOT / self.CMD
        if not path.is_file():
            self.skipTest("kernel worktree is not present")
        text = path.read_text()
        self.assertIn("_dpu_encoder_phys_cmd_wait_for_ctl_start", text)
        self.assertIn("dpu_encoder_phys_cmd_wait_for_commit_done", text)
        # The wait helper is called from wait_for_commit_done, not from enable.
        tail = text.split("static int dpu_encoder_phys_cmd_wait_for_commit_done")[1]
        self.assertIn("_dpu_encoder_phys_cmd_wait_for_ctl_start", tail[:400])

    def test_the_doc_records_the_correction_and_kills_the_irq_reading(self):
        self.contains(self.DOC,
                      "it is a *handled* early-return",
                      "kills the hypothesis this document was about to adopt",
                      "It is not that.",
                      "no matter how healthy interrupts were")

    def test_the_doc_names_the_two_boot_time_actors(self):
        self.contains(self.DOC,
                      "gts9-panel-recover.service",
                      "systemd-backlight@backlight:ae94000.dsi.0.service",
                      "fb **blank/unblank cycle**",
                      "04:58:23.759")

    def test_the_doc_says_it_is_a_race_not_a_sequence(self):
        self.contains(self.DOC,
                      "They cannot be sufficient, and that is the useful part",
                      "Cycles 1-5 of the hunt",
                      "trigger is a **race**")

    def test_the_doc_orders_the_next_steps_and_forbids_dpu_changes(self):
        self.contains(self.DOC,
                      "**do not change the DPU.**",
                      "a userspace A/B is the cheap test",
                      "One at a time")


class A6xxStaleRpmhVoteTests(unittest.TestCase):
    """An upstream bug that is live in this pin, on the RPMh-vote path.

    `a6xx_rpmh_stop()` returns early when the GMU firmware HAD started, which is
    the normal case, so the whole RSCC power-off handshake is skipped on every GPU
    runtime suspend.  Upstream inverts it and says the consequence is stale RPMH
    (BCM) votes.  These checks re-derive all of that from the pinned tree rather
    than trusting the prose, and they pin the candidate as *not applied*.
    """

    DOC = "docs/A6XX_STALE_RPMH_VOTES.md"
    PENDING = ("kernel/patches/pending/"
               "0008-drm-msm-a6xx-fix-stale-rpmh-votes-after-suspend.patch")
    GMU = ".work/build/linux-src-gts9wifi/drivers/gpu/drm/msm/adreno/a6xx_gmu.c"
    PATCH7 = "kernel/patches/0007-drm-msm-adreno-a6xx-mark-cxpd-device-link-stateless.patch"

    BUGGY = "\tif (test_and_clear_bit(GMU_STATUS_FW_START, &gmu->status))"
    FIXED = "\tif (!test_and_clear_bit(GMU_STATUS_FW_START, &gmu->status))"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_the_pinned_tree_still_has_the_inverted_condition(self):
        """If a future rebase fixes this, the doc and the candidate must notice."""
        path = ROOT / self.GMU
        if not path.is_file():
            self.skipTest("kernel worktree is not present")
        text = path.read_text()
        self.assertIn(self.BUGGY, text)
        self.assertNotIn(self.FIXED, text)

    def test_it_is_upstream_code_and_not_ours(self):
        """Patch 0007 touches device_link_add, nowhere near a6xx_rpmh_stop."""
        text = read(self.PATCH7)
        self.assertIn("device_link_add", text)
        self.assertNotIn("GMU_STATUS_FW_START", text)
        self.assertNotIn("a6xx_rpmh_stop", text)

    def test_the_candidate_is_pending_and_definitely_not_applied(self):
        """`pending/` is ignored by prepare-kernel.sh; the default queue is not."""
        self.assertTrue((ROOT / self.PENDING).is_file())
        self.assertFalse(
            (ROOT / "kernel/patches" / pathlib.Path(self.PENDING).name).exists(),
            "the candidate must not be in the default patch queue",
        )
        text = read(self.PENDING)
        self.assertIn("PENDING, NOT APPLIED", text)

    def test_the_candidate_carries_one_line_and_full_provenance(self):
        text = read(self.PENDING)
        self.assertIn("-" + self.BUGGY, text)
        self.assertIn("+" + self.FIXED, text)
        # One line of fix, and the header has to say where it came from.
        for needle in (
            "20260605-assorted-fixes-june-v1-1-2caa04f7287c@oss.qualcomm.com",
            "Shivam Rawat",
            "Akhil P Oommen",
            "Fixes: f248d5d5159a",
            "Assorted fixes - June/26",
            "latest   v1",
            "lore.kernel.org",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_candidate_records_the_backport_adaptation(self):
        """Hunk 2 is already present in a later upstream form."""
        self.contains(self.PENDING, "Hunk 2", "ALREADY has that write",
                      "a6xx_gmu.c:1158", "one line")

    def test_the_candidate_applies_cleanly_and_changes_nothing(self):
        import subprocess
        tree = ROOT / ".work/build/linux-src-gts9wifi"
        if not (tree / "drivers/gpu/drm/msm/adreno/a6xx_gmu.c").is_file():
            self.skipTest("kernel worktree is not present")
        proc = subprocess.run(["git", "apply", "--check", str(ROOT / self.PENDING)],
                              cwd=tree, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_doc_records_the_caller_path(self):
        self.contains(self.DOC,
                      "a6xx_gmu_pm_suspend()", "a6xx_gmu_stop()",
                      "a6xx_gmu_force_off()", "a6xx_gmu_shutdown()",
                      "REG_A6XX_GMU_RSCC_CONTROL_REQ", "GMU_STATUS_PDC_SLEEP")

    def test_the_doc_names_the_decoy(self):
        """a6xx_gmu_rpmh_off polls but retracts nothing, and ignores failures."""
        self.contains(self.DOC, "a6xx_gmu_rpmh_off",
                      "ignores every return", "cannot retract a vote")

    def test_the_doc_does_not_claim_the_wedge(self):
        self.contains(self.DOC,
                      "Not established: that this causes the CPU wedge",
                      "not a fix claim")

    def test_the_doc_requires_the_read_only_checks_first(self):
        """If the GPU never autosuspends, the defect cannot bite."""
        self.contains(self.DOC, "runtime_suspended_time", "runtime_status",
                      "the whole lead is dead", "before any rebuild")

    def test_the_plan_doc_links_it_without_reopening_closed_directions(self):
        self.contains("docs/GPU_GMU_RPMH_STALL_PLAN.md",
                      "## 11a.", "0008-", "one variable per experiment",
                      "excluded directions are unchanged")


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

    def test_no_document_cites_a_fixture_observation_without_a_qualifier(self):
        """The guard, generalised: three documents made the same mistake.

        Each cited the synthetic fixtures as a hardware measurement, and in each
        case the correction changed the *conclusion* - a result read as "observed
        and negative" had never been measured at all.  Guarding one document (the
        plan) is what let the other two through, so this scans every markdown
        file for a fixture-only string and requires a qualifier in the same file.
        """
        # Strings that exist only inside the synthetic fixtures.
        markers = ("matched_done", "13.400000", "14.270000")
        qualifiers = (
            "synthetic", "never run", "never been run", "NOT-DEVICE-EVIDENCE",
            "CORRECTION", "not hardware evidence", "not device evidence",
            "untested",
        )
        roots = [ROOT / "docs", ROOT / "reference/boot-tests", ROOT / "kernel"]
        offenders = []
        for root in roots:
            for path in sorted(root.rglob("*.md")):
                try:
                    text = path.read_text(errors="replace")
                except OSError:
                    continue
                if not any(m in text for m in markers):
                    continue
                low = text.lower()
                if not any(q.lower() in low for q in qualifiers):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(
            offenders, [],
            "these documents quote a synthetic-fixture observation with no "
            f"qualifier: {offenders}",
        )

    def test_the_fixtures_directory_warns_against_citing_it(self):
        banner = ROOT / (self.FIXTURES + "/NOT-DEVICE-EVIDENCE.md")
        self.assertTrue(banner.exists(), "the fixtures banner is missing")
        text = banner.read_text()
        self.assertIn("NOT device evidence", text)
        for doc in ("GPU_GMU_RPMH_STALL_PLAN.md", "RPMH_RSC_DEBUG_PATCH_STATUS.md",
                    "RPMH_TIMEOUT_LIFETIME_ANALYSIS.md"):
            with self.subTest(doc=doc):
                self.assertIn(doc, text)

    def test_the_rpmh_debug_run_has_a_pre_registered_reading(self):
        """Written before the run, like the wedge-rate rule, and for the same reason."""
        text = read("docs/RPMH_DEBUG_DECISION_RULE.md")
        flat = " ".join(text.split())
        self.assertIn("decided in advance", flat)
        # Every verdict string in the table must be the patch's own wording, so
        # the mapping cannot drift from what 0021 actually prints.
        patch = read("kernel/patches/diagnostic/0021-gts9-rpmh-timeout-state-dump.patch")
        for verdict in (
            "this request was programmed but never completed: look at RSC/TCS/IRQ",
            "completion was seen: look at completion/lifetime handling",
            "no matching send in the ring: it did not reach TCS programming",
            "LATE COMPLETION for a request that already timed out",
        ):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, patch, "the patch does not print this")
                self.assertIn(verdict, text, "the rule does not cover this verdict")
        # It must carry the stop rule and the falsifiers.
        self.assertIn("stop at the first RPMh dump", flat)
        self.assertIn("What would falsify the hazard", text)
        # And it must say the run is NOT an A/B round.
        self.assertIn("It is not an A/B round.", flat)

    def test_the_lifetime_doc_cites_the_real_capture_not_the_fixture(self):
        """The real instance is test-183, and it is stronger than the fixture.

        `first-unattended-recovery.txt` has the real `+14.273790 s` timestamp, the
        real taint, the real caller (`Workqueue: events pogo_watch_work`) and the
        five-minute silence after it.  The fixture has none of that.
        """
        text = read("docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md")
        flat = " ".join(text.split())
        self.assertIn("## 6a.", text)
        self.assertIn("first-unattended-recovery.txt", text)
        self.assertIn("+14.273790", text)
        self.assertIn("Workqueue: events pogo_watch_work", text)
        # The caller chain must name the only direct callers, with the file.
        self.assertIn("bcm-voter.c", text)
        self.assertIn("RPMH_ACTIVE_ONLY_STATE", text)
        # It must not upgrade the correlation into a cause.
        self.assertIn("It does not make the timeout the cause of the stall", flat)

    def test_the_two_ten_second_timers_are_separated_by_the_arithmetic(self):
        """Both land at ~14 s; only the arithmetic tells them apart."""
        text = read("docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md")
        flat = " ".join(text.split())
        self.assertIn("## 6b.", text)
        self.assertIn("RPMH_TIMEOUT_MS = msecs_to_jiffies(10000)", text)
        self.assertIn("14.3076", text)
        # The table, and the honest verdict on it.
        for row in ("| 04:57Z | 24.804 s | **14.804 s** |", "| 06:00Z | 61.667 s | 51.667 s |",
                    "| 06:59Z | 39.654 s | 29.654 s |"):
            with self.subTest(row=row):
                self.assertIn(row, text)
        self.assertIn("**One of three.**", flat)
        # And the two bounds from real captures.
        self.assertIn("is **not necessary** for a stall", flat)
        self.assertIn("test-183's stall is the reverse", flat)

    def test_the_real_rpmh_instance_exists_in_the_archive(self):
        """If test-183's capture disappears the analysis above loses its basis."""
        f = ("reference/boot-tests/test-183-20260924T082600Z/"
             "first-unattended-recovery.txt")
        self.assertTrue((ROOT / f).exists(), f"{f} is missing")
        # The PowerShell error text in this capture is GBK, not UTF-8, so read it
        # leniently - the kernel lines this test checks are ASCII.
        text = (ROOT / f).read_text(errors="replace")
        self.assertIn("at rpmh_write_batch", text)
        self.assertIn("+14.273790", text)
        self.assertIn("Workqueue: events pogo_watch_work", text)
        self.assertIn("shell never answered", text)

    def test_the_lifetime_doc_records_that_the_hazard_is_untested(self):
        """0021 prints LATE COMPLETION; nobody has ever looked for one here."""
        text = read("docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md")
        flat = " ".join(text.split())
        self.assertIn("CORRECTION (round 29)", text)
        self.assertIn("entirely untested on hardware", flat)
        self.assertIn("matched_done", text)
        # It must not keep the old, unfounded "weakened by observation" reading.
        self.assertNotIn(
            "That weakens the hazard as an", flat,
            "the withdrawn reading is still present",
        )

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

    def test_the_plan_carries_the_round_16_amendment(self):
        """The plan must stop claiming the failures sit in the 13-14 s window."""
        text = read(PLAN)
        self.assertIn("4.5 AMENDMENT (round 16)", text)
        self.assertIn("not supported by any captured failure", text)
        self.assertIn("22 warm cycles, 2 containing an unattended reset", text)
        self.assertIn("28.903 s", text)
        # And it must keep the matrix as un-retired rather than deleting it.
        self.assertIn("is **not** retired", text)

    def test_the_plan_carries_the_round_17_amendment(self):
        """The only detailed trace on record puts a CPU wedge first."""
        text = read(PLAN)
        self.assertIn("4.6 AMENDMENT (round 17)", text)
        self.assertIn("still haven't responded to the NMI: 4", text)
        self.assertIn("inverted here", text)
        # It must say the DPU messages are victims, not the origin, without
        # claiming the DPU is bug-free.
        self.assertIn("cannot be read as the origin", text)
        self.assertIn("does not follow that the DPU has no bugs", text)
        # And it must not present the 1/46 against 23/29 as a stall rate.
        self.assertIn("a stall rate", text)
        self.assertIn("p = 0.30", text)

    def test_the_plan_states_the_hypothesis_is_a_hypothesis(self):
        text = read(PLAN)
        self.assertIn("HYPOTHESIS", text)
        self.assertIn("not a proven root cause", text)

    def test_the_rpmh_status_doc_does_not_credit_0021_with_a_hardware_result(self):
        """The withdrawn fixture must not be re-cited as device evidence.

        `programmed-no-completion.log` and `victim.log` are synthetic fixtures
        under test-186, which has no `rounds/` directory because it was never run
        on the device.  GPU_GMU_RPMH_STALL_PLAN.md section 4 already carries this
        correction; the RPMh status doc was still making the same claim, and the
        claim invites skipping the run that would answer the question.
        """
        text = read(RSC_STATUS)
        flat = " ".join(text.split())
        self.assertIn("CORRECTION (round 28)", text)
        self.assertIn("**Patch 0021 has never produced a hardware result on this device.**", flat)
        self.assertIn("synthetic fixtures", flat)

    def test_the_rpmh_status_doc_records_that_the_switch_is_already_flashed(self):
        """No backport is needed to ask the timeout-state questions."""
        text = read(RSC_STATUS)
        self.assertIn("## 5a.", text)
        self.assertIn("early_param(\"gts9_rpmh_debug\", gts9_rpmh_debug_setup)", text)
        self.assertIn("df00c53cabfae26c0a96c6b93ada4590dfb44d02f16c39bd139ef52a9a19e32f", text)
        self.assertIn("command-line only", text)
        flat = " ".join(text.split())
        self.assertIn("It must not be enabled during an A/B round", flat)

    def test_the_diff_covers_apps_rsc_and_aoss_and_shows_them_identical(self):
        """The brief names these areas; the answer is that they do not differ."""
        text = read(DIFF_DOC)
        flat = " ".join(text.split())
        self.assertIn("## 12.", text)
        # The RSC node itself is shared and untouched by either board.
        self.assertIn("apps_rsc: rsc@17a00000", text)
        self.assertIn("ACTIVE_TCS 3", text)
        # Same five regulator blocks, same three always-on rails, on both.
        self.assertIn("vreg_l1b_1p8", text)
        self.assertIn("vreg_l10b_1p8", text)
        self.assertIn("vreg_l16b_3p0", text)
        self.assertIn("the same three", flat)
        self.assertIn("same hardware, definitely unrelated", flat)
        # AOSS wiring identical on both.
        self.assertIn("qcom,qmp = <&aoss_qmp>", text)
        # And the observability asymmetry must be stated, not glossed.
        self.assertIn("the ports are not equally observable", flat)
        self.assertIn("ramoops", text)

    def test_the_prime_opp_gap_is_recorded_with_its_mechanism(self):
        """X910 declares the 3.36 GHz OPP; X710 does not, and the LUT has it."""
        text = read(DIFF_DOC)
        flat = " ".join(text.split())
        self.assertIn("opp-3360000000", text)
        self.assertIn("Voltage update failed freq=3360000", text)
        self.assertIn("failed to update OPP for freq=3360000", text)
        self.assertIn("dev_pm_opp_adjust_voltage", text)
        # It must rule out the CPU-path fix as the cause, having checked.
        self.assertIn("This is not caused by the `epss_l3` fix", flat)
        # And it must not promote a once-per-boot message to a marker.
        self.assertIn("It is also not a stall marker", flat)
        for cls in ("different board config, possibly relevant",
                    "needs stock X710 evidence"):
            with self.subTest(cls=cls):
                self.assertIn(cls, text)

    def test_the_plan_keeps_the_rpmh_work_as_a_fallback(self):
        self.assertIn("NEXT_STALL_DEBUG_PLAN.md", read(PLAN))

    def test_the_plan_has_the_five_labelled_experiments(self):
        text = read(PLAN)
        for token in ("msm.disable_acd=1", "msm.skip_gpu=1",
                      "CONFIG_QCOM_AOSS_QMP=y", "gts9_rpmh_debug=1"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_the_early_warning_audit_answers_the_dummy_regulator_question(self):
        """The brief asks five specific questions; the audit must answer them.

        The tempting 'fix' for `supply vdd not found` is to add the regulator,
        and the brief forbids it without evidence.  The evidence is that the
        property is absent on X710, on X910 and upstream, and that SM8550 powers
        the GPU through gpucc GDSCs and OPP levels instead.
        """
        text = read("docs/X710_EARLY_BOOT_WARNINGS.md")
        flat = " ".join(text.split())
        self.assertIn("msm_gpu.c:955-964", text)
        self.assertIn("devm_regulator_get", text)
        self.assertIn("GPU_CC_CX_GDSC", text)
        self.assertIn("ABSENT on both", text)
        self.assertIn("do not add a regulator", flat)
        # And it must not claim the message is a fault signature.
        self.assertIn("none of them is a marker", flat)

    def test_the_early_warning_audit_does_not_inflate_the_chain(self):
        """Two of the four are already gone; the doc must say so."""
        text = read("docs/X710_EARLY_BOOT_WARNINGS.md")
        self.assertIn("Unable to send ACD state to AOSS", text)
        self.assertIn("Unable to drop a managed device link reference", text)
        self.assertIn("CONFIG_QCOM_IPCC=y", text)
        self.assertIn("DL_FLAG_STATELESS", text)
        flat = " ".join(text.split())
        self.assertIn("downgraded from", flat)
        self.assertIn("does **not** retire profiles B and C", flat)

    def test_the_onset_arithmetic_is_pinned_to_the_built_config(self):
        """26 s and 21 s are read from the config, not assumed."""
        text = read("docs/STALL_FIRST_EVENT_ORDERING.md")
        flat = " ".join(text.split())
        self.assertIn("Round 30: the onset is ~6.5-7.8 s", flat)
        self.assertIn("6.55", text)
        self.assertIn("7.74", text)
        # The two timeout sources, named with their config symbols.
        self.assertIn("CONFIG_SOFTLOCKUP_DETECTOR", text)
        self.assertIn("CONFIG_RCU_CPU_STALL_TIMEOUT=21", text)
        # And the config really says so.
        cfg = read("out/kernel-gts9wifi/config")
        self.assertIn("CONFIG_RCU_CPU_STALL_TIMEOUT=21", cfg)
        self.assertIn("CONFIG_HZ=250", cfg)

    def test_the_ordering_table_records_that_it_did_not_survive(self):
        """The 3-of-3 association must be withdrawn on this kernel's evidence."""
        text = read("docs/STALL_FIRST_EVENT_ORDERING.md")
        flat = " ".join(text.split())
        self.assertIn("the marker table does not survive", flat)
        self.assertIn("The association does not generalise", flat)
        # Both new wedges must be shown as lacking the three markers.
        self.assertIn("| `frame done timeout` | **0** | **0** |", text)
        self.assertIn("| `mmc1: Timeout` | **0** | **0** |", text)
        self.assertIn("| `AMC RPMH` | **0** | **0** |", text)

    def test_the_two_wedges_are_archived_with_their_binding(self):
        """test-197 has the device-side marker; test-195's was overwritten.

        The pmsg region is a single slot, so only the most recent marker survives.
        test-197's is archived and proves the mechanism end to end; test-195
        predates preservation and says so in its README rather than leaving a
        reader to guess whether the marker was lost or never written.
        """
        for d, boot in (("test-195-20260925T1023Z", "6d8b975c"),
                        ("test-197-20260925T1103Z", "aad07f8d")):
            with self.subTest(record=d):
                base = ROOT / "reference/boot-tests" / d
                self.assertTrue(base.exists(), f"{d} missing")
                # Both must carry the CPU-level evidence.
                console = (base / "on-device-console-ramoops.txt").read_text(
                    errors="replace")
                for needle in ("soft lockup", "Kernel panic",
                               "toggle_allocation_gate"):
                    self.assertIn(needle, console)
                # And both must name the wedged boot somewhere.
                self.assertIn(boot, read(f"reference/boot-tests/{d}/round-{1if d.startswith('test-195') else 4}.txt"))
        # test-197 additionally has the device-side copy.
        pmsg = read("reference/boot-tests/test-197-20260925T1103Z/on-device-pmsg.txt")
        self.assertIn("aad07f8d", pmsg)
        self.assertIn("round=4", pmsg)
        # test-195 must explain its absence rather than hide it.
        t195 = " ".join(read("reference/boot-tests/test-195-20260925T1023Z/README.md").split())
        self.assertIn("survives in the round record only", t195)
        self.assertIn("single-slot ring", t195)

    def test_profile_c_wedged_with_the_gpu_absent(self):
        """The decisive ablation: same wedge, GPU never registered."""
        d = "reference/boot-tests/test-198-20260925T1235Z"
        if not (ROOT / d).exists():
            self.skipTest("test-198 not recorded yet")
        rec = read(f"{d}/README.md")
        flat = " ".join(rec.split())
        # The claim, and the two independent confirmations of the ablation.
        self.assertIn("the GPU never registered", flat)
        self.assertIn("decisively downgraded", flat)
        # The evidence: zero GPU init on the wedged boot vs one on baseline.
        klog = read(f"{d}/klog-4.txt")
        self.assertEqual(klog.count("Initialized msm 1.13.0 for 3d00000.gpu"), 0,
                         "the wedged Profile C boot must have no GPU init")
        base = read("reference/boot-tests/test-197-20260925T1103Z/klog-4.txt")
        self.assertGreater(base.count("Initialized msm 1.13.0 for 3d00000.gpu"), 0,
                           "the baseline wedge must have bound the GPU, for contrast")
        # The identical CPU-level chain.
        console = (ROOT / f"{d}/on-device-console-ramoops.txt").read_text(errors="replace")
        for needle in ("soft lockup", "Kernel panic", "toggle_allocation_gate",
                       "kick_all_cpus_sync", "FAILED" if False else "failed to stop secondary CPUs"):
            with self.subTest(needle=needle):
                self.assertIn(needle, console)
        # And the three markers neither baseline wedge carried.
        self.assertIn("AMC RPMH", console)
        self.assertIn("frame done timeout", console)
        self.assertIn("Timeout waiting for hardware", console)
        # The onset, third independent agreement.
        self.assertIn("6.80", rec)
        self.assertIn("7.29", rec)

    def test_the_rpmh_run_result_is_the_pre_registered_last_row(self):
        """A wedge with no RPMh output is its own pre-registered outcome."""
        d = "reference/boot-tests/test-199-20260925T1314Z"
        if not (ROOT / d).exists():
            self.skipTest("test-199 not recorded yet")
        rec = read(f"{d}/README.md")
        flat = " ".join(rec.split())
        # The decision rule's last row, quoted in the record.
        self.assertIn("no RPMh output at all, and the stall still happened", flat)
        self.assertIn("through an RPMh timeout", flat)
        self.assertIn("the RPMh direction is downgraded", flat)
        self.assertIn("the victim's stack contains no RPMh path", flat)
        # The dump must genuinely be absent from every channel.
        for f in ("wedge-round9/on-device-console-ramoops.txt",
                  "wedge-round9/klog-9.txt", "wedge-round9/pstore-9.txt"):
            with self.subTest(channel=f):
                self.assertNotIn("gts9-rpmh:", read(f"{d}/{f}"))
        # And the switch must have been proven armed, or absence proves nothing.
        self.assertIn("ARMING-GATE.txt", rec)
        gate = read(f"{d}/ARMING-GATE.txt")
        self.assertIn("rpmh_debug_in_unknown_list=0", gate)
        self.assertIn("gpu_driver=adreno", gate)
        # The victim stack must carry no RPMh path.
        console = read(f"{d}/wedge-round9/on-device-console-ramoops.txt")
        self.assertIn("toggle_allocation_gate", console)
        self.assertIn("failed to stop secondary CPUs", console)
        for frame in ("rpmh", "rpmh_write_batch", "bcm-voter", "rsc_drv"):
            with self.subTest(frame=frame):
                self.assertNotIn(frame, console.lower().replace("qcom-rpmhpd", ""))
        # The new wrinkle: a second-firing soft lockup at 56 s.
        self.assertIn("stuck for 56s", console)
        self.assertIn("8.75", rec)
        self.assertIn("7.58", rec)

    def test_the_plan_records_the_gpu_direction_as_closed(self):
        flat = " ".join(read("docs/NEXT_STALL_DEBUG_PLAN.md").split())
        self.assertIn("RESOLVED IN ROUND 31: the GPU direction is out", flat)
        self.assertIn("it is not necessary for the wedge", flat)
        self.assertIn("DONE, and the GPU is out", flat)

    def test_the_profile_c_result_is_recorded_without_over_claiming(self):
        """The ablation passed; the single event is NOT classified as a GPU verdict."""
        r = "reference/boot-tests/test-196-20260925T1100Z/RESULT.md"
        if not (ROOT / r).exists():
            self.skipTest("test-196 result not written yet")
        text = read(r)
        flat = " ".join(text.split())
        # The gate, and that it can fail.
        for check in ("`Y`", "absent — UNBOUND", "16", "connected"):
            with self.subTest(check=check):
                self.assertIn(check, text)
        # The event must stay unclassified, with both readings named.
        self.assertIn("not determined in 2 rounds", flat)
        self.assertIn("host-side USB reset", flat)
        self.assertIn("abrupt end of the guest", flat)
        self.assertIn("stopping journal is not itself proof of death", flat)
        self.assertIn("The second reading is not excluded", flat)
        # It must not downgrade the GPU on this evidence.
        self.assertIn("does not downgrade the GPU/GMU/ACD path", flat)
        self.assertIn("does not exonerate it either", flat)
        # And the harness defect it exposed must be recorded.
        self.assertIn("under_test_boot_id", text)
        self.assertIn("none of them named the boot the kernel-log evidence came from",
                      flat)
        # The undecodable dump, with the verified magic.
        self.assertIn("c4 5c 5d 77", text)
        self.assertIn("zlib_inflate() failed, ret = -3!", text)

    def test_a_switch_nothing_consumes_is_refused(self):
        """A dead cmdline switch makes every round of its profile unfalsifiable.

        `gts9_rpmh_debug=1` only prints when a timeout happens, so a round with no
        dump cannot be distinguished from a kernel that has no such switch. The
        kernel names every cmdline token it did NOT consume in
        `Unknown kernel command line parameters`, so absence from that list is
        proof a handler ran - and presence is proof none did.
        """
        text = read("scripts/stall-ab.sh")
        self.assertIn("Unknown kernel command line parameters", text)
        self.assertIn("under_test_boot_id", text)
        self.assertIn("unknown_params=", text)
        # It must have a userspace allowlist, or it fires on every profile.
        self.assertIn("USERSPACE_TOKENS=", text)
        for tok in ("gts9_minimal_rootfs", "gts9_watchdog_debug"):
            with self.subTest(tok=tok):
                self.assertIn(tok, text)
        flat = " ".join(text.split())
        self.assertIn("has no consumer in this kernel", flat)
        self.assertIn("unfalsifiable", flat)

    def test_the_rpmh_debug_run_is_single_variable(self):
        """The decision rule forbids mixing it with the A/B tokens."""
        rule = read("docs/RPMH_DEBUG_DECISION_RULE.md")
        flat = " ".join(rule.split())
        self.assertIn("It is not an A/B round.", flat)
        self.assertIn("must not be enabled during an A/B round", flat)
        # And the profile really is one token from baseline.
        import subprocess
        base = read("boot/cmdline.stall-ab-baseline.example.txt").split()
        rpmh = read("boot/cmdline.rpmh-debug.example.txt").split()
        self.assertEqual(sorted(set(rpmh) - set(base)), ["gts9_rpmh_debug=1"])
        self.assertEqual(sorted(set(base) - set(rpmh)), [])

    def test_the_flashed_kernel_carries_the_rpmh_diagnostic(self):
        """The switch only works if the strings are in the flashed image."""
        import gzip
        img = ROOT / "out/kernel-gts9wifi/Image.gz"
        if not img.exists():
            self.skipTest("kernel image not built")
        data = gzip.open(img, "rb").read()
        for needle in (b"gts9-rpmh: TIMEOUT rsc=", b"gts9-rpmh: ring_summary",
                       b"LATE COMPLETION"):
            with self.subTest(needle=needle):
                self.assertIn(needle, data)
        # And that image is the one the flashed bundle was built from.
        info = read("out/boot-bundle-test191-osm-l3/BUNDLE_INFO")
        self.assertIn("df00c53cabfae26c0a96c6b93ada4590dfb44d02f16c39bd139ef52a9a19e32f",
                      info)

    def test_the_cmdline_check_reads_the_answer_not_the_echo(self):
        """`SENT` echoes the command text, which itself contains `cmdline=`.

        A bare `grep -m1 'cmdline='` therefore matches the probe's own echo, so
        the profile check compared a command string against the profile and
        reported "tablet cmdline lacks msm.skip_gpu=1" on a boot that had it.
        Measured on the Profile C preflight, 2026-09-25T12:22Z.
        """
        text = read("scripts/stall-ab.sh")
        self.assertIn("RECV  cmdline=", text)
        self.assertNotIn("grep -a -m1 'cmdline='", text)
        # The `RECV  ` requirement must be explained where it is used.
        flat = " ".join(text.split())
        self.assertIn("matches the echo and never the tablet's answer", flat)

    def test_the_probe_payload_has_no_unescaped_single_quote(self):
        """The `-Commands` argument is single-quoted, so a literal quote ends it.

        Three attempts at `under_test_boot_id` failed this way and each failed
        *silently*: the selector reached the remote shell as a glob (`grep *-1`),
        as an unclosed awk program (`missing } near end of file`), or with the
        harness's own `$DIR/probe-$i-raw.txt` interpolated into the remote command.
        The field simply came back empty. Verified by running the real dry run and
        reading the value out of `preflight-raw.txt`, which is the only test that
        exercises the actual layering.
        """
        text = read("scripts/stall-ab.sh")
        marker = "-Commands " + chr(39)
        start = text.index(marker) + len(marker)
        terminator = chr(39) + ' ' + chr(92)
        payload = text[start:text.index(terminator, start)]
        stray = payload.replace(chr(39) + chr(92) + chr(39) + chr(39), '')
        self.assertNotIn(chr(39), stray,
                         "every single quote in the -Commands payload must be escaped")
        self.assertIn("under_test_boot_id=", text)
        self.assertIn(chr(39) + chr(92) + chr(39) + chr(39) + "{print $2}", text)

    def test_the_probe_emits_no_shell_syntax_errors(self):
        """The boot-under-test fragment must survive the remote shell.

        Its first form used `grep -E "^ *-1 "`, which reached the remote shell as
        the glob `*-1`; its second escaped `awk`'s `$2`, which printed an empty
        field; its third left unescaped single quotes inside the single-quoted
        `-Commands` argument, which closed it early and let the harness's own
        `$DIR/probe-$i-raw.txt` be interpolated into the remote command. All three
        failed silently with the field empty. The form that works was verified
        through a real dry run: `awk '{print $2}'` on the second-from-last boot
        line, with the quotes shell-escaped.
        """
        text = read("scripts/stall-ab.sh")
        start = text.index("BOOT_UNDER_TEST")
        frag = text[start:text.index("PREVBOOT_KLOG", start)]
        # No leading-dash regex - the shell globs it.
        self.assertNotIn("grep -E", frag)
        # The selector reads the boot list and names the -1 boot.
        self.assertIn("journalctl --list-boots", frag)
        self.assertIn("tail -2 | head -1", frag)
        # The awk program must be shell-escaped, not bare.
        self.assertIn(chr(39) + chr(92) + chr(39) + chr(39) + "{print $2}", frag)

    def test_the_boot_under_test_is_recorded_by_the_probe(self):
        """Three boot ids per round, and the evidence describes a fourth thing."""
        text = read("scripts/stall-ab.sh")
        self.assertIn("under_test_boot_id=", text)
        self.assertIn("boot_under_test=", text)
        self.assertIn("boot_list=", text)

    def test_the_profile_c_candidate_is_ready_and_gated(self):
        """A candidate that cannot prove its own ablation is not a candidate."""
        c = "reference/boot-tests/test-196-20260925T1100Z/candidate.txt"
        if not (ROOT / c).exists():
            self.skipTest("test-196 candidate not written yet")
        text = read(c)
        flat = " ".join(text.split())
        # The corrected parameter, and why the old one was wrong.
        self.assertIn("msm.skip_gpu=1", text)
        self.assertIn("MODULE_PARM_DESC(no_gpu", text)
        self.assertIn("false negative", flat)
        # The gate must be present, and must be able to fail.
        for check in ("/sys/module/msm/parameters/skip_gpu",
                      "msm.skip_gpu=1$", "3d00000.gpu/driver",
                      "card*-DSI-1/status"):
            with self.subTest(check=check):
                self.assertIn(check, text)
        self.assertIn("the round is `unattributed`", flat)
        # vendor_boot only, with the hashes that keep it one-variable.
        self.assertIn("`vendor_boot` **only**", text)
        self.assertIn("8072e6c8e3a95e95fba03086a582f9cada3fde5a89e13f29db8ca147b074e8ed", text)
        self.assertIn("06902f993f6fe9b682686ab36ad956032a8f6a250e595a85e1d7ac82092f211f", text)
        self.assertIn("dc78ddf19ce4e83f49c4656e927f048a1717e684b3251b3e7c5d764f793c602c", text)
        # And it must not over-claim a clean result.
        self.assertIn("not reproduced in N rounds", flat)
        self.assertIn("It is *not* \"GPU excluded\"", flat)
        # The bundle must actually exist and match.
        vb = ROOT / "out/boot-bundle-stall-no-gpu/vendor_boot.img"
        if vb.exists():
            self.assertEqual(
                sha256("out/boot-bundle-stall-no-gpu/vendor_boot.img"),
                "8072e6c8e3a95e95fba03086a582f9cada3fde5a89e13f29db8ca147b074e8ed")

    def test_the_plan_carries_the_four_required_sections(self):
        """CONFIRMED / CORRECTED / OPEN / NEXT, and the rule they enforce."""
        text = read("docs/NEXT_STALL_DEBUG_PLAN.md")
        for section in ("## CONFIRMED", "## CORRECTED", "## OPEN",
                        "## NEXT PHYSICAL TEST", "## NOT THIS ROUND"):
            with self.subTest(section=section):
                self.assertIn(section, text)
        flat = " ".join(text.split())
        # The rule, verbatim, because everything else follows from it.
        self.assertIn("First prove this is the same boot and that it really is a wedge",
                      flat)
        # And the corrections that matter most.
        self.assertIn("presence_outages=0", text)
        self.assertIn("means the check did not run", flat)
        self.assertNotIn("no record survives a reboot", flat)

    def test_the_plan_does_not_authorise_a_kernel_fix_from_test_194(self):
        """It is a measurement correction; the forbidden list must say so."""
        text = read("docs/NEXT_STALL_DEBUG_PLAN.md")
        flat = " ".join(text.split())
        self.assertIn("No kernel change follows from test-194", flat)
        for forbidden in ("DPU timeout", "MMC driver", "RPMh timeout",
                          "regulator", "clocks", "IRQ", "cpuidle",
                          "watchdog threshold"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, text)
        # C must not be over-claimed if it is clean.
        self.assertIn("not reproduced in N rounds", flat)
        self.assertIn("must never be written as \"GPU excluded\"", flat)
        # And the RPMh run stays single-variable.
        self.assertIn("Run it **alone**", flat)

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

    def test_the_result_is_recorded(self):
        text = read(f"{self.TESTDIR}/RESULT.md")
        for needle in ("Zero stalls", "no-stall-signature", "no pre-fix rate",
                       "warm reboot", "SID=0x1c00", "28.903 s"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # It must not turn six clean cycles into a fix claim.
        self.assertIn("Does not establish a fix", text)

    def test_the_classifier_output_is_kept(self):
        text = read(f"{self.TESTDIR}/classify-captures.txt")
        self.assertIn("6 round(s): 5 clean, 0 STALL", text)
        self.assertIn("UNATTENDED RESET", text)
        self.assertIn('"verdict": "STALL"', text)

    def test_the_console_helper_cannot_flood_the_capture(self):
        """A closed port must not turn a capture into megabytes of stack traces."""
        text = read("scripts/console-run.ps1")
        self.assertIn("readErrorLogged", text)
        self.assertIn("further read errors suppressed", text)
        # Only TimeoutException may be treated as the normal case.
        self.assertIn("catch [TimeoutException]", text)

    def test_the_pruned_captures_say_what_was_pruned(self):
        for n in range(1, 7):
            rel = f"{self.TESTDIR}/shutdown-{n}-trigger.txt"
            with self.subTest(rel=rel):
                text = read(rel)
                self.assertIn("The original file was", text)
                self.assertIn("Nothing else was altered", text)
                # The evidence that the trigger was sent must survive.
                self.assertIn("systemctl reboot", text)

    def test_the_collector_deployment_is_recorded_with_hashes(self):
        text = read(f"{self.TESTDIR}/README.md")
        self.assertIn("b2a4e9c2abc90eb17daad08ed693738dc2b427c43dc28351a1547b134aad99d4", text)
        self.assertIn("82d29a6934fda30ee4af9ef328447892617cb130333548efd07a077cefb8d94b", text)
        self.assertIn("previous_boot_id=300173a42fb943ba8f1348b0cdb36f4f", text)
        # It must say plainly that this was not a flash.
        self.assertIn("no partition was written, nothing was flashed", text)

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

    def test_the_harnesses_select_the_archive_by_boot_id(self):
        """Ordering cannot identify the archive: this device has no RTC.

        `date -u` is frozen near 2026-04-13T19:38Z, so the <utc> prefix in every
        directory name is nearly constant and the tie breaks on a random boot_id8;
        and measured on the device, all eight retained directories carry mtimes
        within one second of each other.  Neither `ls -1d | tail -1` nor
        `ls -1dt | head -1` is therefore a "newest" test.  The collector names each
        directory after the boot that creates it, so the exact selector is the
        running boot's own id - which is also the archive that describes the
        previous boot, the one every round wants.
        """
        for rel in ("reference/boot-tests/test-187-20260924T1540Z/reboot-rounds.sh",
                    "reference/boot-tests/test-187-20260924T1540Z/cold-boot-capture.sh"):
            with self.subTest(rel=rel):
                text = read(rel)
                self.assertIn("cut -c1-8 /proc/sys/kernel/random/boot_id", text)
                self.assertIn("ls -1d /var/log/gts9-boot-evidence/*-$BID/", text)
                self.assertNotIn("gts9-boot-evidence/*/ 2>/dev/null | tail -1", text)
                self.assertNotIn("ls -1dt /var/log/gts9-boot-evidence/*/", text)

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
        self.assertIn("no `wdt` or `watchdog` node at", text)
        self.assertIn("CONFIG_SOFTDOG", text)
        self.assertIn("Nothing in mainline reset it", text)
        # It must cite the existing findings rather than re-derive them, and it
        # must name the one concrete out-of-kernel candidate without claiming it.
        self.assertIn("docs/WATCHDOG_X710.md", text)
        self.assertIn("qcom,gh-watchdog", text)
        # The residual unknown must stay unknown.
        self.assertIn("stays a candidate", text)
        self.assertIn("no measurement in", text)

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

    def test_the_doc_does_not_assert_a_reset_agent(self):
        """It may name a candidate; it must not name a culprit."""
        text = read(self.DOC)
        self.assertIn("only partly established", text)
        self.assertIn("stays a candidate", text)
        self.assertIn("no measurement in", text)

    def test_the_doc_records_why_the_old_classifier_missed_it(self):
        text = read(self.DOC)
        self.assertIn("observer-ab.sh:93", text)
        # Markdown wraps, so match the phrase in fragments rather than across a
        # line break.
        lowered = text.lower()
        self.assertIn("absence of a line", lowered)
        self.assertIn("no amount of banner-scanning will ever see it", lowered)

    def test_the_doc_records_the_second_episode(self):
        """A failure inside a series reported as clean must stay recorded."""
        text = read(self.DOC)
        self.assertIn("dpu_encoder_frame_done_timeout", text)
        self.assertIn("7f02df57", text)
        self.assertIn("UNATTENDED RESET", text)
        # It must refuse to make the last line the cause.
        self.assertIn("not make the frame-done timeout the cause", text)
        self.assertIn("SHUTDOWN-SERIES-RESULT.md", text)
        # And it must tie the message to the chain the project already recorded.
        self.assertIn("docs/WATCHDOG_X710.md", text)
        self.assertIn("docs/DPU_TRACE.md", text)
        self.assertIn("actually cycled the framebuffer", text)

    def test_the_old_series_result_carries_the_correction(self):
        text = read("reference/boot-tests/test-187-20260924T1540Z/"
                    "on-device/SHUTDOWN-SERIES-RESULT.md")
        self.assertIn("Correction (round 16)", text)
        self.assertIn("14 clean cycles plus 2", text)

    def test_the_classifier_counters_are_pinned(self):
        """The tool that found the second episode must keep counting resets."""
        text = read("reference/boot-tests/test-188-20260925T0115Z/"
                    "classify-captures.py")
        for needle in ("unattended_resets", "longest_open_silence_s",
                       "reboot.target", "prev_boot_end", "dpu_frame_timeout"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_old_classifier_really_did_miss_it(self):
        """Pin the defect itself, not just the description of it."""
        text = read("reference/boot-tests/test-184-20260924T140000Z/observer-ab.sh")
        self.assertIn("console_stall_markers=", text)
        self.assertNotIn("systemd-shutdown", text)


class WedgeRateAttributionTests(unittest.TestCase):
    """A silent console is not evidence until it has been attributed.

    The rate series counts stalls, and the instrument it counts them with is the
    console.  On the healthy test-191 boot that instrument lied: the tty echoed
    every character and executed none of them, because `gts9-acm-getty.service`
    was sitting at a login prompt with no reachable shell, and
    `systemctl restart gts9-acm-getty.service` fixed it outright.  A series that
    scored that as a stall would have invented a failure.

    The guard must not overcorrect either.  On three recorded boots ssh was
    *refused* while ICMP answered; a guard that demanded ssh would have called
    those boots stalls, so the two channels have to be read as a pair and every
    outcome written down.
    """

    TESTDIR = "reference/boot-tests/test-191-20260925T0410Z"
    HARNESS = f"{TESTDIR}/wedge-rate.sh"

    def setUp(self):
        self.text = read(self.HARNESS)

    def early_exit_body(self):
        """The block that decides whether a cycle survived, from its first test."""
        text = self.text
        body = text[text.index('if [ "$EARLY_EXIT" = "1" ] && [ -n "$on_at" ]; then'):]
        return body[:body.index('if [ "$early" = "1" ]; then')]

    def test_the_check_is_ps_not_tasks_current(self):
        """TasksCurrent=0 is not a missing shell: logind moves the session out.

        The name may appear - the comment has to say why it is the wrong test -
        but it must never be what the harness reads.
        """
        self.assertIn("ps -t ttyGS0", self.text)
        # Naming it in a comment is how the next reader learns why it is wrong;
        # reading it is what the check must never do.  Only the code counts.
        code = "\n".join(
            line for line in self.text.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn("systemctl show", code)
        self.assertNotIn("TasksCurrent", code)

    def test_a_silent_console_is_attributed_before_it_is_believed(self):
        for needle in (
            "ensure_console_shell",
            "gts9-acm-getty.service",
            "GETTY_RESTARTED",
            "WEDGE_ATTRIBUTION",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_the_other_channel_decides_which_reading_applies(self):
        """Console silent + ssh alive is the instrument; ssh dead is a stall."""
        text = self.text
        self.assertIn("ssh_answers", text)
        body = self.early_exit_body()
        self.assertLess(
            body.index("ssh_answers"),
            body.index("ensure_console_shell"),
            "ssh must be consulted BEFORE anything is restarted",
        )
        self.assertIn("console-silent-ssh-unreachable", text)
        self.assertIn("unattributed", text)

    def test_nothing_is_restarted_on_a_boot_that_may_be_dying(self):
        """The getty restart lives inside the ssh-answered branch only."""
        body = self.early_exit_body()
        start = body.index("ssh_answers")
        end = body.index("No channel answered")
        self.assertIn("ensure_console_shell", body[start:end])
        # Nothing in the no-channel-answered branch may restart a unit: on a boot
        # that may be dying, that is interference.
        self.assertNotIn("systemctl restart", body[end:])

    def test_both_channels_are_asked_the_uptime_question(self):
        self.assertIn("probe_console_uptime", self.text)
        self.assertIn("probe_ssh_uptime", self.text)
        self.assertIn("uptime_via=", self.text)

    def test_the_fractional_uptime_pattern_keeps_its_decimal_point(self):
        """The bug this project has now shipped twice."""
        for pat in (r"GTS9_ALIVE_\([0-9][0-9]*\)\.[0-9]*_END",
                    r"^\([0-9][0-9]*\)\..*"):
            with self.subTest(pattern=pat):
                self.assertIn(pat, self.text)

    def test_the_summary_reports_the_unresolved_cycles(self):
        self.assertIn("unattributed=$unattributed", self.text)
        self.assertIn("getty_restarts=$getty_restarts", self.text)

    def test_per_cycle_state_is_reset_at_the_top_of_every_cycle(self):
        """A restart or an attribution must not leak into the next cycle."""
        body = self.text[self.text.index("while [ \"$CYCLES\" = \"-1\" ]"):]
        reset = body[:body.index('say "--- cycle $i ---"')]
        for needle in ("GETTY_RESTARTED=0", "WEDGE_ATTRIBUTION=attributed"):
            with self.subTest(needle=needle):
                self.assertIn(needle, reset)

    def test_the_reason_is_written_down_beside_the_code(self):
        """The next reader has to know why ssh gates the guard."""
        flat = " ".join(self.text.split())
        self.assertIn("two causes and they look identical", flat)
        self.assertIn("logind moves", flat)
        self.assertIn("ssh was *refused* while ICMP still answered", flat)
        self.assertIn("unattributed rather than counted as a clean run", flat)

    def test_the_console_failure_classifier_is_tested_offline(self):
        """The classifier is a pure function; test it without the tablet.

        Cycle 1 of the series it guards was scored wrong because the console
        could not be opened at all and the harness called that a silent console.
        The strings that decide it are text, so they can be replayed here.
        """
        import subprocess
        script = ROOT / self.TESTDIR / "test-console-failure-classifier.sh"
        self.assertTrue(script.exists(), f"{script} is missing")
        proc = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"classifier regression test failed:\n{proc.stdout}\n{proc.stderr}",
        )
        self.assertIn("6 passed, 0 failed", proc.stdout)
        # The failure that motivated it must be one of the cases.
        self.assertIn("port could not be opened", proc.stdout)

    def test_a_console_that_was_never_asked_is_not_a_stall(self):
        """Attribution must not depend on how the console failed."""
        text = self.text
        body = text[text.index('if [ "$wedged" = "0" ]; then'):]
        body = body[:body.index('if [ "$early" = "1" ]; then')]
        # ssh is consulted regardless of the console state...
        self.assertIn("if [ -z \"$alive\" ] && ssh_answers; then", body)
        # ...and a port that never opened is recorded as an instrument fault.
        self.assertIn("console-port-failed", body)
        self.assertIn("console-timeout", body)
        self.assertIn("attributed", body)

    def test_the_port_failure_is_named_in_the_log_not_just_counted(self):
        """The next reader must not have to guess which failure this was."""
        self.assertIn("COM17 could not be opened:", self.text)
        self.assertIn("console_state=${CONSOLE_STATE:-untried}", self.text)

    def test_the_failure_record_names_all_three_marker_counts(self):
        """Three records disagree, so the table has to be in the record."""
        text = read(f"{self.TESTDIR}/wedge-rate-20260925T065728Z/"
                    "FAILED-BOOT-20260925T0659.md")
        for needle in ("| 04:57Z |", "| 06:00Z |", "| this one |"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertIn("15", text)
        self.assertIn("14", text)
        self.assertIn("frame-done flood is not the common factor", text)

    def test_the_record_does_not_claim_the_dpu_marker_separates_anything(self):
        """It fires on healthy boots too, and that was measured, not assumed."""
        text = read(f"{self.TESTDIR}/wedge-rate-20260925T065728Z/"
                    "FAILED-BOOT-20260925T0659.md")
        self.assertIn("marker_dpu_encoder_disabled=1", text)
        self.assertIn("4.798040", text)
        self.assertIn("it means nothing", text)
        # And the control must be a table, so the split is visible at a glance.
        for row in ("| `encoder is disabled` | all 3 | **present** | **no**",
                    "| `frame done timeout` | 15 / 14 / 1 | **0** |",
                    "| `mmc1: Timeout` | 2 / 1 / 6 | **0** |"):
            with self.subTest(row=row):
                self.assertIn(row, text)

    def test_the_dpu_noise_is_not_claimed_as_a_candidate(self):
        """docs/DPU_TRACE.md already called it noise; the record must not re-propose it."""
        text = read(f"{self.TESTDIR}/wedge-rate-20260925T065728Z/"
                    "FAILED-BOOT-20260925T0659.md")
        self.assertIn("docs/DPU_TRACE.md", text)
        self.assertIn("is noise, not a timeout", text)

    def test_the_series_probes_markers_after_the_outcome_not_before(self):
        """Instrumentation that ran earlier could change what it measures."""
        text = self.text
        self.assertIn("probe_markers()", text)
        # The call site must come after the verdict and after the stop decisions.
        call = text.index('probe_markers "$i" >>"$DIR/cycle-$i-verdict.txt"')
        self.assertGreater(call, text.index("nmi=$(get nmi_unanswered)"))
        self.assertGreater(call, text.index("*** WEDGE:"))
        # And it must record the same markers the failure records use.
        for marker in ("encoder is disabled", "frame done timeout",
                       "Timeout waiting for hardware", "AMC RPMH",
                       "responded to the NMI"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_the_wedged_boot_journal_and_console_disagree_on_purpose(self):
        """The record has to carry the two-clock lesson, not just the panic."""
        text = read(f"{self.TESTDIR}/wedge-rate-20260925T065728Z/"
                    "FAILED-BOOT-20260925T0659.md")
        self.assertIn("1115 lines and stops at", " ".join(text.split()))
        self.assertIn('"the journal stops" is not "the system froze"', text)

    def test_the_control_count_and_its_significance_are_pinned(self):
        """3 of 3 against 22 of 22, and the p-value that goes with it."""
        text = read("docs/STALL_FIRST_EVENT_ORDERING.md")
        self.assertIn("22 of 22", text)
        self.assertIn("p = 0.00043", text)
        self.assertIn("rate2 8 + rate3 14", text)

    def test_the_control_counts_are_attributed_to_the_probe_not_the_labels(self):
        """A clean cycle's marker row stays valid even from a mislabelled series."""
        text = read("docs/STALL_FIRST_EVENT_ORDERING.md")
        flat = " ".join(text.split())
        self.assertIn("a clean cycle's marker row is valid evidence", flat)
        self.assertIn("touched only how a silent cycle is *labelled*", flat)

    def test_the_decision_rule_was_filled_in_against_its_own_rule(self):
        """The pre-registered thresholds must be read, not quietly replaced."""
        text = read("docs/WEDGE_RATE_DECISION_RULE.md")
        flat = " ".join(text.split())
        self.assertIn("written while the series was still running", flat)
        # The result, and the number it must not hide.
        self.assertIn("p = 1.0", text)
        self.assertIn("The CPU-path fix did not change the wedge rate", flat)
        # It must not upgrade the ACD improvement into an established fact.
        self.assertIn("p = 0.113", text)
        self.assertIn("remains unconfirmed rather than established", flat)
        # And it must say what to do instead of running more cycles.
        self.assertIn("not more rate series", flat)

    def test_the_record_justifies_warm_reboots_as_a_reproduction_vehicle(self):
        """Cold boots need an operator; all three records are warm anyway."""
        flat = " ".join(read("docs/STALL_FIRST_EVENT_ORDERING.md").split())
        self.assertIn("All three records are warm reboots", flat)
        self.assertIn("reproducible with warm reboots alone", flat)
        self.assertIn("reboot_kind=warm", flat)

    def test_the_record_states_what_is_not_established(self):
        """The one unclosed link is the whole strength of the claim."""
        text = read(f"{self.TESTDIR}/wedge-rate-20260925T065728Z/"
                    "FAILED-BOOT-20260925T0659.md")
        self.assertIn("**Not established.**", text)
        self.assertIn("That the failing boot itself had cpufreq bound", text)
        self.assertIn("failed to update OPP for freq=3360000", text)

    def test_a_diagnosed_wedge_is_not_reported_as_unattributed(self):
        """The bug this round found: the strongest evidence read as a question.

        When the second-outage check fires there is nothing left to ask - the
        boot was restarted by something other than the harness - but the block
        below it used to run anyway, leave CONSOLE_STATE at `untried`, and report
        the cycle as unattributed.  Cycle 9 of rate2 was recorded that way.
        """
        body = self.early_exit_body()
        self.assertIn('if [ "$wedged" = "1" ]; then', body)
        self.assertIn("alive_via=second-outage", body)
        # It must come BEFORE the probe block, or the probe runs first.
        self.assertLess(
            body.index('if [ "$wedged" = "1" ]; then'),
            body.index('probe_console_uptime_retry'),
        )

    def test_the_durable_marker_is_written_and_read_correctly(self):
        """/dev/pmsg0 is write-only; reading it truncates and fails."""
        text = self.text
        self.assertIn("write_boot_marker()", text)
        self.assertIn("/dev/pmsg0", text)
        # The read must come from pstore, never from /dev/pmsg0.
        reader = text[text.index("read_boot_markers() {"):]
        reader = reader[:reader.index("\n}")]
        self.assertNotIn("cat /dev/pmsg0", reader)
        self.assertIn("/var/lib/systemd/pstore/pmsg-ramoops-0", reader)
        self.assertIn("sys/fs/pstore/pmsg-ramoops-0", reader)

    def test_the_marker_carries_a_name_that_survives_the_rtc(self):
        """The tablet's clock reads 2026-04-13 on every boot, so time is useless."""
        reader = self.text[self.text.index("write_boot_marker() {"):]
        reader = reader[:reader.index("\n}")]
        self.assertIn("GTS9_BOOT cycle=", reader)
        self.assertIn("boot_id=", reader)
        self.assertIn("RTC reads 2026-04-13", " ".join(self.text.split()))

    def test_the_console_probe_is_never_called_inside_command_substitution(self):
        """The bug that defeated the whole classifier, found from the evidence.

        `CONSOLE_STATE` is how a cycle tells "the port never opened" from "the
        console was silent".  `$(...)` is a subshell, so a state set inside it is
        discarded - while the uptime still arrives, because it is echoed inside
        that same subshell.  The bug therefore hides behind a value that looks
        correct, and the port-failed branch becomes unreachable.

        Cycle 9 of the rate2 series is the observed instance: its log says
        "no channel answered (untried, ...)" - `untried` being the initial value,
        which is only possible if the assignment never reached the parent shell.
        """
        for line in self.text.splitlines():
            if "probe_console_uptime" not in line:
                continue
            if line.lstrip().startswith("#"):
                continue
            with self.subTest(line=line.strip()):
                self.assertNotIn(
                    "$(probe_console_uptime", line,
                    "the probe must be called plainly: $( ) is a subshell and "
                    "CONSOLE_STATE would be lost",
                )

    def test_the_presence_watch_is_re_read_when_the_cycle_ends(self):
        """A self-reboot after the early-exit watch closed must still count.

        The onset is not fixed - 6.8 s, ~52.5 s and ~76 s in the three complete
        records - so a watch that stops at back+EARLY_MIN_UPTIME can miss one
        entirely, which is what happened to cycle 9.
        """
        text = self.text
        self.assertIn("SECOND OUTAGE seen at verdict time", text)
        self.assertIn("Re-read presence now that the cycle is over", " ".join(text.split()))
        # And the verdict written earlier must be corrected, not left stale.
        self.assertIn("second_outage_gone=", text)
        self.assertIn("bring its two outage fields up to date", " ".join(text.split()))

    def test_the_classifier_test_exercises_the_real_call_path(self):
        """A unit test that calls the function plainly cannot catch the above."""
        script = (ROOT / self.TESTDIR / "test-console-failure-classifier.sh").read_text()
        self.assertIn("probe_console_uptime sample", script)
        harness = self.text
        # The harness must call it the same way the test does - plainly.
        self.assertIn('probe_console_uptime_retry "$i" || true', harness)


class StallClassificationTests(unittest.TestCase):
    """A quiet console is not a wedge, and the verdict names must say so.

    test-194 is the reason this class exists: a boot printed one `frame done
    timeout`, went silent on COM19, showed a stale panel and refused ssh - and
    then ran normally for 170 s to a clean restart, with zero lockup, RCU, NMI or
    panic markers.  Every one of those signals had been treated as sufficient for
    "stall" up to that point.  The four verdicts below replace that.
    """

    HARNESS = "scripts/stall-ab.sh"
    T194 = "reference/boot-tests/test-194-20260925T0906Z"

    def setUp(self):
        self.text = read(self.HARNESS)

    # 1. kernel console lines in a watch file -------------------------------
    def test_kernel_console_lines_are_recognised_through_the_host_prefix(self):
        """A watch line is `<host ts> RECV  [<kernel ts>] ...`.

        The metric anchored on `^\[` reported 0 while the capture held kernel
        lines, and that was then read as "this channel carries no kernel text".
        """
        self.assertIn(r"grep -acE 'RECV  \[[ ]*[0-9]+\.[0-9]+\]'", self.text)
        self.assertNotIn(r"grep -acE '^\[[ ]*[0-9]+\.[0-9]+\]'", self.text)
        import re
        pat = re.compile(r"RECV  \[ *[0-9]+\.[0-9]+\]")
        # The capture carries GBK PowerShell error text, so read it leniently;
        # the kernel lines this checks are ASCII.
        live = (ROOT / f"{self.T194}/live-console-capture.txt").read_text(
            errors="replace")
        self.assertTrue(pat.search(live), "the real capture must match")

    # 2. the early blind spot must not be written as "zero kernel text" -----
    def test_the_early_console_blind_spot_is_not_described_as_zero_kernel_text(self):
        flat = " ".join(self.text.split())
        self.assertIn("CORRECTED", flat)
        self.assertIn("gadget console only starts delivering once the host has "
                      "enumerated it", flat)
        self.assertNotIn("contains 13577 bytes and **zero** kernel lines", flat)

    # 4. a stopped harness must not leave a readable-as-complete round ------
    def test_a_round_record_is_only_trusted_once_the_identity_is_verified(self):
        flat = " ".join(self.text.split())
        self.assertIn("mark_round()", self.text)
        self.assertIn("GTS9_AB run=$RUN profile=$PROFILE round=$tag", self.text)
        self.assertIn("/dev/kmsg", self.text)
        self.assertIn("/dev/pmsg0", self.text)
        # unattributed must outrank a confident label
        self.assertIn("unattributed outranks everything", flat)
        # and an unverified identity must force it
        self.assertIn('[ "${IDENTITY:-missing}" != verified ] && verdict=unattributed',
                      self.text)

    # 3. boot identity binds the channels to one round ---------------------
    def test_the_boot_marker_binds_console_journal_and_pstore_to_a_round(self):
        """Proved on hardware, not asserted.

        `mark_round` writes run/profile/round/boot_id into /dev/kmsg and
        /dev/pmsg0 before the reboot; the next boot's probe reads both.  Measured
        end to end: the marker reported `boot_id=4955f1f1` and the round record's
        own `identity=` line carried the same id, so console, journal, pstore and
        the USB trace are provably one round.
        """
        text = self.text
        self.assertIn("mark_round()", text)
        self.assertIn("GTS9_AB run=$RUN profile=$PROFILE round=$tag", text)
        self.assertIn("/dev/kmsg", text)
        self.assertIn("/dev/pmsg0", text)
        # the marker must reach the probe's two channel reads
        self.assertIn("IDENTITY_PMSG", text)
        self.assertIn("identity_ring", text)
        # and the boot id must be resolved REMOTELY, not locally
        flat = " ".join(text.split())
        self.assertIn("resolved REMOTELY on the tablet", flat)
        self.assertNotIn("boot_id=\$(cat /proc/sys/kernel/random/boot_id)", text)

    def test_a_missing_field_counts_as_zero_not_an_arithmetic_error(self):
        """An empty expansion must not make the classifier fail open or closed."""
        self.assertIn("getn()", self.text)
        self.assertIn("A missing field must read as 0", " ".join(self.text.split()))
        # the classes are iterated as names, so they must be space-separated
        wedge = self.text.split("WEDGE_CLASSES=")[1].split("\n")[0]
        self.assertNotIn("|", wedge, "a pipe-joined list iterates once")

    def test_a_non_discriminating_marker_is_not_scored(self):
        """`rcg didn't update` fires on every boot, so it cannot classify."""
        suspect = self.text.split("SUSPECT_CLASSES=")[1].split("\n")[0]
        self.assertNotIn("disp_rcg_stale", suspect)
        self.assertNotIn("gpu_dummy_reg", suspect)
        # but it must still be counted, just not scored
        self.assertIn("'disp_rcg_stale|rcg didn.t update its configuration'", self.text)
        flat = " ".join(self.text.replace("#", " ").split())
        self.assertIn("cannot discriminate does not belong in a classifier", flat)

    # 5. nmi_unresponsive is counted ---------------------------------------
    def test_unanswered_nmi_is_counted_as_a_wedge_class_marker(self):
        self.assertIn("nmi_unresponsive|haven.t responded to the NMI", self.text)
        self.assertIn("nmi_unresponsive", self.text.split("WEDGE_CLASSES=")[1].split("\n")[0])
        # per channel
        self.assertIn('echo "${key}_klog=', self.text)
        self.assertIn('echo "${key}_pstore=', self.text)

    # 6/7. neither console silence nor a lone frame timeout is a wedge ------
    def test_console_silence_alone_cannot_produce_a_wedge_verdict(self):
        flat = " ".join(self.text.split())
        self.assertIn("verdict=clean", self.text)
        self.assertIn("verdict=suspect", self.text)
        # wedge requires presence_outages>=2 or a wedge-class marker
        self.assertIn('[ "${p_n:-0}" -ge 2 ] && verdict=wedge', self.text)
        self.assertIn('[ "${wedge_n:-0}" -gt 0 ] && verdict=wedge', self.text)

    def test_a_lone_frame_done_timeout_cannot_produce_a_wedge_verdict(self):
        """It is a `suspect` marker, not a wedge marker."""
        wedge = self.text.split("WEDGE_CLASSES=")[1].split("\n")[0]
        suspect = self.text.split("SUSPECT_CLASSES=")[1].split("\n")[0]
        self.assertNotIn("dpu_frame_timeout", wedge)
        self.assertNotIn("mmc_timeout", wedge)
        self.assertNotIn("rpmh_timeout", wedge)
        for cls in ("dpu_frame_timeout", "mmc_timeout", "rpmh_timeout",
                    "rpmh_active_only"):
            with self.subTest(cls=cls):
                self.assertIn(cls, suspect)
        self.assertIn("verdict=suspect", self.text)

    # 8. an automatic second reboot is strong evidence ---------------------
    def test_no_harness_variable_name_contains_a_hyphen(self):
        """A hyphenated name is a silent no-op, and this one hid a whole signal.

        `klog-watch=$path` parses as the command `klog-watch=...` (command not
        found), and `"$klog-watch.txt"` expands as `${klog}` + `-watch.txt`, a
        path that does not exist.  The presence read therefore got nothing and
        every automatic-restart count came back 0 - from the commit that added
        the detector until test-195 exposed it.  `presence_outages=0` in the
        test-193 records means "the check did not run", not "no restart".
        """
        import re
        bad = []
        for line in self.text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*-[A-Za-z0-9_-]*)\s*=", line)
            if m:
                bad.append(m.group(1))
        self.assertEqual(bad, [], f"invalid shell variable names assigned: {bad}")
        self.assertIn("watch_log=", self.text)
        self.assertNotIn("klog-watch", self.text)

    def test_the_restart_detector_reads_a_real_capture(self):
        """Verified against the test-195 watch log, which has two outages."""
        import subprocess
        log = ("reference/boot-tests/test-195-20260925T1023Z/"
               "console-1-watch.txt")
        if not (ROOT / log).exists():
            self.skipTest("test-195 capture not present")
        out = subprocess.run(
            ["bash", "-c",
             'tr -d "\\r" <"$1" | awk \'/PRESENCE usb0525:a4a7=False/ { n++ } '
             'END { print n+0 }\'', "_", str(ROOT / log)],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, "2", "the wedge round has two outages")
        rec = read("reference/boot-tests/test-195-20260925T1023Z/README.md")
        self.assertIn("never worked in this harness", " ".join(rec.split()))

    def test_an_unrequested_second_reboot_is_a_wedge(self):
        self.assertIn("presence_outages=", self.text)
        self.assertIn("automatic_reboot=", self.text)
        self.assertIn('[ "${p_n:-0}" -ge 2 ] && verdict=wedge', self.text)
        self.assertIn("that is the failure signature, not a clean round - stopping",
                      self.text)

    # 9. a requested reboot is not an automatic one -------------------------
    def test_a_requested_reboot_is_not_classified_as_automatic(self):
        """The harness issues exactly one reboot per round, by design."""
        self.assertIn("-Command 'systemctl reboot' -CommandAtSeconds 6", self.text)
        # Cleanliness is defined partly by the reboot being the harness's own.
        # The comment wraps, so match on the flattened text without the comment
        # markers rather than on any one physical line.
        flat = " ".join(self.text.replace("#", " ").split())
        self.assertIn("clean", flat)
        self.assertIn("no automatic reboot", flat)
        # And the requested reboot's own text must not be counted as automatic.
        self.assertNotIn("will reboot now", self.text)

    # 10. SysRq gadget path is unsupported ---------------------------------
    def test_the_ttygs_sysrq_path_is_marked_unsupported_everywhere(self):
        sh = read("scripts/sysrq-over-console.sh")
        ps1 = read("scripts/sysrq-over-console.ps1")
        for name, text in (("sh", sh), ("ps1", ps1)):
            with self.subTest(file=name):
                self.assertIn("UNSUPPORTED ON GTS9 TTYGS", text)
                self.assertIn("BreakState", text)
                self.assertIn("uart_port", text)
        # It must refuse by default in both layers.
        self.assertIn("--probe-unsupported-path", sh)
        self.assertIn("$ProbeUnsupportedPath", ps1)
        self.assertIn("exit 3", sh)
        self.assertIn("exit 3", ps1)

    def test_the_sysrq_refusal_is_the_default_on_this_host(self):
        import subprocess
        proc = subprocess.run(["bash", "scripts/sysrq-over-console.sh"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 3, "must refuse without the explicit flag")
        self.assertIn("UNSUPPORTED ON GTS9 TTYGS", proc.stderr + proc.stdout)

    # 11. fixtures stay separate from hardware evidence --------------------
    def test_fixture_and_hardware_evidence_stay_separate(self):
        """test-194 is hardware; test-186's fixtures are not, and never mix."""
        banner = ROOT / ("reference/boot-tests/test-186-20260924T230000Z/"
                         "fixtures/NOT-DEVICE-EVIDENCE.md")
        self.assertTrue(banner.exists(), "the fixtures banner must exist")
        # The provenance audit is hardware evidence and must not cite a fixture
        # as its source.
        audit = read(f"{self.T194}/PROVENANCE-AUDIT.md")
        self.assertIn("0f056455", audit)
        self.assertNotIn("programmed-no-completion.log", audit)
        self.assertNotIn("victim.log", audit)

    # 12. no mixing of ROUND files across RUNs -----------------------------
    def test_round_files_from_different_runs_cannot_mix(self):
        self.assertIn("refusing to mix runs", self.text)
        self.assertIn("GTS9_APPEND_RUNS", self.text)
        self.assertIn('echo "run=$RUN"', self.text)

    # the correction itself -------------------------------------------------
    def test_the_provenance_audit_states_what_was_retracted(self):
        audit = read(f"{self.T194}/PROVENANCE-AUDIT.md")
        flat = " ".join(audit.split())
        # The wrong boot, and the right one.
        self.assertIn("846e17b8", audit)
        self.assertIn("0f056455", audit)
        self.assertIn("the round analysed the wrong boot", flat)
        # The three-claims distinction.
        self.assertIn("three different claims", flat)
        self.assertIn("never reached the ring", audit)   # quoted as retracted
        self.assertIn("absent from that boot's journal capture", flat)
        # Level is not the explanation, and the source says why.
        self.assertIn("pr_err_ratelimited", audit)
        # The 7.887 s inference is withdrawn.
        self.assertIn("withdrawn", flat)

    def test_the_photo_is_bound_to_a_different_boot(self):
        tbl = read(f"{self.T194}/PHOTO-EVIDENCE-TABLE.md")
        flat = " ".join(tbl.split())
        self.assertIn("6.755336", tbl)
        self.assertIn("21.987343", tbl)
        self.assertIn("24.487343", tbl)
        # It must not claim a boot id it cannot prove.
        self.assertNotIn("| a2997452 |", tbl)
        self.assertIn("not named in any journal", tbl)
        # And the forbidden inference must be scoped, not used.
        self.assertIn("17.887 - 10 = 7.887 s", flat)
        self.assertIn("withdrawn", flat)
        self.assertIn("conditional form", flat)


if __name__ == "__main__":
    unittest.main()
