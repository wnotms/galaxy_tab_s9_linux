"""Round 33: the `cpuidle.off=1` diagnostic profile.

This phase adds one profile and one arming gate. It deliberately changes nothing
about the kernel, the DTB or the existing profiles, so the tests below are mostly
about *what must not happen*:

* the new profile must be the baseline plus exactly one token, or it is not an
  ablation of the idle path - it is an ablation of two things at once, and
  `docs/CPU_IDLE_WEDGE_PLAN.md` forbids that;
* the arming gate must not use the check the brief suggests
  (`cat .../cpuidle/current_driver`), because under `cpuidle.off=1` that file
  does not exist - so a correctly-armed profile would be rejected as broken.
  The gate has to key on the *absence* of the sysfs group and on the governor
  never registering, and both of those are asserted here against the source;
* the plan's decision rule must be pre-registered, present, and must not contain
  any of the forbidden success words.

The Kconfig/source claims the arming gate rests on are verified against the
pinned tree by `test_the_arming_gate_is_derived_from_the_pinned_source` below,
so the gate cannot drift away from the kernel it is checking.
"""

import hashlib
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

BASELINE = "boot/cmdline.stall-ab-baseline.example.txt"
CPUIDLE_OFF = "boot/cmdline.stall-ab-cpuidle-off.example.txt"
NO_LLCC = "boot/cmdline.stall-ab-no-llcc-off.example.txt"
NO_CLUSTER = "boot/cmdline.stall-ab-no-cluster-idle.example.txt"
DTS_BASE = "kernel/dts/sm8550-samsung-gts9wifi.dts"
DTS_DIAG_DIR = "kernel/dts/diagnostic"
VERIFY = "scripts/verify-idle-ablation.sh"
PARSER = "scripts/lib/dtb-idle-states.py"
HARNESS = "scripts/stall-ab.sh"
PLAN = "docs/CPU_IDLE_WEDGE_PLAN.md"
IDLE_ANALYSIS = "docs/SM8550_IDLE_STATE_ANALYSIS.md"
CPUIDLE_DIFF = "docs/X710_X910_CPUIDLE_DIFF.md"

# The existing profiles that must stay byte-identical: this phase adds a
# profile, it does not touch a known-good boot.
KNOWN_GOOD = {
    BASELINE: "263814b89d811bddc7e6478951fb992c7381a44f1592435da039ae0ce0fb6403",
    "boot/cmdline.stall-ab-no-acd.example.txt": None,
    "boot/cmdline.stall-ab-no-gpu.example.txt": None,
    "boot/cmdline.stall-ab-late-deferred.example.txt": None,
}

PINNED_DTSI = ".work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550.dtsi"
PINNED_CPUIDLE = ".work/linux-mainline/drivers/cpuidle/cpuidle.c"
PINNED_PSCI_IDLE = ".work/linux-mainline/drivers/cpuidle/cpuidle-psci.c"
PINNED_GOVERNOR = ".work/linux-mainline/drivers/cpuidle/governor.c"


def read(rel):
    return (ROOT / rel).read_text()


def prose(rel):
    """File text with wrapping removed, for matching wrapped prose.

    Three assertions in this file failed on their first run purely because the
    phrase they looked for was split across a line break - by the markdown
    wrapping, by a shell comment's leading `#`, or by a blockquote's `>`.  This
    normalises all three away and is still an exact-substring check, so it does
    not loosen what is being asserted.
    """
    text = re.sub(r"(?m)^\s*(#|>)\s?", " ", read(rel))
    return " ".join(text.split())


def code_only(rel):
    """A DTS with its comments removed.

    The diagnostic overlays document *why* they avoid a construct - the
    no-llcc-off file explains at length that it is not a `/delete-property/`,
    and both cite the `cpu_pd` index-0 trap.  Asserting on the raw text would
    therefore flag the documentation as the violation it warns about, so the
    code checks below look at the code.
    """
    text = read(rel)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def tokens(rel):
    """The command line exactly as the bundle builder emits it.

    `scripts/build-boot-bundle.sh` does `tr '\\n' ' '` and strips the trailing
    space, so a `#` comment line would become literal kernel command-line text.
    """
    return read(rel).replace("\n", " ").strip().split()


def pinned(rel):
    """A file in the pinned upstream tree, or None if it is not checked out."""
    p = ROOT / rel
    return p.read_text() if p.exists() else None


class ProfileShapeTests(unittest.TestCase):
    """The profile is the baseline plus one token, and carries nothing else."""

    def test_it_is_the_baseline_plus_exactly_one_token(self):
        base = tokens(BASELINE)
        self.assertEqual(
            tokens(CPUIDLE_OFF),
            base[:2] + ["cpuidle.off=1"] + base[2:],
            "the cpuidle-off profile must be byte-identical to the baseline "
            "except for the single inserted token",
        )

    def test_the_added_token_is_the_documented_one(self):
        self.assertIn("cpuidle.off=1", tokens(CPUIDLE_OFF))
        self.assertNotIn("cpuidle.off", " ".join(tokens(BASELINE)))

    def test_it_carries_no_other_ablation_or_diagnostic_token(self):
        """One variable. Any second token makes the round unattributable."""
        joined = " ".join(tokens(CPUIDLE_OFF))
        for forbidden in (
            "msm.skip_gpu",
            "msm.disable_acd",
            "deferred_probe_timeout",
            "gts9_rpmh_debug",
            "gts9_kmsg_mirror",
            "gts9_dpu_flight",
            "gts9_poweroff_trace",
        ):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, joined)

    def test_it_keeps_the_non_negotiable_profile_tokens(self):
        """Every measured profile keeps the panel console and the detectors."""
        joined = " ".join(tokens(CPUIDLE_OFF))
        self.assertIn("console=tty0", joined)
        self.assertIn("msm.separate_gpu_kms=1", joined)
        self.assertIn("gts9_watchdog_debug=1", joined)
        self.assertIn("panic=10", joined)
        # Exactly one console, and it is the panel: a serial debug console is a
        # blocking writer under measurement (docs/BOOT_CONSOLE_BLOCK.md).
        self.assertEqual(joined.count("console="), 1)
        for gone in ("console=ttyGS1", "console=ttyMSM0", "earlycon"):
            self.assertNotIn(gone, joined)

    def test_it_is_pure_cmdline_with_no_comment_lines(self):
        text = read(CPUIDLE_OFF)
        self.assertNotIn("#", text)
        self.assertTrue(text.endswith("\n"))
        for tok in tokens(CPUIDLE_OFF):
            self.assertNotIn("\n", tok)

    def test_the_filename_follows_the_harness_convention(self):
        """stall-ab.sh resolves most profiles by name, so the name is load-bearing.

        The RPMh profile is the one documented exception (it predates the
        harness and two docs point at it).  A new profile must follow the
        convention, or the harness reports "missing profile file" and the
        profile is unusable even though every test above passes.
        """
        self.assertTrue(
            CPUIDLE_OFF.endswith("boot/cmdline.stall-ab-cpuidle-off.example.txt"),
            "a new profile must be named cmdline.stall-ab-<profile>.example.txt",
        )
        # And the harness must not have grown a special case for it.
        harness = read(HARNESS)
        self.assertNotIn("cpuidle-off) CMDLINE=", harness)
        self.assertIn(
            '*)          CMDLINE=$REPO/boot/cmdline.stall-ab-$PROFILE.example.txt ;;',
            harness,
        )

    def test_the_existing_profiles_are_untouched(self):
        for name, digest in KNOWN_GOOD.items():
            with self.subTest(cmdline=name):
                if digest is not None:
                    self.assertEqual(sha256(name), digest)


class KernelMechanismTests(unittest.TestCase):
    """Every claim the profile and its gate rest on, checked against source.

    These read the pinned tree under `.work/linux-mainline`.  They skip rather
    than fail when it is not checked out, because a missing worktree is not a
    defect in this repository - but they must never be *weakened* to pass.
    """

    def setUp(self):
        if pinned(PINNED_CPUIDLE) is None:
            self.skipTest("pinned mainline tree is not checked out")

    def test_cpuidle_off_is_a_builtin_module_param_read_by_cpuidle_disabled(self):
        src = pinned(PINNED_CPUIDLE)
        self.assertIn("module_param(off, int, 0444);", src)
        self.assertIn("int cpuidle_disabled(void)", src)
        self.assertRegex(src, r"int cpuidle_disabled\(void\)\s*\{\s*return off;")

    def test_cpuidle_init_bails_before_creating_the_sysfs_group(self):
        """This is why `current_driver` cannot be the arming check.

        `cpuidle_init()` is a core_initcall that returns -ENODEV when off, so
        `cpuidle_add_interface()` never runs and the whole
        `/sys/devices/system/cpu/cpuidle/` group is absent.  A gate written
        against `current_driver` would reject a correctly-armed profile.
        """
        src = pinned(PINNED_CPUIDLE)
        m = re.search(
            r"static int __init cpuidle_init\(void\)\s*\{(.*?)\n\}",
            src,
            re.S,
        )
        self.assertIsNotNone(m, "cpuidle_init() not found")
        body = m.group(1)
        self.assertIn("if (cpuidle_disabled())", body)
        self.assertIn("return -ENODEV;", body)
        # and the sysfs interface is created only after that guard
        self.assertIn("return cpuidle_add_interface();", body)

    def test_not_available_is_what_short_circuits_the_governor(self):
        """The gate the idle loop tests before falling back to WFI."""
        src = pinned(PINNED_CPUIDLE)
        self.assertIsNotNone(
            re.search(
                r"bool cpuidle_not_available\(.*?\n\{\s*"
                r"return off \|\| !initialized \|\| !drv \|\| !dev \|\| !dev->enabled;",
                src,
                re.S,
            ),
            "cpuidle_not_available() must return `off || !initialized || ...`; "
            "the whole profile depends on that first term",
        )

    def test_the_governor_is_registered_only_through_the_cpuidle_core(self):
        """The strong half of the gate.

        `cpuidle_register_governor()` returns -ENODEV when the framework is off,
        so `cpuidle: using governor menu` cannot be printed.  Its absence from
        the boot under test is therefore positive evidence, not a missing log.
        """
        src = pinned(PINNED_GOVERNOR)
        m = re.search(
            r"int cpuidle_register_governor\(struct cpuidle_governor \*gov\)\s*\{(.*?)\n\}",
            src,
            re.S,
        )
        self.assertIsNotNone(m, "cpuidle_register_governor() not found")
        body = m.group(1)
        self.assertIn("if (cpuidle_disabled())", body)
        self.assertIn("return -ENODEV;", body)
        self.assertIn('pr_info("cpuidle: using governor %s\\n", gov->name);', src)

    def test_menu_is_the_governor_that_wins_and_teo_cannot_displace_it(self):
        """Why CONFIG_CPU_IDLE_GOV_TEO=y is not the mechanism.

        `menu` sorts before `teo` in the cpuidle governors Makefile *and* rates
        higher (20 vs 19), so the switch condition cannot pick teo.  This is the
        claim docs/X710_X910_CPUIDLE_DIFF.md §1.1 makes.
        """
        menu = ROOT / ".work/linux-mainline/drivers/cpuidle/governors/menu.c"
        teo = ROOT / ".work/linux-mainline/drivers/cpuidle/governors/teo.c"
        mk = ROOT / ".work/linux-mainline/drivers/cpuidle/governors/Makefile"
        for f in (menu, teo, mk):
            if not f.exists():
                self.skipTest("governor sources are not checked out")
        self.assertRegex(menu.read_text(), r'\.name\s*=\s*"menu"')
        self.assertRegex(menu.read_text(), r"\.rating\s*=\s*20,")
        self.assertRegex(teo.read_text(), r'\.name\s*=\s*"teo"')
        self.assertRegex(teo.read_text(), r"\.rating\s*=\s*19,")
        mk_text = mk.read_text()
        self.assertLess(
            mk_text.index("menu.o"),
            mk_text.index("teo.o"),
            "menu must be registered before teo, which is half of why it wins",
        )

    def test_a_failed_psci_suspend_prints_nothing(self):
        """The reason `rejected` counters are mandatory evidence.

        There is no pr_*() on the failure path: the return value becomes -1 and,
        for a domain state, a counter is incremented.  So an empty dmesg is not
        evidence that PSCI behaved, and the plan may not treat it as such.
        """
        src = pinned(PINNED_PSCI_IDLE)
        self.assertIn("ret = psci_cpu_suspend_enter(state) ? -1 : idx;", src)
        self.assertIn("pm_genpd_inc_rejected(ds->pd, ds->state_idx);", src)
        # And no logging in that function's failure region.
        m = re.search(
            r"static __cpuidle int __psci_enter_domain_idle_state\(.*?\n\}",
            src,
            re.S,
        )
        self.assertIsNotNone(m, "__psci_enter_domain_idle_state() not found")
        self.assertNotIn("pr_err", m.group(0))
        self.assertNotIn("pr_warn", m.group(0))

    def test_the_cluster_state_overrides_the_cpu_state_in_osi_mode(self):
        """The line that makes 'the CPU state' and 'the PSCI state' different.

        In OSI mode the deepest CPU state's enter() is the domain one, and it
        overwrites `state` with the cluster's parameter when the genpd governor
        selected a domain state.  An ablation design that assumes the CPU-local
        parameter is what firmware receives would be wrong.
        """
        src = pinned(PINNED_PSCI_IDLE)
        self.assertIn("if (ds->state)\n\t\tstate = ds->state;", src)
        self.assertIn(
            "drv->states[state_count - 1].enter = psci_enter_domain_idle_state;",
            src,
        )
        # and it is limited to OSI mode
        self.assertIn("if (!psci_has_osi_support())\n\t\treturn 0;", src)

    def test_csd_lock_wait_debug_is_the_missing_instrument_and_is_off(self):
        """The one facility that names the stuck CPU's IPI handler.

        It must be recorded as a build item rather than silently enabled: it
        changes timing on the path the ablation measures, so it belongs in a
        separate diagnostic profile.  If the pinned tree ever gains the symbol
        this test fails and the plan's §2.1 must be re-read.
        """
        kconf = pinned(".work/linux-mainline/lib/Kconfig.debug")
        smp = pinned(".work/linux-mainline/kernel/smp.c")
        if kconf is None or smp is None:
            self.skipTest("pinned tree is not checked out")
        # Extract the entry by slicing to the next top-level `config`, rather
        # than a `.*?` regex: a non-greedy dot does not cross newlines without
        # re.S, and enabling re.S would let the match run past this entry into
        # an unrelated one that happens to say `default n`.
        start = kconf.index("\nconfig CSD_LOCK_WAIT_DEBUG\n")
        rest = kconf[start + 1:]
        nxt = rest.find("\nconfig ", 1)
        entry = rest[:nxt if nxt != -1 else len(rest)]
        self.assertIn("\tbool \"Debugging for csd_lock_wait()", entry)
        self.assertIn("\tdefault n\n", entry)
        # It really does print the handler and a stack.
        self.assertIn("IPI handler function currently executing", kconf)
        self.assertIn("non-responsive CSD lock", smp)
        self.assertIn("dump_cpu_task(cpu);", smp)
        # And it is not set in the X710 config, which is why it is a build item.
        cfg = read("out/kernel-gts9wifi/config")
        self.assertRegex(cfg, r"# CONFIG_CSD_LOCK_WAIT_DEBUG is not set")

    def test_the_trace_design_records_its_observer_effect(self):
        text = read(PLAN)
        self.assertIn("rcupdate.rcu_cpu_stall_ftrace_dump", text)
        self.assertIn("trace_clock=global", text)
        self.assertIn("single-shot", text)
        self.assertIn("Observer effect, recorded as the brief requires", text)
        # the deliberate exclusion of tp_printk, with its reason
        self.assertIn("tp_printk", text)
        self.assertIn("live-lock", text)

    def test_the_five_states_and_their_parameters_are_as_documented(self):
        src = pinned(PINNED_DTSI)
        if src is None:
            self.skipTest("pinned sm8550.dtsi is not checked out")
        for param in ("0x40000004", "0x41000044", "0x4100c344"):
            with self.subTest(param=param):
                self.assertIn(f"arm,psci-suspend-param = <{param}>;", src)
        # All three CPU states share ONE parameter: there is no per-cluster
        # PSCI parameter difference to blame.
        self.assertEqual(src.count("arm,psci-suspend-param = <0x40000004>;"), 3)
        # And cpu_pd3..cpu_pd7 exist, which is what the brief's proposed
        # per-CPU ablation would have had to edit.
        for n in range(8):
            with self.subTest(cpu_pd=n):
                self.assertIn(f"cpu_pd{n}: power-domain-cpu{n} {{", src)


class AblationConstraintTests(unittest.TestCase):
    """The per-CPU ablation the brief proposes cannot be built, and says so."""

    def setUp(self):
        if pinned(PINNED_DTSI) is None:
            self.skipTest("pinned mainline tree is not checked out")

    def test_removing_a_cpu_pd_state_would_kill_the_whole_driver(self):
        """The index-0 trap, asserted against the three functions involved.

        `dt_init_idle_driver()` stops at the first NULL state node, so removing
        `domain-idle-states` from a `cpu_pd` gives that CPU zero states, which
        makes `psci_idle_init_cpu()` return -ENODEV, which makes
        `psci_cpuidle_probe()` roll back EVERY cpu.  The brief's
        IDLE-LITTLE-ONLY profile would silently be cpuidle.off=1 for all eight.
        """
        cid = pinned(".work/linux-mainline/drivers/cpuidle/dt_idle_states.c")
        cpu_c = pinned(".work/linux-mainline/drivers/of/cpu.c")
        psci = pinned(PINNED_PSCI_IDLE)
        for name, src in (("dt_idle_states.c", cid), ("of/cpu.c", cpu_c),
                          ("cpuidle-psci.c", psci)):
            if src is None:
                self.skipTest(f"{name} is not checked out")
        # of_get_cpu_state_node resolves via the power domain first
        self.assertIn('of_parse_phandle(args.np, "domain-idle-states", index)', cpu_c)
        # dt_init_idle_driver breaks on the first NULL
        self.assertRegex(
            cid,
            r"state_node = of_get_cpu_state_node\(cpu_node, i\);\s*\n\s*if \(!state_node\)\s*\n\s*break;",
        )
        # and psci_idle_init_cpu rejects a zero-state driver
        self.assertIn("if (ret <= 0)\n\t\treturn ret ? : -ENODEV;", psci)
        # and any single failure unregisters all of them
        m = re.search(
            r"static int psci_cpuidle_probe\(struct faux_device \*fdev\)\s*\{(.*?)\n\}",
            psci,
            re.S,
        )
        self.assertIsNotNone(m, "psci_cpuidle_probe() not found")
        self.assertIn("goto out_fail;", m.group(1))
        self.assertIn("cpuidle_unregister(drv);", psci)

    def test_deleting_the_property_yields_a_synthetic_state_not_zero_states(self):
        """The no-cluster-idle mechanism, traced in the pinned source.

        The obvious reading of "delete domain-idle-states" is "the domain has no
        states and never powers down".  That is wrong: genpd synthesises a single
        state whose `data` is NULL, so `psci_pd_power_off()` returns early and no
        cluster suspend-param is ever handed to firmware - while the CPU's own
        0x40000004 still is.

        The distinction changes how the profile's result must be described, so it
        is pinned here against the three functions that produce it.  Without this
        test the documentation could drift back to the tempting shorthand and a
        reader would compare the two cluster profiles expecting a depth ordering
        that does not exist.
        """
        core = pinned(".work/linux-mainline/drivers/pmdomain/core.c")
        domain = pinned(".work/linux-mainline/drivers/cpuidle/cpuidle-psci-domain.c")
        psci = pinned(PINNED_PSCI_IDLE)
        for name, src in (("core.c", core), ("cpuidle-psci-domain.c", domain),
                          ("cpuidle-psci.c", psci)):
            if src is None:
                self.skipTest(f"{name} is not checked out")

        # 1. zero states is success and yields a NULL states array
        self.assertRegex(core, r"if \(!ret\) \{\s*\n\s*\*states = NULL;")
        # 2. the governor is NULL when there are no states, decided BEFORE
        #    pm_genpd_init() can synthesise one
        self.assertIn("pd_gov = pd->states ? &pm_domain_cpu_gov : NULL;", domain)
        self.assertIn("ret = pm_genpd_init(pd, pd_gov, false);", domain)
        # 3. gd is allocated only when there IS a governor, which is what makes
        #    the timed path in _genpd_power_off() false
        self.assertRegex(core, r"if \(genpd->gov\) \{\n\t\tgd = kzalloc_obj")
        # 4. one synthetic state is created for a domain with none.
        #    Sliced to the closing brace rather than matched with `.*?`: a
        #    non-greedy dot does not cross newlines without re.S, and enabling
        #    re.S would let the match run from this function into an unrelated
        #    one.
        def block(src, header):
            start = src.index(header)
            end = src.index("\n}", start)
            return src[start:end]

        synth = block(core, "static int genpd_set_default_power_state(")
        self.assertIn("kzalloc_obj(*state)", synth)
        self.assertIn("genpd->state_count = 1;", synth)
        self.assertIn("genpd_set_default_power_state(genpd)", core)

        # 5. the PSCI power-off hook bails on the missing data
        poff = block(domain, "static int psci_pd_power_off(")
        self.assertIn("if (!state->data)", poff)
        self.assertIn("return 0;", poff)
        # 6. so ds->state is never set, and the CPU param is what is sent
        self.assertIn("if (ds->state)\n\t\tstate = ds->state;", psci)

        # and the document says so, in these terms
        text = read(IDLE_ANALYSIS)
        self.assertIn("### 5.4 What deleting the whole property actually does", text)
        self.assertIn("the CPU-local `0x40000004` is what is sent", text)
        self.assertIn("not** nested in the way they look", text)

    def test_a_cluster_state_can_be_removed_cleanly(self):
        """The ablation that IS supported, asserted at its two tolerances.

        `genpd_iterate_idle_states()` skips unavailable nodes, and
        `of_genpd_parse_idle_states()` treats zero states as success - which is
        why board-level deletion of a `cluster_sleep_N` phandle works and the
        per-CPU equivalent does not.
        """
        core = pinned(".work/linux-mainline/drivers/pmdomain/core.c")
        genpd = pinned(".work/linux-mainline/drivers/cpuidle/dt_idle_genpd.c")
        if core is None or genpd is None:
            self.skipTest("pmdomain sources are not checked out")
        self.assertRegex(
            core,
            r"if \(!of_device_is_available\(np\)\)\s*\n\s*continue;",
        )
        self.assertRegex(
            core,
            r"if \(!ret\) \{\s*\n\s*\*states = NULL;\s*\n\s*\*n = 0;\s*\n\s*return 0;",
        )
        # and psci_pd_init tolerates a domain with no states to manage
        domain = pinned(".work/linux-mainline/drivers/cpuidle/cpuidle-psci-domain.c")
        self.assertIsNotNone(domain)
        self.assertIn("pd_gov = pd->states ? &pm_domain_cpu_gov : NULL;", domain)


class TestRecordTests(unittest.TestCase):
    """The on-device test record: a plan, not a result."""

    RECORD = "reference/boot-tests/test-226-cpuidle-off-gate"

    def test_it_is_recorded_as_prepared_and_not_as_a_result(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("Status: prepared, not flashed", text)
        self.assertIn("contains no result", text)
        # It must not claim any observation was made on hardware.  The one
        # legitimate "PASSED" is the validator's own read-only bundle verdict,
        # which is a statement about the images and not about the tablet, so the
        # check is anchored on the phrases that would assert a device result.
        for forbidden in ("**Result:", "we observed", "the tablet showed",
                          "physically verified", "the run showed"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        # A bundle-validation PASS is expected and must be the only PASS.
        self.assertEqual(text.count("PASS"), 1, "only the bundle verdict may say PASS")

    def test_the_identity_artifacts_are_present_and_match_the_bundle(self):
        for name in ("BUNDLE_INFO", "bundle-SHA256SUMS", "kernel-SHA256SUMS",
                     "kernel.release", "source-commit.txt"):
            with self.subTest(artifact=name):
                self.assertTrue((ROOT / self.RECORD / name).is_file(),
                                f"missing {name}")
        # The recorded bundle sums must be the built bundle's own sums.
        self.assertEqual(
            read(f"{self.RECORD}/bundle-SHA256SUMS"),
            read("out/boot-bundle-cpuidle-off/SHA256SUMS"),
        )
        # The recorded source commit is the commit whose tree the bundle was
        # built from.  It cannot be HEAD, because committing this record moves
        # HEAD forward - an earlier version of this test asserted equality and
        # failed for exactly that reason, which is the test doing its job on the
        # wrong invariant.
        import subprocess

        def git(*args):
            return subprocess.run(["git", "-C", str(ROOT), *args],
                                  capture_output=True, text=True,
                                  check=True).stdout.strip()

        recorded = read(f"{self.RECORD}/source-commit.txt").strip()
        self.assertRegex(recorded, r"^[0-9a-f]{40}$")
        # It must be committed history, not a dirty worktree state that no commit
        # describes.
        git("merge-base", "--is-ancestor", recorded, "HEAD")

        # The strong check, and the one that actually protects the record: the
        # artifacts recorded as flashed must be the artifacts this tree builds.
        # This subsumes any list of "inputs that could have changed" - a first
        # revision enumerated those files instead, which was both weaker (it
        # missed scripts/prepare-kernel.sh until it failed, then missed
        # kernel/dts/diagnostic/ by hand-waving) and noisier (it fired on commits
        # that cannot change a default build).
        #
        # It is skippable when the kernel has not been built, because a missing
        # out/ is not a defect - but it must never be weakened to pass.
        # ------------------------------------------------------------------
        # `Image.gz` is NOT reproducible across build *methods*, and the record
        # says so rather than pretending otherwise.
        #
        # Round 34 measured three different Image.gz hashes for the identical
        # source and the identical resolved config:
        #
        #   f7472872   the flashed image (produced by a relink of a warm tree)
        #   30ea8737   an incremental rebuild of the same tree
        #   51219ab1   a KERNEL_CLEAN=1 build, which reproduced exactly on a
        #              second clean run
        #
        # `Image.gz` is not reproducible by ANY build method, and a first pass
        # at this got that wrong by comparing a build with itself.  Two
        # *independent* KERNEL_CLEAN=1 runs gave 51219ab1 and 8b9ad746.  What is
        # reproducible is the code: those two builds differ by exactly two
        # printable strings, both the build timestamp
        # (`21260902183652Z` vs `21260902185640Z`, twenty minutes apart), while
        # every functional string checked (rcu_preempt, soft lockup,
        # toggle_allocation_gate, dpu_encoder_helper_wait_for_irq) is identical.
        # The 8 % byte delta is one contiguous ~4 MB region of entropy 7.999,
        # i.e. a compressed blob containing that timestamp, which shifts
        # wholesale when one input byte changes.
        #
        # The DTB and the resolved config, by contrast, ARE byte-stable, so those
        # are asserted exactly.  Weakening the Image check to a warning would be
        # wrong; asserting it exactly would fail on every honest rebuild, which
        # is how a check becomes noise nobody reads.
        # ------------------------------------------------------------------
        built = ROOT / "out/kernel-gts9wifi/SHA256SUMS"
        if not built.exists():
            self.skipTest("no built kernel to compare the recorded hashes against")
        recorded_sums = read(f"{self.RECORD}/kernel-SHA256SUMS")
        want = {}
        have = {}
        for line in recorded_sums.splitlines():
            if line.strip():
                d, n = line.split(None, 1)
                want[n.strip()] = d
        for line in built.read_text().splitlines():
            if line.strip():
                d, n = line.split(None, 1)
                have[n.strip()] = d
        # Byte-stable artifacts must match exactly.
        for name in ("sm8550-samsung-gts9wifi.dtb", "config", "kernel.release"):
            with self.subTest(artifact=name):
                self.assertEqual(have.get(name), want.get(name),
                                 f"{name} is byte-stable and must still match the record")
        # Image.gz must exist and be a kernel image, but its hash is
        # build-method dependent; that is recorded, not asserted away.
        self.assertIn("Image.gz", have)
        self.assertIn("Image.gz", want)
        # And they must be the hashes the candidate bundle names, so the chain
        # record -> kernel -> bundle is closed rather than two parallel claims.
        info = read(f"{self.RECORD}/BUNDLE_INFO")
        for name in ("Image.gz", "sm8550-samsung-gts9wifi.dtb"):
            digest = dict(
                line.split(None, 1)[::-1]
                for line in recorded_sums.splitlines()
                if line.strip()
            )[name].strip()
            with self.subTest(artifact=name):
                if name == "Image.gz":
                    self.assertIn(f"image_gz_sha256={digest}", info)
                else:
                    self.assertIn(f"dtb_sha256={digest}", info)

    def test_the_candidate_manifest_matches_the_real_bundles(self):
        """A manifest is only useful if its hashes are the bundles' own.

        It is written by hand from measured output, so it can drift the moment
        anyone rebuilds.  Every hash in it is checked against the artifact it
        claims to describe, and the bundle that is missing is skipped rather
        than silently accepted.
        """
        text = read(f"{self.RECORD}/CANDIDATE-MANIFEST.md")
        bundles = {
            "cpuidle-off": "out/boot-bundle-cpuidle-off",
            "abl-no-llcc-off": "out/boot-bundle-abl-no-llcc-off",
            "abl-no-cluster-idle": "out/boot-bundle-abl-no-cluster-idle",
        }
        checked = 0
        for key, path in bundles.items():
            if not (ROOT / path / "SHA256SUMS").exists():
                continue
            checked += 1
            sums = read(f"{path}/SHA256SUMS")
            for line in sums.splitlines():
                if not line.strip():
                    continue
                digest, name = line.split()
                with self.subTest(bundle=key, image=name):
                    self.assertIn(
                        f"{digest}  {name}", text,
                        f"{path}/{name} hash is not the one the manifest records",
                    )
            for field in ("image_gz_sha256", "dtb_sha256"):
                value = [
                    ln.split("=", 1)[1] for ln in read(f"{path}/BUNDLE_INFO").splitlines()
                    if ln.startswith(field + "=")
                ][0]
                with self.subTest(bundle=key, field=field):
                    self.assertIn(value, text)
        if checked == 0:
            self.skipTest("no candidate bundles are present to check against")

    def test_each_parked_bundle_verifies_against_itself(self):
        """The parked set must be checkable without rebuilding anything.

        scripts/validate-boot-bundle.sh compares a bundle against the built tree,
        so it passes only for whichever profile was built most recently - with
        three parked candidates, two always look broken. That is how a bundle
        set rots unnoticed.  verify-parked-bundle.sh checks the properties that
        must hold for any candidate, against the bundle alone.
        """
        import subprocess
        parked = {
            "cpuidle-off": "out/boot-bundle-cpuidle-off",
            "abl-no-llcc-off": "out/boot-bundle-abl-no-llcc-off",
            "abl-no-cluster-idle": "out/boot-bundle-abl-no-cluster-idle",
        }
        present = [(k, v) for k, v in parked.items() if (ROOT / v).is_dir()]
        if not present:
            self.skipTest("no parked bundles to verify")
        for profile, path in present:
            with self.subTest(bundle=profile):
                r = subprocess.run(
                    ["bash", str(ROOT / "scripts/verify-parked-bundle.sh"),
                     str(ROOT / path), profile.replace("abl-", "")],
                    capture_output=True, text=True,
                )
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("PARKED BUNDLE VERIFIED", r.stdout)

    def test_a_cmdline_only_profile_is_verified_against_the_baseline_dtb(self):
        """`cpuidle-off` has no ablation in its device tree at all.

        Asking the DTB verifier for an ablation it does not have would fail a
        perfectly good bundle - which it did, until the mapping was fixed.
        """
        text = read("scripts/verify-parked-bundle.sh")
        self.assertIn("dtb_profile=baseline", text)
        self.assertIn("The DTB profile is not always the bundle profile", text)
        self.assertIn("no-llcc-off|no-cluster-idle) dtb_profile=$profile", text)

    def test_the_manifest_warns_that_the_two_ablations_write_two_partitions(self):
        """The trap that produced a wrong table once already."""
        text = read(f"{self.RECORD}/CANDIDATE-MANIFEST.md")
        # `write` is the table's COLUMN HEADER, not part of the cell - an
        # earlier version of this assertion included it and failed on a manifest
        # that was correct.
        self.assertIn("| profile | write |", text)
        self.assertIn("| **`vendor_boot` only** |", text)
        self.assertIn("| **`boot` + `vendor_boot`** |", text)
        # and it must say why, with the measured hashes
        self.assertIn("An idle ablation changes **two** partitions", text)
        self.assertIn("71e194a5", text)
        self.assertIn("80aa010f", text)

    def test_the_manifest_gets_the_fdt_byte_order_right(self):
        """`od -tx4` on a little-endian host byte-reverses the big-endian FDT.

        The manifest first stated these as spaced bytes ('44 00 00 41'), which is
        not what the command prints and would have sent a reader chasing a
        mismatch that does not exist.  Pinned against the value the tool actually
        produces.
        """
        import struct
        text = read(f"{self.RECORD}/CANDIDATE-MANIFEST.md")
        raw = struct.pack(">I", 0x41000044)
        word = raw[::-1].hex()          # what `od -An -tx4` prints
        self.assertEqual(word, "44000041")
        self.assertIn(word, text)
        # the endian-independent check must be presented as the primary one
        self.assertIn("The **count** is the check to trust first", text)
        self.assertNotIn("44 00 00 41", text)

    def test_the_absent_physical_run_is_recorded_as_absent(self):
        """A prepared bundle must not read as a completed test.

        The tablet was not connected when this candidate was prepared, so no
        on-device run happened.  That has to be written down: a bundle with a
        README full of hashes and commands looks exactly like the aftermath of a
        successful run to anyone reading the directory later.
        """
        text = read(f"{self.RECORD}/STATUS-no-physical-run.md")
        self.assertIn("Nothing has been flashed", text)
        self.assertIn("not connected", text)
        # the evidence for that claim, so it is checkable rather than asserted
        for probe in ("adb devices", "packet loss", "COM19", "04e8"):
            with self.subTest(probe=probe):
                self.assertIn(probe, text)
        # and the correction it produced
        self.assertIn("71e194a5 -> 80aa010f", text)
        self.assertIn("1245bb39 -> e237a98e", text)

    def test_it_states_the_one_partition_delta_and_the_current_device_state(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("`vendor_boot` only", text)
        self.assertIn("1245bb39be1a6cfd65e381e44d19ce4ab29ca295f976f0c78067e4bfecc5b18a", text)
        self.assertIn("49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9", text)
        # The trap that was found while preparing this: the device's init_boot is
        # NEWER than the one in the older opp bundle, so reusing that one would
        # have added a second variable.
        self.assertIn("newer** than the one inside the older", text)
        self.assertIn("1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0", text)

    def test_it_warns_that_the_arming_check_is_by_absence(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("does not exist", text)
        self.assertIn("absence* is the positive signal", text)

    def test_it_carries_the_recovery_and_no_fix_language(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("## 7. Recovery", text)
        self.assertIn("Hold the power key", text)
        self.assertIn("Forbidden at every sample size", text)
        # and it defers to the pre-registered rule rather than restating a new one
        self.assertIn("do not re-derive it", text)


class WedgeSshRunnerTests(unittest.TestCase):
    """scripts/wedge-ssh.sh: the same experiment over the one transport present."""

    RUNNER = "scripts/wedge-ssh.sh"

    # Attribution, failure classes, unexpected restart handling and stopping
    # are exercised with archived logs and a mock transport in
    # test_wedge_evidence.py. Do not pin the old count/index implementation or
    # introductory prose here: those assertions passed with a broken verdict.

    def test_it_refuses_to_run_unless_the_profile_is_armed(self):
        text = read(self.RUNNER)
        self.assertIn("NOT armed", text)
        self.assertIn("arming gate PASSED", text)
        # the cpuidle-off gate decides on the sysfs group, per the plan
        self.assertIn("test -d /sys/devices/system/cpu/cpuidle", text)

    def test_it_never_writes_a_partition(self):
        text = read(self.RUNNER)
        for forbidden in ("dd if=", "of=/dev/", "fastboot", "mkbootimg", "avbtool"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, text)


class WedgeResultRecordTests(unittest.TestCase):
    """The test-227 record: a decided result, with its corrections kept."""

    RECORD = "reference/boot-tests/test-227-cpuidle-off-run"

    def test_it_records_the_pre_registered_first_row_outcome(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("the plan's pre-registered first-row outcome", text)
        flat = prose(f"{self.RECORD}/README.md").replace("**", "")
        # The rule is quoted verbatim from the plan; with the blockquote marker
        # stripped the phrase is contiguous again.
        self.assertIn("full cpuidle framework is not necessary for the wedge", flat)
        self.assertIn("go to §7", flat)

    def test_it_does_not_claim_a_fix_or_a_cause(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("Nothing here is a fix", text)
        self.assertIn("Any cause.", text)          # listed under "Does not establish"
        self.assertIn("PSCI-idle hypothesis is `downgraded`", text)
        # The words themselves appear - but only as negations ("nothing here is
        # `solved'"), which is the opposite of claiming them.  Assert the
        # negations are present and that no POSITIVE claim is made.
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("Nothing here is a fix, and nothing here is `solved`", flat)
        for claim in ("is solved", "has been solved", "the wedge is fixed",
                      "root cause is confirmed", "the cause is"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, flat)

    def test_the_three_cpu_roles_are_stated_correctly(self):
        """Victim, detector and reporter are three different CPUs.

        An earlier draft called CPU 1 a victim. It is the `events_unbound`
        reporter whose stack is the documented canary, and conflating the two is
        the mistake this project already corrected once
        (docs/CPU_WEDGE_EVIDENCE.md, "the reporting CPU, not the wedged ones").
        """
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("the stalled CPU", text)
        self.assertIn("the **detector**", text)
        self.assertIn("the **reporter**", text)
        self.assertIn("the canary, not the\n  cause", text.replace("**", ""))
        self.assertIn("An earlier draft of this section called CPU 1 a victim", text)

    def test_it_archives_the_evidence_it_cites(self):
        for name in ("PRE-WRITE-STATE.txt", "FLASH-TRANSCRIPT.md",
                     "evidence/pstore-raw.txt",
                     "evidence/wedged-boot-minus1-klog.txt",
                     "evidence/wedged-boot-minus2-klog.txt",
                     "evidence/boot-list.txt",
                     "evidence/arming-during-wedges.txt",
                     "evidence/genpd-with-cpuidle-off.txt"):
            with self.subTest(artifact=name):
                self.assertTrue((ROOT / self.RECORD / name).is_file(),
                                f"missing evidence: {name}")

    def test_the_cited_wedge_markers_are_actually_in_the_pstore(self):
        """Every line the README quotes must exist in the archived record.

        Read as bytes: the file is the device's ramoops console verbatim and
        contains NULs and occasional corruption, which is exactly why it is kept
        raw instead of being cleaned up.
        """
        path = ROOT / self.RECORD / "evidence/pstore-raw.txt"
        raw = path.read_bytes().decode("utf-8", "replace")
        for needle in (
            "rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:",
            "4-...!: (0 ticks this GP)",
            "softirq=1391/1391",
            "watchdog: BUG: soft lockup - CPU#1 stuck for 26s! [kworker/u32:9",
            "Kernel panic - not syncing: softlockup: hung tasks",
            "SMP: failed to stop secondary CPUs 4,6-7",
            "toggle_allocation_gate+0x58/0x14c",
            "smp_call_function_many_cond+0x3ec/0x514",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, raw)

    def test_it_marks_what_was_not_captured(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("Not captured, and marked absent rather than implied", text)
        self.assertIn("/proc/interrupts", text)

    def test_it_records_the_elevated_clustered_rate_without_claiming_it(self):
        """2 of 4 is above both fixed-era baselines, and it must say so.

        The registered conclusion stands on its own evidence - a wedge with the
        framework absent means cpuidle is not necessary.  But presenting the
        profile as merely neutral would hide that the count is unlikely under the
        measured rate, and that the two failures were CONSECUTIVE.  The record
        must state both, name the two readings, and refuse to pick one.
        """
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("two of them wedged", flat)
        self.assertIn("0.0068", flat)          # P(>=2 in 4) vs 3.4%
        self.assertIn("0.16–0.84", flat)       # the CI, so no rate is claimed
        self.assertIn("the two failures are consecutive", flat)
        self.assertIn("this is a different shape", flat)
        # both readings named, and neither chosen
        self.assertIn("does `cpuidle.off=1` change the rate?", flat)
        self.assertIn("this is a signal to test, not a finding", flat)
        # and the forbidden over-claim is explicitly forbidden
        self.assertIn("must not be written as", flat)
        self.assertIn("cpuidle.off=1 makes the wedge worse", flat)

    def test_the_profile_was_reverted_and_the_revert_is_recorded(self):
        """An unexplained elevated rate must not be left on the tablet."""
        flat = prose(f"{self.RECORD}/ROLLBACK.md")
        self.assertIn("restored to the pre-test image", flat)
        self.assertIn("49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9", flat)
        self.assertIn("read-back", flat)
        # and the reason it was done
        self.assertIn("elevated-rate observation", flat)
        # The revert must be CONFIRMED in behaviour, not just in bytes: the
        # running kernel's /proc/cmdline still showed the token right after the
        # write, because it comes from RAM. Only a reboot proves the revert, and
        # the record has to say so or a reader will think the write was enough.
        self.assertIn("Confirmed in effect after a reboot", flat)
        self.assertIn("psci_idle", flat)
        self.assertIn("449 / 1246", flat)
        self.assertIn("reports the **running** kernel's command line", flat)

    def test_it_names_the_rollback_and_its_hash(self):
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9", text)
        self.assertIn("/dev/sda24", text)


class HarnessTests(unittest.TestCase):
    """The harness accepts the profile and gates it before counting rounds."""

    def setUp(self):
        self.src = read(HARNESS)

    def _case_block(self, require):
        """The `cpuidle-off)` case arm that contains `require`.

        There are two: one validates the profile *file* before the run, and one
        is the arming gate that inspects the *tablet*.  Selecting by content is
        deliberate - a positional match would silently start testing the wrong
        block if a profile were ever reordered.
        """
        # Slice to the closing `esac`, not to the first `;;`: the arming gate
        # contains its own inner `case` whose arms also end in `;;`, so a
        # non-greedy match on `;;` would truncate it and then report the block
        # as missing.
        starts = [m.end() for m in re.finditer(r"\n\tcpuidle-off\)\n", self.src)]
        blocks = []
        for st in starts:
            end = self.src.find("\nesac", st)
            blocks.append(self.src[st:end if end != -1 else len(self.src)])
        hits = [b for b in blocks if require in b]
        self.assertEqual(
            len(hits), 1,
            f"expected exactly one cpuidle-off case arm containing {require!r}, "
            f"found {len(hits)} of {len(blocks)} blocks",
        )
        return hits[0]

    def test_the_harness_knows_the_profile(self):
        self.assertIn("cpuidle-off", self.src)
        # the accepted-profile case list
        self.assertRegex(
            self.src,
            r"case \"\$PROFILE\" in baseline\|no-acd\|no-gpu\|late-deferred"
            r"\|rpmh-debug\|cpuidle-off\|no-llcc-off\|no-cluster-idle\)",
        )
        self.assertIn("cpuidle-off", usage_names(self.src))

    def test_the_harness_requires_the_token_and_only_the_token(self):
        gate = self._case_block(require="cpuidle-off profile lacks")
        self.assertIn("cpuidle\\.off=1", gate)
        for forbidden in ("msm.skip_gpu", "msm.disable_acd",
                          "deferred_probe_timeout", "gts9_rpmh_debug"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, gate)

    def test_the_arming_gate_does_not_use_current_driver(self):
        """The trap the brief's suggested check would have walked into.

        Under cpuidle.off=1 the sysfs group does not exist, so a gate keyed on
        `current_driver` would reject a correctly-armed profile.  The gate may
        *record* the driver, but it must decide on the sysfs group's absence and
        on the governor never having registered.
        """
        gate = self._case_block(require="arming gate PASSED")
        self.assertIn("cpuidle_sysfs", gate)
        self.assertIn("ABSENT", gate)
        self.assertIn("cpuidle_gov_boot", gate)
        self.assertIn("arming gate PASSED", gate)
        # It must refuse to conclude anything when arming cannot be verified.
        self.assertIn("no round may be counted", gate)
        self.assertIn("die ", gate)

    def test_the_probe_collects_the_mandatory_cpuidle_evidence(self):
        for field in ("cpuidle_sysfs=", "cpuidle_driver=", "cpuidle_gov_boot=",
                      "cpuidle_states=", "genpd_cluster=", "psci_caps="):
            with self.subTest(field=field):
                self.assertIn(field, self.src)
        # `rejected` is the only signal a failed CPU_SUSPEND produces, so both
        # the per-CPU and the per-domain counter must be read.
        self.assertIn("/rejected", self.src)
        self.assertIn("pm_genpd/power-domain-cluster/idle_states", self.src)

    def test_the_cpuidle_fields_reach_the_probe_filter_and_the_round_record(self):
        # the two grep filters that keep probe output
        self.assertGreaterEqual(self.src.count("cpuidle_sysfs=|cpuidle_driver="), 2)
        # the round record loop
        self.assertIn("for f in cpuidle_sysfs cpuidle_driver cpuidle_gov "
                      "cpuidle_gov_boot psci_caps; do", self.src)
        self.assertIn('echo "cpuidle_states=$(sed -n', self.src)
        self.assertIn('echo "genpd_cluster=$(sed -n', self.src)

    def test_the_summary_table_shows_whether_the_profile_armed(self):
        self.assertIn("sysfs", self.src)
        self.assertIn("gov  boot_id", self.src)

    def test_the_observer_effect_rule_still_covers_the_other_profiles(self):
        """cpuidle-off is allowed to change behaviour; rpmh-debug is not.

        The A/B observer-effect gate must still forbid the instrumentation
        tokens, and cpuidle.off must remain absent from the *other* profiles -
        otherwise the A/B baseline silently becomes a different experiment.
        """
        self.assertIn("observer_forbidden=", self.src)
        self.assertIn("must be absent from an A/B profile", self.src)
        # rpmh-debug must keep refusing cpuidle.off alongside it
        self.assertIn("msm.disable_acd deferred_probe_timeout cpuidle.off", self.src)

    def test_the_script_still_refuses_to_flash(self):
        for forbidden in ("fastboot flash", "flash partition",
                          "mkbootimg", "avbtool"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, self.src)
        self.assertIn("never flashes", self.src)


class ClusterAblationTests(unittest.TestCase):
    """Profiles I and J: the variable is the DTB, not the command line."""

    VARIANTS = {
        "no-llcc-off": f"{DTS_DIAG_DIR}/sm8550-samsung-gts9wifi-no-llcc-off.dts",
        "no-cluster-idle": f"{DTS_DIAG_DIR}/sm8550-samsung-gts9wifi-no-cluster-idle.dts",
    }

    def test_both_variants_exist_and_are_diagnostic_only(self):
        for name, path in self.VARIANTS.items():
            with self.subTest(variant=name):
                text = read(path)
                self.assertIn("DIAGNOSTIC OVERLAY", text)
                self.assertIn("not a fix", text)
                self.assertIn("not part of the default build", text)

    def test_the_overlay_includes_the_board_tree_by_a_non_conflicting_name(self):
        """The overlay is copied ONTO the name it would otherwise include.

        That is self-inclusion: a first revision did exactly that and would have
        looped or produced an empty tree.  The include must therefore name a
        different file, and prepare-kernel.sh must install the real board tree
        under that name.
        """
        for name, path in self.VARIANTS.items():
            with self.subTest(variant=name):
                text = read(path)
                self.assertIn('#include "sm8550-samsung-gts9wifi-board.dts"', text)
                self.assertNotIn('#include "sm8550-samsung-gts9wifi.dts"', text)
        prep = read("scripts/prepare-kernel.sh")
        self.assertIn('"$qcom_dts/sm8550-samsung-gts9wifi-board.dts"', prep)

    def test_no_llcc_off_overrides_the_list_and_keeps_the_shallow_state(self):
        text = code_only(self.VARIANTS["no-llcc-off"])
        self.assertIn("domain-idle-states = <&cluster_sleep_0>;", text)
        # It must NOT delete the property: that would be the other profile.
        self.assertNotIn("/delete-property/", text)

    def test_no_cluster_idle_deletes_the_property(self):
        text = code_only(self.VARIANTS["no-cluster-idle"])
        self.assertIn("/delete-property/ domain-idle-states", text)

    def test_neither_variant_touches_the_per_cpu_states(self):
        """The index-0 trap: touching a cpu_pd would cost all eight CPUs cpuidle."""
        for name, path in self.VARIANTS.items():
            with self.subTest(variant=name):
                text = code_only(path)
                self.assertNotIn("cpu_pd", text)
                self.assertNotIn("little_cpu_sleep_0", text)
                self.assertNotIn("big_cpu_sleep_0", text)
                self.assertNotIn("prime_cpu_sleep_0", text)
                # And only one override block, so a later edit cannot quietly add
                # a second one that the verifier would not notice.
                self.assertEqual(text.count("&cluster_pd {"), 1)

    def test_the_command_lines_are_byte_identical_to_baseline(self):
        """The whole point: no token distinguishes these profiles."""
        base = (ROOT / BASELINE).read_bytes()
        for name in (NO_LLCC, NO_CLUSTER):
            with self.subTest(cmdline=name):
                self.assertEqual((ROOT / name).read_bytes(), base)

    def test_the_build_script_embeds_the_dtb_in_both_partitions(self):
        """An ablation changes TWO images, and the plan said one until measured.

        `build-boot-bundle.sh` appends the DTB to boot.img's payload and also
        passes the same file as `--dtb` to vendor_boot.img.  So a DTB-only
        profile cannot be flashed by writing one partition: the two copies would
        disagree about the cluster idle states and the round would be
        uninterpretable.  Asserted against the script, so a future edit that
        drops one of the two copies is caught here rather than on the tablet.
        """
        bundle = read("scripts/build-boot-bundle.sh")
        # appends to the boot.img payload
        self.assertIn('cat "$image" "$dtb" > "$tmp/boot-kernel"', bundle)
        # and passes the same file to vendor_boot
        self.assertIn('--dtb "$dtb" --vendor_cmdline "$cmdline"', bundle)
        # and the plan records the measured two-partition delta
        plan = read(PLAN)
        self.assertIn("Both DTB-carrying partitions must be written", plan)
        self.assertIn("71e194a5 -> 80aa010f", plan)
        self.assertIn("1245bb39 -> e237a98e", plan)

    def test_the_plan_documents_the_build_and_arm_recipe(self):
        """A profile that cannot be built and armed is not a profile.

        The plan's first draft got profile 2's mechanism wrong - it said "delete
        the cluster_sleep_1 phandle", which is not an operation.  The recipe and
        the corrected mechanism are asserted so the document cannot drift back.
        """
        text = read(PLAN)
        self.assertIn("GTS9_IDLE_ABLATION=no-llcc-off", text)
        self.assertIn("verify-idle-ablation.sh", text)
        self.assertIn("**The verify step is not optional", text)
        # the corrected mechanism, named as such
        self.assertIn("override** the `cluster_pd` phandle list", text)
        self.assertIn("There is no such operation", text)
        # and why the cmdline cannot arm these profiles
        self.assertIn("command line\nbyte-identical to baseline", text)

    def test_prepare_kernel_accepts_only_the_closed_set(self):
        prep = read("scripts/prepare-kernel.sh")
        self.assertIn("GTS9_IDLE_ABLATION", prep)
        self.assertRegex(prep, r"''\|no-llcc-off\|no-cluster-idle\) ;;")
        self.assertIn("must be empty, no-llcc-off or no-cluster-idle", prep)


class DtbParserTests(unittest.TestCase):
    """The verifier's parse, which is the only thing standing between a silent
    no-op ablation and a clean boot series."""

    def test_the_parser_exists_and_is_executable(self):
        p = ROOT / PARSER
        self.assertTrue(p.is_file())
        self.assertTrue(p.stat().st_mode & 0o100, "parser must be executable")

    def test_it_parses_the_baseline_dtb_correctly(self):
        """Run the real parser on the real built DTB, if it is present."""
        dtb = ROOT / "out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb"
        if not dtb.exists():
            self.skipTest("no built DTB to parse")
        import subprocess
        r = subprocess.run(["python3", str(ROOT / PARSER), str(dtb)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout

        def get(key):
            for line in out.splitlines():
                if line.startswith(key + "="):
                    return line[len(key) + 1:]
            return None

        self.assertEqual(get("cluster_pd_node"), "/psci/power-domain-cluster")
        self.assertEqual(get("cluster_states"), "0x41000044 0x4100c344")
        self.assertEqual(get("cpu_pd_count"), "8")
        self.assertEqual(get("cpu_states_with_shared_param"), "3")
        self.assertEqual(get("cluster_state_definitions"), "2")
        self.assertEqual(get("model"), "Samsung Galaxy Tab S9 Wi-Fi")
        self.assertEqual(get("board_id"), "present")
        for n in range(8):
            self.assertEqual(get(f"cpu_pd_state_count:power-domain-cpu{n}"), "1")
        for name in ("silver", "gold", "goldplus"):
            self.assertEqual(
                get(f"cpu_state_name:{name}-rail-power-collapse"), "present")

    def test_the_parser_does_not_count_lines_where_it_must_count_phandles(self):
        """The bug the first awk revision had.

        `domain-idle-states = <0x30 0x31>` is two phandles on ONE line, so a
        line-counting parser returns 1 and silently mis-reports an unablated
        tree as ablated.  Asserted here on a synthetic tree so the test does not
        depend on which DTB happens to be built.
        """
        import subprocess
        import tempfile
        dts = """
/dts-v1/;
/ {
	model = "synthetic";
	psci {
		cluster_pd: power-domain-cluster {
			#power-domain-cells = <0x00>;
			domain-idle-states = <0x30 0x31>;
		};
	};
	cpus {
		idle-states {
			cluster-sleep-0 { compatible = "domain-idle-state";
				arm,psci-suspend-param = <0x41000044>; phandle = <0x30>; };
			cluster-sleep-1 { compatible = "domain-idle-state";
				arm,psci-suspend-param = <0x4100c344>; phandle = <0x31>; };
		};
	};
};
"""
        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / "t.dts"
            dtb = pathlib.Path(td) / "t.dtb"
            src.write_text(dts)
            c = subprocess.run(["dtc", "-I", "dts", "-O", "dtb",
                                "-o", str(dtb), str(src)],
                               capture_output=True, text=True)
            if c.returncode != 0:
                self.skipTest("dtc unavailable")
            r = subprocess.run(["python3", str(ROOT / PARSER), str(dtb)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("cluster_states=0x41000044 0x4100c344", r.stdout)


class AblationVerifierTests(unittest.TestCase):
    """The verifier must accept the right DTB and reject every wrong one."""

    def _run(self, dtb, profile):
        import subprocess
        return subprocess.run(
            ["bash", str(ROOT / VERIFY), str(dtb), profile],
            capture_output=True, text=True,
        )

    def test_a_wrong_profile_is_rejected(self):
        dtb = ROOT / "out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb"
        if not dtb.exists():
            self.skipTest("no built DTB")
        r = self._run(dtb, "baseline")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # The unablated tree must NOT pass as either ablation.
        for profile in ("no-llcc-off", "no-cluster-idle"):
            with self.subTest(profile=profile):
                r = self._run(dtb, profile)
                self.assertNotEqual(r.returncode, 0,
                                    f"unablated DTB passed as {profile}")
                self.assertIn("cluster_pd references", r.stdout)

    def test_an_unknown_profile_is_refused(self):
        dtb = ROOT / "out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb"
        if not dtb.exists():
            self.skipTest("no built DTB")
        r = self._run(dtb, "no-such-profile")
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown profile", r.stderr)

    def test_it_verifies_the_dtb_inside_the_bundle_that_would_be_flashed(self):
        """The artifact that matters is the one in the bundle, not out/.

        Everything else in this file verifies out/kernel-gts9wifi/*.dtb or an
        ablation build in .work/.  Neither is what a flash writes: the flashed
        DTB is the one appended to boot.img (and mirrored into vendor_boot), and
        nothing was checking it.  A bundle assembled from a stale build would
        have passed every other test here.

        This closes the gap end to end: extract the DTB from the candidate
        bundle's own boot.img payload, verify it, and require boot.img and
        vendor_boot to agree - they are two independent copies of the same tree
        and a mismatch means the bootloader and the kernel would disagree about
        the idle states.
        """
        import struct
        import subprocess
        import zlib

        bundle = ROOT / "out/boot-bundle-cpuidle-off"
        boot_img = bundle / "boot.img"
        vendor_boot = bundle / "vendor_boot.img"
        if not boot_img.exists():
            self.skipTest("the cpuidle-off bundle has not been built")

        payload = boot_img.read_bytes()
        start = payload.find(b"\x1f\x8b\x08")
        self.assertGreater(start, 0, "no gzip payload in the candidate boot.img")
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        d.decompress(payload[start:])
        unused = d.unused_data
        self.assertEqual(unused[:4], b"\xd0\x0d\xfe\xed", "no appended DTB")
        # The partition is padded, so the DTB length comes from the FDT header's
        # totalsize field rather than from len(unused).
        dtb_size = struct.unpack(">I", unused[4:8])[0]
        appended = unused[:dtb_size]

        # It must be the DTB the bundle's own manifest names.
        info = read("out/boot-bundle-cpuidle-off/BUNDLE_INFO")
        want = [
            line.split("=", 1)[1] for line in info.splitlines()
            if line.startswith("dtb_sha256=")
        ][0]
        self.assertEqual(hashlib.sha256(appended).hexdigest(), want,
                         "the bundle's boot.img DTB is not the one BUNDLE_INFO names")

        # Write it out and run the real verifier on it.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "candidate.dtb"
            path.write_bytes(appended)
            r = self._run(str(path), "baseline")
            self.assertEqual(r.returncode, 0,
                             "the candidate bundle's own DTB failed verification:\n"
                             + r.stdout + r.stderr)
            # and it must be rejected as each ablation, or the gate is toothless
            for profile in ("no-llcc-off", "no-cluster-idle"):
                with self.subTest(profile=profile):
                    r = self._run(str(path), profile)
                    self.assertNotEqual(
                        r.returncode, 0,
                        f"the candidate bundle's DTB passed as {profile}")

        # boot.img and vendor_boot carry independent copies of the same tree.
        if not vendor_boot.exists():
            self.skipTest("no vendor_boot.img in the candidate bundle")
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(
                ["python3", str(ROOT / ".work/tools/unpack_bootimg.py"),
                 "--boot_img", str(vendor_boot), "--out", td],
                capture_output=True, check=False,
            )
            vendor_dtb = pathlib.Path(td) / "dtb"
            if not vendor_dtb.exists():
                self.skipTest("could not extract the vendor_boot DTB")
            self.assertEqual(
                hashlib.sha256(vendor_dtb.read_bytes()).hexdigest(),
                hashlib.sha256(appended).hexdigest(),
                "boot.img and vendor_boot.img carry DIFFERENT device trees; the "
                "bootloader and the kernel would disagree about the idle states",
            )

    def test_a_missing_dtb_is_refused(self):
        r = self._run("/nonexistent.dtb", "baseline")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no such DTB", r.stderr)


class ClusterHarnessGateTests(unittest.TestCase):
    """The DTB-driven arming gate: the only way to identify these profiles."""

    def setUp(self):
        self.src = read(HARNESS)

    def test_the_harness_knows_both_profiles(self):
        self.assertRegex(self.src, r"no-llcc-off\|no-cluster-idle")
        self.assertIn("no-llcc-off", usage_names(self.src))

    def test_it_asserts_the_cmdline_is_byte_identical_to_baseline(self):
        self.assertIn("byte-identical cmdline to baseline", self.src)
        self.assertIn("cmp -s", self.src)

    def test_the_probe_reads_the_device_tree_not_just_the_cmdline(self):
        for field in ("dt_cluster_states=", "dt_cluster_param=",
                      "dt_cpu_state_params=", "dt_cpu_state_names=", "dt_model="):
            with self.subTest(field=field):
                self.assertIn(field, self.src)
        self.assertIn("/proc/device-tree/psci/power-domain-cluster", self.src)

    def test_the_gate_requires_the_per_cpu_states_to_be_intact(self):
        """The guard against the index-0 trap reaching the tablet."""
        self.assertIn("per-CPU states are intact", self.src)
        self.assertIn("expected 3 per-CPU idle states", self.src)
        self.assertIn("0x40000004", self.src)

    def test_the_gate_reads_the_dt_big_endian(self):
        """The FDT is big-endian and /proc/device-tree exposes raw bytes.

        Verified in drivers/of/kobj.c: `memory_read_from_buffer(..., pp->value,
        ...)` copies without conversion, so every 32-bit read on a little-endian
        host must be byte-swapped.  The cluster param did this from the start and
        the per-CPU one did not - a latent gate that would have rejected a
        correct DTB and looked like an ablated build failing to arm.
        """
        # Both 32-bit readers must byte-swap.
        self.assertEqual(self.src.count(r"s/\(..\)\(..\)\(..\)\(..\)/\4\3\2\1/"), 2)
        # And the per-CPU reader must not use a native-endian 32-bit read.
        self.assertNotIn('printf "0x%x " $(od -An -tu4 "$s")', self.src)

    def test_the_dt_identity_reaches_the_round_record(self):
        self.assertIn("for f in dt_cluster_states dt_cluster_param "
                      "dt_cpu_state_names dt_cpu_state_params dt_model; do",
                      self.src)

    def test_both_dt_fields_reach_both_probe_filters(self):
        self.assertGreaterEqual(self.src.count("dt_cluster_states=|"), 2)


def usage_names(src):
    """The profile list from the harness's usage text.

    The list is wrapped across lines once it grows past the width the file uses,
    so this reads to the end of the usage block rather than to the end of the
    line - an earlier one-line version silently truncated and reported the
    last profile as missing.
    """
    m = re.search(r"PROFILE is one of: (.*?)\nEOF", src, re.S)
    if not m:
        m = re.search(r"PROFILE is one of: ([^\n]+)", src)
    return " ".join(m.group(1).split()) if m else ""


if __name__ == "__main__":
    unittest.main()
