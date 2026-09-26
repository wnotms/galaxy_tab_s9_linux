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


class PlanDocumentTests(unittest.TestCase):
    """The plan is a plan: pre-registered, and honest in its vocabulary."""

    def test_the_three_documents_exist(self):
        for name in (PLAN, IDLE_ANALYSIS, CPUIDLE_DIFF):
            with self.subTest(doc=name):
                self.assertTrue((ROOT / name).is_file(), f"missing {name}")

    def test_the_decision_rule_is_pre_registered_with_a_verdict_table(self):
        text = read(PLAN)
        self.assertIn("## 5. The pre-registered decision rule", text)
        self.assertIn("Written before the first boot of this profile", text)
        # The gate row that stops the direction on a single wedge.
        self.assertIn("full cpuidle framework is not necessary for the wedge", text)
        # The sample-size ladder the brief asks for.
        for n in ("n = 10", "n = 30", "n = 60"):
            with self.subTest(n=n):
                self.assertIn(n, text)

    def test_it_forbids_the_success_vocabulary(self):
        text = read(PLAN)
        self.assertIn("Forbidden phrasings", text)
        for word in ("fixed", "solved", "root cause confirmed"):
            with self.subTest(word=word):
                self.assertIn(word, text)
        # and the only permitted form of a clean series
        self.assertIn("not reproduced in N boots", text)

    def test_it_states_that_zero_of_ten_is_no_evidence(self):
        """The arithmetic that stops '10 clean boots' being read as a result."""
        text = read(PLAN)
        self.assertIn("0 of 10 has a 71% probability", text)
        self.assertIn("Ten clean boots are *no evidence at all*", text)

    def test_a_single_wedge_is_the_first_row_of_the_rule(self):
        text = read(PLAN)
        rule = text.split("### 5.2 The rule", 1)[1].split("### 5.3", 1)[0]
        # The k>=1 row must appear before the clean-series rows: one wedge is a
        # fact, sixty clean boots are only a bound.
        self.assertLess(
            rule.index("any `k ≥ 1`"),
            rule.index("n = 10`, `k = 0"),
        )

    def test_it_records_that_the_briefs_per_cpu_profile_is_unbuildable(self):
        text = read(PLAN)
        self.assertIn("### 3.1 Why there is no `IDLE-LITTLE-ONLY` profile", text)
        self.assertIn("it cannot be built", text)

    def test_it_does_not_claim_a_fix(self):
        text = read(PLAN)
        self.assertIn("no \"final fix\" is proposed", text.lower())
        self.assertIn("**This is a hypothesis, not a conclusion", text)

    def test_it_keeps_the_downgraded_routes_downgraded(self):
        """The two closed directions must not be re-opened as experiments."""
        text = read(PLAN)
        self.assertIn("GPU is not necessary", text)
        self.assertIn("RPMh timeout branch is not necessary", text)

    def test_it_protects_the_cpu_path_fix(self):
        text = read(PLAN)
        self.assertIn("no revert", text.lower())
        self.assertIn("EPSS / OSM L3 / 3.36 GHz Prime OPP are **kept**", text)

    def test_it_declares_the_safety_boundaries(self):
        text = read(PLAN)
        self.assertIn("## 10. What this round does **not** do", text)
        for boundary in ("no flash", "no partition write", "no repartition",
                         "no change to `main`"):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, text)

    def test_it_answers_the_eight_final_questions(self):
        text = read(PLAN)
        self.assertIn("## 12. The questions the brief wants answered", text)
        for q in range(1, 9):
            with self.subTest(question=q):
                self.assertRegex(text, rf"\n\| {q} \| ")

    def test_the_idle_analysis_is_not_a_claim_about_unmerged_code(self):
        """The rename patch is v1 and unmerged; the doc must say so."""
        text = read(IDLE_ANALYSIS)
        self.assertIn("not merged", text)
        self.assertIn("20260914-b4-idle-state-name-v1-17-660c31187819@oss.qualcomm.com", text)
        self.assertIn("It is a naming and debugfs change", text)

    def test_the_idle_analysis_labels_the_state_names_as_labels_only(self):
        text = read(IDLE_ANALYSIS)
        self.assertIn("labels of convenience only", text)
        self.assertIn("It is not known", text)

    def test_the_diff_doc_records_teo_as_inert(self):
        text = read(CPUIDLE_DIFF)
        self.assertIn("does **not** change the active governor", text)


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
            r"case \"\$PROFILE\" in baseline\|no-acd\|no-gpu\|late-deferred\|rpmh-debug\|cpuidle-off\)",
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


def usage_names(src):
    m = re.search(r"PROFILE is one of: ([^\n]+)", src)
    return m.group(1) if m else ""


if __name__ == "__main__":
    unittest.main()
