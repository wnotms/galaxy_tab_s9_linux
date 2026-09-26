"""Round 34: the CSD/IPI diagnostic profile.

The instrument this round turns on is the one that can answer why a wedged CPU
stopped answering IPIs, and the failure mode it guards against is silent in the
worst direction: a build that *believes* it is instrumented but is not produces a
wedge with no CSD output, and docs/CSD_IPI_WEDGE_PLAN.md Case D exists precisely
to stop that being read as "CSD is not involved".

So most of what follows is about the split being real in both directions:

* the production configuration must NOT acquire `CONFIG_CSD_LOCK_WAIT_DEBUG`,
  including when the diagnostic fragment is named but the build is meant to be
  production;
* the diagnostic configuration must have BOTH the symbol and its `_DEFAULT`
  companion, because the Kconfig symbol alone enables nothing at runtime - the
  static key is `DEFINE_STATIC_KEY_MAYBE(CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT, ...)`
  and that defaults to `n`;
* nothing else may ride along: one instrument at a time is what makes a result
  attributable.

Every kernel-side claim is read out of the pinned tree rather than restated from
a search result, so the tests cannot drift away from the kernel they describe.
"""

import hashlib
import pathlib
import re
import struct
import subprocess
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[1]

CSD_FRAGMENT = "kernel/config/gts9wifi-csd-lock.fragment"
CSD_CMDLINE = "boot/cmdline.stall-ab-csd-lock.example.txt"
BASELINE_CMDLINE = "boot/cmdline.stall-ab-baseline.example.txt"
PLAN = "docs/CSD_IPI_WEDGE_PLAN.md"
BUILD = "scripts/build-kernel.sh"
DIAG_OUT = "out/kernel-gts9wifi-csd-lock"
DIAG_BUNDLE = "out/boot-bundle-csd-lock"

PINNED_SMP = ".work/linux-mainline/kernel/smp.c"
PINNED_KCONFIG = ".work/linux-mainline/lib/Kconfig.debug"
PINNED_TYPES = ".work/linux-mainline/include/linux/smp_types.h"
PINNED_CSD_H = ".work/linux-mainline/include/trace/events/csd.h"

# The exact `pr_alert` format the instrument emits.  Kept as a literal because
# finding it in a compiled kernel is the only end-to-end proof that the
# instrument is really in the artifact that would be flashed.
CSD_REPORT_FORMAT = b"csd: %s non-responsive CSD lock"


def read(rel):
    return (ROOT / rel).read_text()


def prose(rel):
    """File text with wrapping and inline markdown emphasis removed.

    Three things in these documents break a naive substring match: the line
    wrapping, a shell comment's leading `#` or a blockquote's `>`, and inline
    emphasis (`` `code` ``, `**bold**`).  Normalising all three keeps the check
    an exact substring test while making it about the words rather than the
    formatting - which is the part that carries the meaning.
    """
    text = re.sub(r"(?m)^\s*(#|>)\s?", " ", read(rel))
    text = text.replace("**", "").replace("`", "")
    # Paired single-asterisk emphasis (`*not*`), but NOT the `*` in a glob-like
    # name such as `timer:*` or `ipi:*`.
    #
    # Two earlier attempts at this were wrong in opposite directions: stripping
    # every asterisk turned `timer:*` into `timer:` and broke three unrelated
    # tests, and a word-boundary regex still ate it because `r` is a word
    # character.  The rule that works is simply: an asterisk followed by a colon
    # is part of a name, anything else paired is emphasis.
    text = re.sub(r"\*(?=\S)([^*\n]*?)\*(?!:)", r"\1", text)
    return " ".join(text.split())


def pinned(rel):
    p = ROOT / rel
    return p.read_text() if p.exists() else None


def tokens(rel):
    return read(rel).replace("\n", " ").strip().split()


class FragmentTests(unittest.TestCase):
    """The diagnostic fragment is additive, opt-in, and minimal."""

    def test_it_exists_and_is_not_in_the_default_path(self):
        self.assertTrue((ROOT / CSD_FRAGMENT).is_file())
        build = read(BUILD)
        # The default is empty; the fragment is only read when named.
        self.assertIn('diag_fragment=${GTS9_DIAG_FRAGMENT:-}', build)
        self.assertIn('GTS9_DIAG_FRAGMENT does not exist', build)

    def test_it_requests_both_symbols_the_instrument_needs(self):
        text = read(CSD_FRAGMENT)
        self.assertIn("CONFIG_CSD_LOCK_WAIT_DEBUG=y", text)
        # Without _DEFAULT the static key is off at boot and nothing is printed.
        self.assertIn("CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT=y", text)

    def test_it_leaves_the_recovery_chain_alone(self):
        """panic_on_ipistall must stay 0: round one collects, it does not panic.

        The brief is explicit, and there is a second reason: making the
        instrument panic earlier shortens the window in which the target CPU's
        state can be observed.
        """
        flat = prose(CSD_FRAGMENT)
        self.assertIn("panic_on_ipistall", flat)
        self.assertIn("DELIBERATELY LEFT AT 0", flat)
        # And the fragment must not *set* anything about the recovery chain.
        # Checked against the effective Kconfig lines only: the file quite
        # correctly *mentions* CONFIG_PANIC_TIMEOUT in a comment saying it does
        # not change it, and matching raw text would flag that documentation as
        # the violation it warns about.
        effective = [
            line.strip() for line in read(CSD_FRAGMENT).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        for line in effective:
            with self.subTest(kconfig=line):
                self.assertNotIn("SOFTLOCKUP", line)
                self.assertNotIn("PANIC_TIMEOUT", line)
                self.assertNotIn("WORKQUEUE", line)
                self.assertNotIn("HUNG_TASK", line)
        # and the only symbols it sets are the two the instrument needs
        self.assertEqual(
            sorted(effective),
            sorted(["CONFIG_CSD_LOCK_WAIT_DEBUG=y",
                    "CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT=y"]),
            "the diagnostic fragment must set exactly the two instrument symbols",
        )

    def test_it_does_not_enable_the_deferred_instruments(self):
        """One instrument at a time makes a result attributable."""
        text = read(CSD_FRAGMENT)
        for sym in ("CONFIG_IRQSOFF_TRACER=y", "CONFIG_PREEMPT_TRACER=y",
                    "CONFIG_FUNCTION_TRACER=y", "CONFIG_FUNCTION_GRAPH_TRACER=y"):
            with self.subTest(symbol=sym):
                self.assertNotIn(sym, text)

    def test_it_carries_none_of_the_forbidden_cmdline_profiles(self):
        """The diagnostic is the CSD instrument and nothing else."""
        text = read(CSD_FRAGMENT)
        for tok in ("cpuidle.off=1", "msm.skip_gpu=1", "msm.disable_acd=1",
                    "gts9_rpmh_debug=1", "deferred_probe_timeout=300"):
            with self.subTest(token=tok):
                self.assertNotIn(tok, text)


class PinnedSourceTests(unittest.TestCase):
    """Every kernel-side claim the plan makes, read out of the pinned tree."""

    def setUp(self):
        if pinned(PINNED_SMP) is None:
            self.skipTest("pinned mainline tree is not checked out")

    def test_the_instrument_is_on_the_canary_s_own_wait(self):
        """The whole argument: our canary spins in csd_lock_wait().

        `smp_call_function_many_cond()` is the function the wedge's stack names,
        and with the option on its `csd_lock_wait()` is the instrumented one.
        """
        src = pinned(PINNED_SMP)
        # The many-cond path waits per target CPU.  Sliced to the closing brace
        # rather than matched with a non-greedy dot, which cannot cross newlines
        # without re.S and would let a match run into an unrelated function.
        start = src.index("if (run_remote && wait) {")
        end = src.index("\n}", start)
        block = src[start:end]
        self.assertIn("for_each_cpu(cpu, cfd->cpumask)", block)
        self.assertIn("csd_lock_wait(csd);", block)
        # and that wait is the instrumented one under the option
        self.assertRegex(
            src,
            r"static __always_inline void csd_lock_wait\(call_single_data_t \*csd\)\s*\n\{"
            r"\s*\n\s*if \(static_branch_unlikely\(&csdlock_debug_enabled\)\) \{\s*\n"
            r"\s*__csd_lock_wait\(csd\);",
        )

    def test_it_reports_the_waiter_the_target_and_the_work(self):
        src = pinned(PINNED_SMP)
        # waiter, duration, target, function and argument in one line
        self.assertIn(
            'pr_alert("csd: %s non-responsive CSD lock (#%d) on CPU#%d, '
            'waiting %lld ns for CPU#%02d %pS(%ps).\\n"',
            src,
        )
        # and the discriminator: prior request vs this one vs nothing
        self.assertIn("handling prior %pS(%ps) request.", src)
        self.assertIn('!cpu_cur_csd ? "unresponsive" : "handling this request"', src)
        # and the target's stack, best-effort
        self.assertIn("dump_cpu_task(cpu);", src)
        # and the re-send that proves the handler was never started
        self.assertIn("Re-sending CSD lock (#%d) IPI from CPU#%02d to CPU#%02d", src)

    def test_the_timeout_is_five_seconds_and_earlier_than_rcu(self):
        """Why this fires before anything the project has used."""
        src = pinned(PINNED_SMP)
        self.assertRegex(src, r"static ulong csd_lock_timeout = 5000;")
        self.assertIn("/* CSD lock timeout in milliseconds. */", src)
        # RCU, for comparison, is 21 s on this build (RCU_CPU_STALL_TIMEOUT=21).
        self.assertIn("static int panic_on_ipistall;", src)
        self.assertIn("module_param(csd_lock_timeout, ulong, 0644);", src)
        self.assertIn("module_param(panic_on_ipistall, int, 0644);", src)
        # csdlock_debug is an __setup parameter, not a module_param - so unlike
        # the other two it is NOT writable after boot.
        self.assertIn('__setup("csdlock_debug=", csdlock_debug);', src)
        self.assertNotIn("module_param(csdlock_debug", src)

    def test_the_static_key_defaults_off_so_both_symbols_are_needed(self):
        src = pinned(PINNED_SMP)
        self.assertIn(
            "static DEFINE_STATIC_KEY_MAYBE(CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT, "
            "csdlock_debug_enabled);",
            src,
        )

    def test_the_target_cpu_comes_from_dst_which_needs_64bit(self):
        """Without CONFIG_64BIT every report would name cpu = -1."""
        src = pinned(PINNED_SMP)
        self.assertRegex(
            src,
            r"csd_type = CSD_TYPE\(csd\);\s*\n\s*if \(csd_type == CSD_TYPE_ASYNC \|\| "
            r"csd_type == CSD_TYPE_SYNC\)\s*\n\s*return csd->node\.dst;",
        )
        types = pinned(PINNED_TYPES)
        self.assertIsNotNone(types)
        # dst exists only under 64BIT
        self.assertRegex(types, r"#ifdef CONFIG_64BIT\s*\n\s*u16 src, dst;\s*\n#endif")

    def test_the_function_entry_exit_pair_brackets_the_handler(self):
        """The round-two instrument, verified now so round two need not re-derive it."""
        src = pinned(PINNED_SMP)
        self.assertRegex(
            src,
            r"csd_do_func\(smp_call_func_t func, void \*info, call_single_data_t \*csd\)"
            r"\s*\n\{\s*\n\s*trace_csd_function_entry\(func, csd\);\s*\n"
            r"\s*func\(info\);\s*\n\s*trace_csd_function_exit\(func, csd\);",
        )
        hdr = pinned(PINNED_CSD_H)
        self.assertIsNotNone(hdr)
        # Not gated on the CSD option, so it is available in a production build.
        self.assertNotIn("#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG", hdr)

    def test_a_builtin_module_param_is_namespaced_on_the_cmdline(self):
        """`smp.csd_lock_timeout=`, not `csd_lock_timeout=`.

        Verified in the compiled artifact rather than assumed: kernel/params.c
        stores the module name before a dot, and the diagnostic Image.gz contains
        the strings `smp.csd_lock_timeout` and `smp.panic_on_ipistall`.  Passing
        the bare name would be silently ignored - the same class of defect as
        msm.no_gpu=1, which shipped for two rounds.
        """
        src = pinned(PINNED_SMP)
        self.assertIn('The "module" name (KBUILD_MODNAME) is stored before a dot, the',
                      pinned(".work/linux-mainline/kernel/params.c"))
        # the params really are module_param, inside the option's ifdef
        self.assertIn("module_param(csd_lock_timeout, ulong, 0644);", src)
        self.assertIn("module_param(panic_on_ipistall, int, 0644);", src)
        # and the plan records the prefixed form
        flat = prose(PLAN)
        self.assertIn("smp.csd_lock_timeout", flat)
        self.assertIn("smp.panic_on_ipistall", flat)
        # the compiled artifact proves it, when it has been built
        img = ROOT / DIAG_OUT / "Image.gz"
        if img.exists():
            payload = BuiltArtifactTests._kernel_payload(img)
            self.assertIn(b"smp.csd_lock_timeout", payload)
            self.assertIn(b"smp.panic_on_ipistall", payload)

    def test_the_arming_gate_is_a_capability_only_the_diagnostic_has(self):
        """A positive test, because 'no output' must not read as 'not involved'.

        Both CSD module_params are inside `#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG`, so
        their sysfs files exist only in a kernel built with the option.  The file
        appearing after the flash cannot be produced by a stale image or by a
        cmdline that failed to take - which is what makes it a real gate.
        """
        src = pinned(PINNED_SMP)
        # both module_param calls live inside the option's ifdef
        idx_ifdef = src.index("#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG")
        idx_timeout = src.index("module_param(csd_lock_timeout")
        idx_endif = src.index("#else", idx_ifdef)
        self.assertLess(idx_ifdef, idx_timeout)
        self.assertLess(idx_timeout, idx_endif)

        flat = prose(PLAN)
        self.assertIn("/sys/module/smp/parameters/csd_lock_timeout", flat)
        self.assertIn("does not exist", flat)
        self.assertIn("unknown-parameter list", flat)

    def test_the_kconfig_symbols_and_their_dependencies(self):
        kc = pinned(PINNED_KCONFIG)
        self.assertIsNotNone(kc)
        start = kc.index("\nconfig CSD_LOCK_WAIT_DEBUG\n")
        rest = kc[start + 1:]
        nxt = rest.find("\nconfig ", 1)
        entry = rest[:nxt if nxt != -1 else len(rest)]
        for dep in ("depends on DEBUG_KERNEL", "depends on SMP", "depends on 64BIT"):
            with self.subTest(dep=dep):
                self.assertIn(dep, entry)
        self.assertIn("\tdefault n\n", entry)
        # and the companion, which is what actually turns it on at boot
        start2 = kc.index("\nconfig CSD_LOCK_WAIT_DEBUG_DEFAULT\n")
        rest2 = kc[start2 + 1:]
        nxt2 = rest2.find("\nconfig ", 1)
        entry2 = rest2[:nxt2 if nxt2 != -1 else len(rest2)]
        self.assertIn("depends on CSD_LOCK_WAIT_DEBUG", entry2)


class BuildWiringTests(unittest.TestCase):
    """The production/diagnostic split, enforced by the build script."""

    def setUp(self):
        self.build = read(BUILD)

    def test_the_merge_order_lets_the_diagnostic_layer_win(self):
        """merge_config.sh is last-wins, so the diagnostic must come last."""
        self.assertIn('merge_cfgs=("$stock_cfg" "$fragment")', self.build)
        self.assertIn('merge_cfgs+=("$diag_path")', self.build)
        self.assertIn('"${merge_cfgs[@]}"', self.build)

    def test_a_production_build_may_not_acquire_the_symbol(self):
        self.assertIn(
            "the production build must not enable CONFIG_CSD_LOCK_WAIT_DEBUG",
            self.build,
        )

    def test_a_diagnostic_build_must_have_both_symbols_and_64bit(self):
        self.assertIn("CSD diagnostic build is missing $sym=y", self.build)
        self.assertIn("the instrument would never run and a wedge would produce no output",
                      self.build)
        self.assertIn("CSD diagnostic build requires CONFIG_64BIT=y (csd->node.dst)",
                      self.build)

    def test_a_diagnostic_build_may_not_smuggle_in_other_instruments(self):
        self.assertIn("one instrument at a time", self.build)
        for sym in ("CONFIG_IRQSOFF_TRACER", "CONFIG_PREEMPT_TRACER",
                    "CONFIG_FUNCTION_TRACER", "CONFIG_FUNCTION_GRAPH_TRACER"):
            with self.subTest(symbol=sym):
                self.assertIn(sym, self.build)

    def test_a_diagnostic_build_must_keep_the_recovery_chain(self):
        self.assertIn("must keep CONFIG_PANIC_TIMEOUT=0", self.build)
        self.assertIn("must keep CONFIG_SOFTLOCKUP_DETECTOR=y", self.build)


class CmdlineProfileTests(unittest.TestCase):
    """The profile is the baseline plus one token, and nothing else."""

    def test_it_is_the_baseline_plus_exactly_one_token(self):
        base = tokens(BASELINE_CMDLINE)
        self.assertEqual(
            tokens(CSD_CMDLINE),
            base[:2] + ["csdlock_debug=1"] + base[2:],
            "the CSD profile must be the baseline with one inserted token",
        )

    def test_the_token_is_near_the_front(self):
        """ABL appends kilobytes of its own cmdline and dropped our last token.

        AGENT.md records this for msm.separate_gpu_kms=1; a diagnostic token is
        no different, so it must not sit at the end.
        """
        toks = tokens(CSD_CMDLINE)
        self.assertLessEqual(toks.index("csdlock_debug=1"), 4)

    def test_it_keeps_the_non_negotiables(self):
        joined = " ".join(tokens(CSD_CMDLINE))
        self.assertIn("console=tty0", joined)
        self.assertIn("softlockup_panic=1", joined)
        self.assertIn("panic=10", joined)
        self.assertEqual(joined.count("console="), 1)

    def test_it_carries_no_other_ablation_token(self):
        joined = " ".join(tokens(CSD_CMDLINE))
        for tok in ("cpuidle.off", "msm.skip_gpu", "msm.disable_acd",
                    "deferred_probe_timeout", "gts9_rpmh_debug"):
            with self.subTest(token=tok):
                self.assertNotIn(tok, joined)

    def test_it_does_not_touch_the_csd_timing_parameters(self):
        """Defaults are deliberate: 5 s timeout, panic_on_ipistall disabled."""
        joined = " ".join(tokens(CSD_CMDLINE))
        self.assertNotIn("csd_lock_timeout", joined)
        self.assertNotIn("panic_on_ipistall", joined)

    def test_the_baseline_is_untouched(self):
        self.assertEqual(
            hashlib.sha256((ROOT / BASELINE_CMDLINE).read_bytes()).hexdigest(),
            "263814b89d811bddc7e6478951fb992c7381a44f1592435da039ae0ce0fb6403",
        )


class PlanDocumentTests(unittest.TestCase):
    """The plan is pre-registered, honest, and does not re-open closed routes."""

    def test_the_four_cases_are_present_and_distinct(self):
        text = read(PLAN)
        for case in ("### Case A", "### Case B", "### Case C", "### Case D",
                     "### Case E"):
            with self.subTest(case=case):
                self.assertIn(case, text)

    def test_case_d_forbids_the_obvious_wrong_conclusion(self):
        """No output must not become 'CSD is not involved'."""
        flat = prose(PLAN)
        # prose() strips the backticks, so this is the plain form.
        self.assertIn('This does not mean "CSD is not involved."', flat)
        self.assertIn("The forbidden sentence is CSD is not involved", flat)
        # and the confirmation order that must precede any conclusion
        self.assertIn("CONFIG_CSD_LOCK_WAIT_DEBUG=y", flat)
        self.assertIn("unknown-parameter list", flat)

    def test_it_records_the_success_condition_as_information_not_absence(self):
        flat = prose(PLAN)
        self.assertIn("a real CPU wedge produces more target-CPU / CSD / IPI state",
                      flat)
        self.assertIn("This is failure forensics, not a rate experiment", flat)

    def test_it_keeps_the_three_cpu_roles_apart(self):
        flat = prose(PLAN)
        # prose() strips the inline emphasis, so these are the plain words.
        self.assertIn("the stalled CPU", flat)
        self.assertIn("the detector", flat)
        self.assertIn("the reporter", flat)
        self.assertIn("This is the canary", flat)

    def test_it_does_not_reopen_the_closed_directions(self):
        flat = prose(PLAN)
        # Table cells, with the inline emphasis stripped by prose().
        for cell in ("| GPU / GMU / ACD / AOSS | downgraded |",
                     "| RPMh rpmh_write() timeout | downgraded |",
                     "| cpufreq / EPSS / OSM L3 | orthogonal |",
                     "| PSCI / cpuidle | not necessary |"):
            with self.subTest(cell=cell):
                self.assertIn(cell, flat)
        self.assertIn("Not to be run", flat)

    def test_it_forbids_hardware_power_changes(self):
        flat = prose(PLAN)
        self.assertIn("no hardware voltage, frequency, CPR or regulator change", flat)
        self.assertIn("a direction, not authorization", flat)

    def test_it_does_not_repropose_the_present_gic_fix(self):
        flat = prose(PLAN)
        self.assertIn("0d62a49ab55c", flat)
        self.assertIn("already-present GICv3 fix", flat)

    def test_the_ftrace_design_is_constrained_now_not_later(self):
        flat = prose(PLAN)
        self.assertIn("trace_clock=global is mandatory", flat)
        self.assertIn("single-shot", flat)
        self.assertIn("contend rather than add", flat)
        self.assertIn("tp_printk is not used", flat)
        self.assertIn("Buffer sizing is measured, not guessed", flat)
        self.assertIn("timer:* is not enabled in the first pass", flat)
        self.assertIn("timer:* stays out of the first pass", flat)

    def test_it_records_that_evidence_must_be_armed_before_the_wedge(self):
        flat = prose(PLAN)
        self.assertIn("A wedged boot cannot be interrogated", flat)
        self.assertIn("/proc/interrupts", flat)


class ClosedDirectionProtectionTests(unittest.TestCase):
    """Guard the conclusions that must not be re-opened as current work.

    The failure this prevents is specific and has already happened once in this
    project: a later round re-running an ablation whose answer was already
    established (`msm.no_gpu` shipped for two rounds with a parameter the kernel
    did not have).  Here the risk is an agent reading an older document, seeing
    "PSCI idle" as the live hypothesis, and re-running the cluster ablations that
    test-227 made pointless.
    """

    NEXT_PLAN = "docs/NEXT_STALL_DEBUG_PLAN.md"

    def test_the_next_plan_names_round_34_as_the_active_branch(self):
        flat = prose(self.NEXT_PLAN)
        self.assertIn("ROUND 34 / CURRENT ACTIVE BRANCH", flat)
        self.assertIn("Active branch: IPI / CSD / IRQ delivery", flat)
        # and the history is retained rather than deleted
        self.assertIn("retained in full as history", flat)

    def test_it_states_psci_idle_is_not_necessary_with_its_evidence(self):
        flat = prose(self.NEXT_PLAN)
        self.assertIn("PSCI / cpuidle / deep idle | not necessary", flat)
        self.assertIn("usage 0 / rejected 0", flat)
        self.assertIn("test-227", flat)

    def test_it_is_not_necessary_and_not_proven_perfect(self):
        """The exact wording the brief requires.

        `cpuidle is not necessary for this wedge` is a different claim from
        `cpuidle is proven perfect`, and only the first is supported.  Recorded
        so a later round cannot cite this as evidence that cpuidle has no bugs.
        """
        flat = prose(PLAN)
        self.assertIn("not necessary", flat)
        # The plan must not claim the framework is flawless anywhere.
        for overclaim in ("cpuidle is correct", "cpuidle is proven",
                          "cpuidle has no bugs", "idle is exonerated"):
            with self.subTest(overclaim=overclaim):
                self.assertNotIn(overclaim, flat)

    def test_the_closed_directions_each_name_what_closed_them(self):
        flat = prose(self.NEXT_PLAN)
        for needle in ("test-198", "test-199", "test-227", "test-182"):
            with self.subTest(test=needle):
                self.assertIn(needle, flat)

    def test_the_ablation_profiles_are_not_listed_as_pending_work(self):
        """No document may present the cluster ablations as the next step."""
        for doc in (PLAN, self.NEXT_PLAN):
            with self.subTest(doc=doc):
                flat = prose(doc)
                for phrase in ("next item, run no-llcc-off",
                               "next: no-cluster-idle",
                               "next step: cpuidle-off"):
                    self.assertNotIn(phrase, flat.lower())


class WedgeResultTests(unittest.TestCase):
    """test-228's outcome: Case B, and the harness bug that nearly hid it."""

    RECORD = "reference/boot-tests/test-228-csd-ipi-diagnostic"
    EVID = f"{RECORD}/evidence"
    RESULT = f"{RECORD}/RESULT.md"

    def test_the_evidence_files_are_archived(self):
        for name in ("csd-reports.txt", "rcu-and-nmi.txt",
                     "wedged-boot-klog-full.txt", "pstore-console-ramoops.txt"):
            with self.subTest(artifact=name):
                self.assertTrue((ROOT / self.EVID / name).is_file(),
                                f"missing evidence: {name}")

    def test_the_quoted_csd_lines_are_in_the_archive(self):
        """Every line the result quotes must exist in the archived evidence."""
        raw = (ROOT / self.EVID / "csd-reports.txt").read_bytes().decode("utf-8", "replace")
        for needle in (
            "on CPU#4, waiting 5000000050 ns for CPU#03 do_nothing",
            "on CPU#1, waiting 5000000102 ns for CPU#07 rcu_barrier_handler",
            "csd: CSD lock (#1) unresponsive.",
            "csd: CSD lock (#2) unresponsive.",
            "Re-sending CSD lock (#2) IPI from CPU#01 to CPU#07",
            "Re-sending CSD lock (#1) IPI from CPU#04 to CPU#03",
            "Continued non-responsive CSD lock (#1)",
        ):
            with self.subTest(needle=needle[:44]):
                self.assertIn(needle, raw)

    def test_the_two_target_cpus_and_functions_are_recorded(self):
        raw = read(f"{self.EVID}/csd-reports.txt")
        self.assertIn("for CPU#03 do_nothing", raw)
        self.assertIn("for CPU#07 rcu_barrier_handler", raw)
        # and the independent confirmation
        nm = read(f"{self.EVID}/rcu-and-nmi.txt")
        self.assertIn("still haven't responded to the NMI: 3", nm)
        self.assertIn("7-...!", nm)
        self.assertIn("softirq=613/613", nm)

    def test_the_result_is_classified_as_case_b_with_its_reasoning(self):
        flat = prose(self.RESULT)
        self.assertIn("Case B", flat)
        # why 'unresponsive' rules Case A out
        self.assertIn("cpu_cur_csd", flat)
        self.assertIn("neither target was inside any IPI handler", flat)
        # and why 'handler is slow' is unavailable
        self.assertIn("cannot block", flat)

    def test_it_does_not_claim_a_cause_or_a_fix(self):
        flat = prose(self.RESULT)
        self.assertIn("Not a cause.", flat)
        self.assertIn("Not a fix, and no fix is proposed.", flat)
        self.assertIn("Not a rate.", flat)
        for overclaim in ("the root cause is", "we fixed", "this fixes the"):
            with self.subTest(overclaim=overclaim):
                self.assertNotIn(overclaim, flat)

    def test_it_records_the_onset_correction(self):
        """The first pass said 13.30 s was inside the band; it is not."""
        flat = prose(self.RESULT)
        self.assertIn("13.30 s", flat)
        self.assertIn("Correction to my own first pass", flat)
        self.assertIn("It is not", flat)

    def test_it_records_the_harness_defect_and_its_fix(self):
        """The wedge was first classified clean; that must stay on the record."""
        flat = prose(self.RESULT)
        self.assertIn("first recorded as verdict=clean", flat)
        self.assertIn("idx=$(( -extra_boots ))", flat)
        self.assertIn("extra_boots > 0", flat)
        self.assertIn("a detector that runs, reports, and is then not consulted", flat)

    def test_it_does_not_propose_supply_changes(self):
        flat = prose(self.RESULT)
        self.assertIn("not authorization to touch big-core voltage", flat)
        self.assertIn("Not something to fix by touching supplies", flat)
        self.assertIn("a correlation and a direction", flat)

    def test_the_dpu_correlation_is_recorded_as_a_correlation_only(self):
        """The crtc103 burst appears on the wedge - and on clean boots too.

        Recording it without that caveat would re-introduce exactly the mistake
        the brief forbids: attributing the failure to whichever subsystem
        complained.  The marker's counts across boots and its position RELATIVE
        to onset are both in the record, and neither reading is chosen.
        """
        flat = prose(self.RESULT)
        self.assertIn("crtc103 event 1 overflow", flat)
        # it is explicitly not promoted
        self.assertIn("not a wedge discriminator", flat)
        self.assertIn("this round separates neither", flat)
        # the clean-boot counterexample is named
        self.assertIn("test-047", flat)
        # and the ordering versus onset is stated
        self.assertIn("~9.31 s", flat)
        self.assertIn("10.101 s", flat)
        # the two readings, and the refusal to pick
        self.assertIn("the DPU is a victim", flat)
        self.assertIn("the DPU is a contributor", flat)
        # the brief's rule, applied
        self.assertIn("do not attribute the failure to the", flat)

    def test_the_correlation_evidence_file_exists(self):
        p = ROOT / self.EVID / "dpu-overflow-correlation.txt"
        self.assertTrue(p.is_file())
        text = p.read_text()
        self.assertIn("NOT a wedge discriminator", text)
        self.assertIn("victim", text)

    def test_the_restore_is_recorded_and_confirmed_in_behaviour(self):
        """Leaving a diagnostic kernel running would be unacceptable."""
        flat = prose(f"{self.RECORD}/RESTORE.md")
        self.assertIn("confirmed in behaviour", flat)
        self.assertIn("71e194a5", flat)
        self.assertIn("49ae21b3", flat)
        # the capability test, now showing the diagnostic is gone
        self.assertIn("/sys/module/smp/parameters/", flat)
        self.assertIn("empty", flat)
        # and the tmpfs lesson, which cost one attempt
        self.assertIn("tmpfs", flat)

    def test_the_plan_records_the_case_b_outcome(self):
        flat = prose(PLAN)
        self.assertIn("Case B, unambiguously", flat)
        self.assertIn("do_nothing", flat)
        self.assertIn("rcu_barrier_handler", flat)
        # and the round-2 table it produces
        self.assertIn("Round 2, made specific by this result", flat)

    def test_the_pre_run_plan_is_not_rewritten_to_match(self):
        """The pre-registered plan must keep saying what was expected first."""
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("RUN. See RESULT.md", flat)
        self.assertIn("It is not edited to match the outcome", flat)


class SshRunnerGateTests(unittest.TestCase):
    """The csd-lock arming gate in scripts/wedge-ssh.sh.

    It must be a POSITIVE capability test.  Both CSD module_params live inside
    `#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG`, so their sysfs files exist only in a
    kernel built with the option - which is what lets the plan's Case D
    distinguish "the instrument was not running" from "CSD is not involved".
    """

    RUNNER = "scripts/wedge-ssh.sh"

    def test_the_harness_knows_the_profile(self):
        text = read(self.RUNNER)
        self.assertRegex(text, r"case \"\$PROFILE\" in baseline\|cpuidle-off\|csd-lock\)")

    def test_the_gate_keys_on_the_parameter_files_existing(self):
        text = read(self.RUNNER)
        self.assertIn("/sys/module/smp/parameters/", text)
        self.assertIn("csd_lock_timeout is absent, so this kernel was NOT built with", text)
        self.assertIn("a profile failure, not a result (plan Case D)", text)
        self.assertIn("panic_on_ipistall parameter absent", text)

    def test_the_gate_requires_the_token_to_have_been_consumed(self):
        """A token nothing reads stays in the kernel's unknown-parameter list."""
        text = read(self.RUNNER)
        self.assertIn("unknown-parameter list, so no __setup handler consumed it", text)
        self.assertIn("the switch is dead", text)

    def test_the_gate_requires_the_self_recovery_chain(self):
        text = read(self.RUNNER)
        self.assertIn("the tablet would not recover by itself", text)
        self.assertIn("softlockup_panic=1 panic=10", text)

    def test_it_records_the_instrument_state_with_every_round(self):
        """A wedge with no CSD output is only interpretable if the instrument's
        liveness and timeout are on the record for that round."""
        text = read(self.RUNNER)
        for field in ("csd_timeout_ms=", "csd_panic_on_ipistall=",
                      "csd_report_lines=", "csd_first_report=",
                      "csd_targets=", "csd_disposition=",
                      "csd_resends=", "csd_unstuck="):
            with self.subTest(field=field):
                self.assertIn(field, text)

    def test_it_extracts_the_target_cpu_from_the_report(self):
        """`waiting N ns for CPU#X` is the field the whole round is for."""
        text = read(self.RUNNER)
        # the report is parsed for its target and function, and for the
        # disposition that decides Case A versus Case B
        self.assertIn("for CPU#[0-9]+ [^ ]+", text)
        self.assertIn("unresponsive|handling this request|handling prior", text)


class TestRecordTests(unittest.TestCase):
    """The test-228 hand-off: a plan with verifiable identity, not a result."""

    RECORD = "reference/boot-tests/test-228-csd-ipi-diagnostic"

    def test_the_pre_run_plan_is_marked_as_run_without_being_rewritten(self):
        """The plan was written before the flash; it must stay that way.

        It now points at RESULT.md, but its identity, write scope, arming gate and
        expected output shapes are still the pre-registered ones - that is what
        makes it evidence of what was expected rather than a description written
        after the fact.
        """
        text = read(f"{self.RECORD}/README.md")
        self.assertIn("RUN. See", text)
        self.assertIn("It is not edited to match the outcome", text)
        # the pre-registered content is still present
        self.assertIn("Arming gate", text)
        self.assertIn("Expected CSD output", text)

    def test_the_identity_artifacts_are_present(self):
        for name in ("BUNDLE_INFO", "bundle-SHA256SUMS", "kernel-SHA256SUMS",
                     "diagnostic-config.txt", "source-commit.txt",
                     "PRE-WRITE-STATE.txt"):
            with self.subTest(artifact=name):
                self.assertTrue((ROOT / self.RECORD / name).is_file(),
                                f"missing {name}")

    def test_the_recorded_hashes_are_the_built_ones(self):
        """A manifest that drifts is worse than none."""
        for pair in (("bundle-SHA256SUMS", f"{DIAG_BUNDLE}/SHA256SUMS"),
                     ("BUNDLE_INFO", f"{DIAG_BUNDLE}/BUNDLE_INFO"),
                     ("kernel-SHA256SUMS", f"{DIAG_OUT}/SHA256SUMS"),
                     ("diagnostic-config.txt", f"{DIAG_OUT}/config")):
            rec, live = pair
            if not (ROOT / live).exists():
                continue
            with self.subTest(artifact=rec):
                self.assertEqual(read(f"{self.RECORD}/{rec}"), read(live))

    def test_it_says_both_kernel_partitions_must_be_written(self):
        """The trap that produced a wrong table once already."""
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("Both kernel-carrying partitions must be written", flat)
        self.assertIn("71e194a5", flat)
        self.assertIn("f0f893c7", flat)
        # and the ones that must NOT be written
        self.assertIn("never written by this repository's tests", flat)

    def test_the_arming_gate_is_a_positive_capability_test(self):
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("ls /sys/module/smp/parameters/", flat)
        self.assertIn("production today: EMPTY", flat)
        self.assertIn("only the diagnostic kernel has", flat)
        # and it says what to do when it fails
        self.assertIn("stop", flat.lower())
        self.assertIn("Case D", flat)

    def test_it_explains_every_csd_report_shape(self):
        flat = prose(f"{self.RECORD}/README.md")
        for shape in ("handling prior", "handling this request", "unresponsive",
                      "Re-sending CSD lock"):
            with self.subTest(shape=shape):
                self.assertIn(shape, flat)
        # the re-send is the never-started discriminator.  prose() strips the
        # paired emphasis, so the plain words are what match.
        self.assertIn("the target never started the handler", flat)
        self.assertIn("from \"never started\"", flat)

    def test_it_warns_that_a_missing_target_stack_proves_nothing(self):
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("best-effort", flat)
        self.assertIn("A missing target stack is not evidence of anything", flat)

    def test_it_records_the_success_condition_as_information(self):
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn('Not "no wedge"', flat)
        self.assertIn("more target-CPU / CSD / IPI state information than", flat)

    def test_it_notes_that_image_gz_is_not_reproducible(self):
        """So a hash mismatch on a rebuild is not read as a moved source."""
        flat = prose(f"{self.RECORD}/README.md")
        self.assertIn("not reproducible", flat)
        # prose() also strips backticks.
        self.assertIn("Compare config and the DTB first", flat)

    def test_it_carries_the_rollback(self):
        flat = prose(f"{self.RECORD}/README.md")
        # prose() strips a heading's leading `#`, so this is the heading text.
        self.assertIn("10. Rollback", flat)
        self.assertIn("49ae21b3", flat)
        self.assertIn("no recovery boot", flat)


class BuiltArtifactTests(unittest.TestCase):
    """If the candidate is built, check the artifacts rather than the sources."""

    def test_the_production_config_has_the_symbol_off(self):
        cfg = ROOT / "out/kernel-gts9wifi/config"
        if not cfg.exists():
            self.skipTest("no production config built")
        text = cfg.read_text()
        self.assertIn("# CONFIG_CSD_LOCK_WAIT_DEBUG is not set", text)

    def test_the_diagnostic_config_has_both_symbols_on(self):
        cfg = ROOT / DIAG_OUT / "config"
        if not cfg.exists():
            self.skipTest("the diagnostic kernel has not been built")
        text = cfg.read_text()
        self.assertIn("CONFIG_CSD_LOCK_WAIT_DEBUG=y", text)
        self.assertIn("CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT=y", text)
        self.assertIn("CONFIG_64BIT=y", text)
        # and nothing else may have ridden along
        for sym in ("CONFIG_IRQSOFF_TRACER", "CONFIG_PREEMPT_TRACER",
                    "CONFIG_FUNCTION_TRACER"):
            with self.subTest(symbol=sym):
                self.assertNotIn(f"{sym}=y", text)

    def test_the_two_configs_differ_by_exactly_the_instrument(self):
        prod = ROOT / "out/kernel-gts9wifi/config"
        diag = ROOT / DIAG_OUT / "config"
        if not prod.exists() or not diag.exists():
            self.skipTest("both configs must be built to compare them")
        import difflib
        diff = [l for l in difflib.unified_diff(
            prod.read_text().splitlines(), diag.read_text().splitlines(), n=0)
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
        self.assertEqual(
            sorted(diff),
            sorted([
                "-# CONFIG_CSD_LOCK_WAIT_DEBUG is not set",
                "+CONFIG_CSD_LOCK_WAIT_DEBUG=y",
                "+CONFIG_CSD_LOCK_WAIT_DEBUG_DEFAULT=y",
            ]),
            "the diagnostic config must differ from production only by the "
            "instrument; anything else is a second variable",
        )

    @staticmethod
    def _kernel_payload(image_gz):
        """The raw kernel from an Image.gz.

        `out/kernel-gts9wifi/Image.gz` is a plain gzip file - the board DTB is
        appended to the *boot.img* payload, not to this.  An earlier version of
        this test reused the boot.img extraction path here and failed with
        "incorrect header check".
        """
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        return d.decompress(image_gz.read_bytes())

    def test_the_instrument_string_is_in_the_diagnostic_kernel(self):
        img = ROOT / DIAG_OUT / "Image.gz"
        if not img.exists():
            self.skipTest("the diagnostic kernel has not been built")
        self.assertIn(CSD_REPORT_FORMAT, self._kernel_payload(img))

    def test_the_instrument_is_absent_from_the_production_kernel(self):
        img = ROOT / "out/kernel-gts9wifi/Image.gz"
        if not img.exists():
            self.skipTest("no production kernel built")
        self.assertNotIn(CSD_REPORT_FORMAT, self._kernel_payload(img))

    @staticmethod
    def _bundle_payload(boot_img):
        """The decompressed kernel from a boot.img payload.

        boot.img carries `Image.gz` with the board DTB appended, so the gzip
        stream has to be stopped at its own end rather than by taking the whole
        file.
        """
        data = pathlib.Path(boot_img).read_bytes()
        start = data.find(b"\x1f\x8b\x08")
        assert start > 0, "no gzip payload"
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        return d.decompress(data[start:]) + d.flush()

    def test_the_bundle_carries_the_diagnostic_kernel(self):
        """The artifact that would be flashed, not just out/.

        The kernel is gzip-compressed inside boot.img, so the check is made
        against the decompressed payload.  This is the end-to-end proof that the
        instrument is in the thing a flash would write.
        """
        boot = ROOT / DIAG_BUNDLE / "boot.img"
        if not boot.exists():
            self.skipTest("the CSD bundle has not been built")
        raw = self._bundle_payload(boot)
        self.assertIn(CSD_REPORT_FORMAT, raw)

        # and the bundle's own manifest names the diagnostic kernel
        info = read(f"{DIAG_BUNDLE}/BUNDLE_INFO")
        diag_hash = hashlib.sha256((ROOT / DIAG_OUT / "Image.gz").read_bytes()).hexdigest()
        prod_hash = hashlib.sha256(
            (ROOT / "out/kernel-gts9wifi/Image.gz").read_bytes()).hexdigest()
        self.assertIn(f"image_gz_sha256={diag_hash}", info)
        self.assertNotIn(f"image_gz_sha256={prod_hash}", info)

    def test_the_arming_gate_string_is_in_the_diagnostic_bundle(self):
        """The gate is a capability only the diagnostic kernel has.

        `csd_lock_timeout` and `panic_on_ipistall` are module_param calls inside
        `#ifdef CONFIG_CSD_LOCK_WAIT_DEBUG`, so `/sys/module/smp/parameters/`
        gains those files only in a kernel built with the option.  The compiled
        name is namespaced (`smp.csd_lock_timeout`), and finding it in the
        bundle's own kernel is what makes the on-device gate meaningful.
        """
        boot = ROOT / DIAG_BUNDLE / "boot.img"
        if not boot.exists():
            self.skipTest("the CSD bundle has not been built")
        payload = BuiltArtifactTests._bundle_payload(boot)
        self.assertIn(b"smp.csd_lock_timeout", payload)
        self.assertIn(b"smp.panic_on_ipistall", payload)

    def test_the_gate_strings_are_absent_from_the_production_bundle(self):
        boot = ROOT / "out/boot-bundle-cpuidle-off/boot.img"
        if not boot.exists():
            self.skipTest("no production bundle to compare against")
        payload = BuiltArtifactTests._bundle_payload(boot)
        self.assertNotIn(b"smp.csd_lock_timeout", payload)
        self.assertNotIn(CSD_REPORT_FORMAT, payload)

    def test_the_bundle_cmdline_carries_the_token(self):
        vendor = ROOT / DIAG_BUNDLE / "vendor_boot.img"
        if not vendor.exists():
            self.skipTest("the CSD bundle has not been built")
        r = subprocess.run(
            ["python3", str(ROOT / ".work/tools/unpack_bootimg.py"),
             "--boot_img", str(vendor)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            self.skipTest("unpack_bootimg unavailable")
        self.assertIn("csdlock_debug=1", r.stdout)

    def test_the_bundle_changes_only_the_two_dtb_carrying_partitions(self):
        """A kernel change moves boot.img AND vendor_boot - not init_boot/dtbo/vbmeta.

        The comparison is against the *current device state* rather than against
        every bundle in out/, because out/ holds unrelated historical bundles
        built with other initramfs profiles; comparing to those would fail for
        reasons that have nothing to do with this candidate.  (An earlier version
        did exactly that and reported failures against boot-bundle-test052.)
        """
        if not (ROOT / DIAG_BUNDLE).is_dir():
            self.skipTest("the CSD bundle has not been built")

        def sha(p):
            return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

        # From reference/boot-tests/test-227-cpuidle-off-run/PRE-WRITE-STATE.txt,
        # re-read from the device after the rollback: these are what the tablet
        # will have before this candidate is written.
        device = {
            "init_boot.img": "1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0",
            "dtbo.img": "c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3",
            "vbmeta.img": "b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4",
        }
        for part, want in device.items():
            with self.subTest(partition=part):
                self.assertEqual(sha(ROOT / DIAG_BUNDLE / part), want,
                                 f"{part} must carry the device's existing image forward")

        # and the instrument-bearing ones must have changed
        info = read(f"{DIAG_BUNDLE}/BUNDLE_INFO")
        diag_hash = sha(ROOT / DIAG_OUT / "Image.gz")
        self.assertIn(f"image_gz_sha256={diag_hash}", info)


if __name__ == "__main__":
    unittest.main()
