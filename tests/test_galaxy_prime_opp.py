"""The Galaxy prime CPU operating point, and the boundaries of that one change.

SM8550-AC ("Snapdragon 8 Gen 2 for Galaxy") exposes a 3.36 GHz CPU7 entry in the
hardware frequency LUT that ABL programs. Generic `sm8550.dtsi` stops at
3.1872 GHz, so the board DT has to describe the extra point or
`qcom-cpufreq-hw` has nothing to attach that LUT entry to. Without it every boot
prints:

    cpu cpu7: Voltage update failed freq=3360000
    cpu cpu7: failed to update OPP for freq=3360000

The mechanism, from `drivers/cpufreq/qcom-cpufreq-hw.c`:
`qcom_cpufreq_hw_read_lut()` walks the hardware LUT and calls
`qcom_cpufreq_update_opp()` per distinct frequency; with interconnect scaling in
use that becomes `dev_pm_opp_adjust_voltage()`, which looks the frequency up and
returns `-ENOENT` when no OPP matches. The `dev_err` in that function is the
message above. So this is a DT-description-versus-hardware-LUT mismatch, not a
supply failure.

The tests below are deliberately as narrow as the change. Half of them exist to
stop this single-variable fix from being widened later: no voltage, no
turbo-mode, no other OPP table touched, no cpuidle or cmdline policy dragged in.

This suite does NOT claim the change fixes the CPU wedge. That is a separate
question with its own evidence in docs/CPU_WEDGE_EVIDENCE.md, and it needs a
pre-registered A/B rather than an inference from this node existing.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DTS = 'kernel/dts/sm8550-samsung-gts9wifi.dts'
GENERIC = '.work/build/linux-src-gts9wifi/arch/arm64/boot/dts/qcom/sm8550.dtsi'

# The exact top-end votes the generic prime OPPs already use. The new node must
# reuse them, because this port has no independent 3.36 GHz bandwidth
# measurement and the S8 Gen 2 for Galaxy prime rail is the same LLCC/DDR/L3
# client at the top of its range.
TOP_END_VOTES = '<(933000 * 16) (3686000 * 4) (1689600 * 32)>'


def read(path):
    return (ROOT / path).read_text()


def opp_table(dts_text, label):
    """The body of `label: opp-table-... { ... }` from a DTS, or '' if absent."""
    m = re.search(re.escape(label) + r':\s*opp-table-[a-z0-9]+\s*\{(.*?)\n\t\};',
                  dts_text, re.S)
    return m.group(1) if m else ''


def board_cpu7_override(dts_text):
    """The `&cpu7_opp_table { ... };` override body from the board DTS."""
    m = re.search(r'&cpu7_opp_table\s*\{(.*?)\n\};', dts_text, re.S)
    return m.group(1) if m else ''


class TheBoardDescribesTheGalaxyPrimeOpp(unittest.TestCase):

    def test_the_board_overrides_the_cpu7_opp_table(self):
        self.assertTrue(board_cpu7_override(read(DTS)),
                        'the board DTS must override &cpu7_opp_table')

    def test_exactly_one_3360000000_node(self):
        body = board_cpu7_override(read(DTS))
        self.assertEqual(len(re.findall(r'opp-3360000000\s*\{', body)), 1)
        # ... and the whole board file must not declare it twice.
        self.assertEqual(len(re.findall(r'opp-3360000000\s*\{', read(DTS))), 1)

    def test_opp_hz_is_exactly_3360000000(self):
        body = board_cpu7_override(read(DTS))
        self.assertIn('opp-hz = /bits/ 64 <3360000000>;', body)

    def test_it_reuses_the_generic_top_end_votes(self):
        """Same LLCC/DDR/L3 votes as the highest generic prime OPP.

        Checked against the pinned source rather than a copy of the numbers, so
        a kernel update that changes the generic table fails here instead of
        silently leaving this node voting for bandwidth nobody else asks for.
        """
        body = board_cpu7_override(read(DTS))
        self.assertIn('opp-peak-kBps = ' + TOP_END_VOTES + ';', body)
        generic = read(GENERIC)
        table = opp_table(generic, 'cpu7_opp_table')
        self.assertTrue(table, f'cannot find cpu7_opp_table in {GENERIC}')
        # The highest generic OPP must use those exact votes.
        last = re.findall(r'opp-\d+\s*\{[^}]*\}', table, re.S)[-1]
        self.assertIn('opp-peak-kBps = ' + TOP_END_VOTES + ';', last,
                      'the generic top-end prime OPP no longer uses these votes')

    def test_the_generic_table_still_stops_at_3187200000(self):
        """The premise of the whole change: upstream has no 3.36 GHz node."""
        generic = read(GENERIC)
        table = opp_table(generic, 'cpu7_opp_table')
        self.assertIn('opp-3187200000', table)
        self.assertNotIn('opp-3360000000', table)
        self.assertNotIn('3360000000', generic)


class TheNewNodeCarriesOnlyWhatIsEvidenced(unittest.TestCase):

    def test_no_opp_microvolt(self):
        """Voltage comes from the hardware LUT, which writes it into the OPP.

        A voltage here would be a rail value this port has not measured, and
        `dev_pm_opp_adjust_voltage()` overwrites it at probe anyway.
        """
        body = board_cpu7_override(read(DTS))
        self.assertNotIn('opp-microvolt', body)
        # The generic table does not declare one either, so adding it here would
        # also make this OPP inconsistent with its neighbours.
        self.assertNotIn('opp-microvolt', opp_table(read(GENERIC), 'cpu7_opp_table'))

    def test_no_turbo_mode(self):
        """Boost classification comes from the LUT's core-count field.

        `qcom_cpufreq_hw_read_lut()` sets CPUFREQ_BOOST_FREQ for the last
        LUT_TURBO_IND entry itself, and the driver never reads `turbo-mode`. A
        board-level `turbo-mode` would therefore be an unreferenced claim.
        """
        body = board_cpu7_override(read(DTS))
        self.assertNotIn('turbo-mode', body)

    def test_the_node_describes_only_hz_and_bandwidth(self):
        """Only opp-hz and opp-peak-kBps: nothing else is evidenced.

        The value of opp-peak-kBps is a separate line from its name in this
        style, so the property set is read from the source line that opens each
        property rather than by trying to match name and value together.
        """
        body = board_cpu7_override(read(DTS))
        node = re.search(r'opp-3360000000\s*\{(.*?)\};', body, re.S).group(1)
        # The class must allow uppercase: `opp-peak-kBps` has a capital B, and a
        # lowercase-only pattern silently sees just opp-hz.
        props = set(re.findall(r'^\s*([a-zA-Z][a-zA-Z0-9,-]*)\s*=', node, re.M))
        self.assertEqual(props, {'opp-hz', 'opp-peak-kBps'},
                         f'unexpected property in the new OPP node: {props}')

    def test_the_comment_names_the_lut_not_a_wedge(self):
        """The comment must state the observed cause, and claim nothing more."""
        text = read(DTS)
        # The evidence: the driver message this removes.
        self.assertIn('Voltage update failed freq=3360000', text)
        # The mechanism, named precisely.
        self.assertIn('qcom_cpufreq_hw_read_lut', text)
        self.assertIn('dev_pm_opp_adjust_voltage', text)
        # And no claim about the stall.
        for overclaim in ('wedge', 'RCU stall', 'rcu stall', 'softlockup',
                          'voltage instability', 'stabilize'):
            with self.subTest(overclaim=overclaim):
                self.assertNotIn(overclaim, text)


class TheOldPrimeOppSurvives(unittest.TestCase):

    def test_3187200000_is_still_described(self):
        """The new node is an addition, not a replacement."""
        self.assertIn('opp-3187200000', opp_table(read(GENERIC), 'cpu7_opp_table'))

    def test_the_board_does_not_remove_or_modify_it(self):
        body = board_cpu7_override(read(DTS))
        self.assertNotIn('opp-3187200000', body)
        self.assertNotIn('/delete-node/', body)
        self.assertNotIn('opp-hz', re.sub(r'opp-3360000000\s*\{.*?\};', '', body, flags=re.S))


class TheChangeDidNotWiden(unittest.TestCase):
    """Boundaries of a single-variable change, asserted rather than promised."""

    def test_no_other_opp_table_is_touched(self):
        text = read(DTS)
        overrides = re.findall(r'^&(\w*opp_table\w*)\s*\{', text, re.M)
        self.assertEqual(overrides, ['cpu7_opp_table'],
                         'only the prime CPU OPP table may be overridden')

    def test_no_gpu_opp_table_change(self):
        text = read(DTS)
        self.assertNotIn('&gpu_opp_table', text)
        self.assertNotIn('719000000', text)

    def test_no_cpuidle_change(self):
        """cpuidle states are the kernel's; this change does not touch them."""
        text = read(DTS)
        for forbidden in ('idle-state', 'cpu-idle-states', 'cpuidle',
                          'domain-idle-states'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_no_regulator_or_voltage_content_was_added(self):
        """This change adds no rail: no regulator node, no microvolt."""
        body = board_cpu7_override(read(DTS))
        for forbidden in ('regulator-', 'microvolt', '-supply'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, body)

    def test_the_production_cmdline_gained_nothing(self):
        """The production profile must still be exactly what it was.

        This is the profile that boots Debian, and the whole point of a
        single-variable change is that it does not move. Its tokens are asserted
        as a set so an addition fails here rather than in a boot.
        """
        tokens = read('boot/cmdline.example.txt').split()
        self.assertEqual(sorted(tokens), [
            'clk_ignore_unused',
            'console=tty0',
            'consoleblank=0',
            'fbcon=font:TER16x32',
            'firmware_class.path=/lib/firmware',
            'gts9_display_recover=1',
            'gts9_rootfs=/dev/mmcblk1p1',
            'gts9_sec_log=0x880200000,0x200000',
            'loglevel=4',
            'msm.separate_gpu_kms=1',
            'nokaslr',
            'panic=0',
            'pd_ignore_unused',
            'regulator_ignore_unused',
            'systemd.ssh_auto=no',
        ])

    def test_no_stall_recovery_token_appears_in_production(self):
        """panic=0 is deliberate (89a6601) and stays; nothing new joins it.

        The seven DEBUG profiles legitimately carry softlockup_panic=1 and
        panic=10 - that is their purpose, and they carried them before this
        change. What must not happen is one of them leaking into the profile
        that boots Debian, which is the decision another round has to make.
        """
        text = read('boot/cmdline.example.txt')
        for token in ('softlockup_panic', 'panic=10', 'cpuidle.off',
                      'panic_on_rcu_stall', 'panic_on_stall_time',
                      'panic_on_oops'):
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_the_debug_cmdlines_keep_their_own_watchdog_tokens(self):
        """The debug profiles are unchanged, and this change did not touch them.

        Their watchdog tokens predate the OPP work (they arrive with f33f338).
        Asserted so a later reader does not read their presence as fallout from
        this node, and so a future edit cannot quietly remove them either.
        """
        for name in ('cmdline.stall-ab-baseline.example.txt',
                     'cmdline.watchdog-debug.example.txt'):
            with self.subTest(cmdline=name):
                text = read('boot/' + name)
                self.assertIn('softlockup_panic=1', text)
                self.assertIn('panic=10', text)


if __name__ == '__main__':
    unittest.main()
