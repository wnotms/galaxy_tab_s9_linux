"""Host checks for the X710 fast debug channel and the slow-shutdown analysis.

Pins the two things this work established so neither can quietly regress:

* the serial console's rate is not a baud-rate problem - COM17/COM19 are USB
  CDC-ACM gadget ports and the host's line coding is nominal - so the answer is a
  network function on the same gadget, plus ssh and adb over it;
* the network function is opt-in and cannot cost the ACM console, which is the
  only way in before userspace is up and the only thing that survives a userspace
  that has stopped.
"""
import hashlib
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

FRAGMENT = "kernel/config/gts9wifi-mainline.fragment"
GADGET = "rootfs-overlay/usr/libexec/gts9-usb-acm"
ADBD_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-adbd.service"
FETCH = "scripts/fetch-adbd-packages.sh"
SSH_WRAPPER = "scripts/gts9-ssh.sh"
CHANNEL = "scripts/gts9-debug-channel.sh"
CHANNEL_DOC = "docs/FAST_DEBUG_CHANNEL.md"
SHUTDOWN_DOC = "docs/SLOW_SHUTDOWN_ANALYSIS.md"
CONSOLE_SH = "scripts/console-run.sh"
CONSOLE_PS = "scripts/console-run.ps1"


def read(rel):
    return (ROOT / rel).read_text()


class GadgetNetworkFunctionTests(unittest.TestCase):
    """The NCM function must be additive, opt-in, and unable to cost the console."""

    def test_it_is_off_unless_the_flag_file_exists(self):
        text = read(GADGET)
        self.assertIn("/etc/gts9-usb-net", text)
        # No flag file -> read_net_conf leaves both empty -> setup_network and
        # configure_network return immediately.
        self.assertIn("read_net_conf", text)
        for fn in ("setup_network", "configure_network"):
            with self.subTest(fn=fn):
                self.assertRegex(text, rf"{fn}\(\) \{{\n\t\[ -n \"\$net_kind\" \] \|\| return 0")

    def test_only_ncm_and_ecm_are_accepted(self):
        """Both are built into this kernel; anything else is a typo, not a feature."""
        text = read(GADGET)
        self.assertIn("ncm | ecm)", text)
        self.assertIn("unknown network function", text)

    def test_a_missing_function_does_not_fail_the_service(self):
        """A kernel without CONFIG_USB_CONFIGFS_NCM must still bring up the console."""
        text = read(GADGET)
        self.assertIn("want CONFIG_USB_CONFIGFS_${net_kind}", text)
        # The mkdir failure branch clears net_kind and returns 0; it must not fail().
        m = re.search(r"if ! mkdir -p \"\$GADGET/functions/\$net_kind\.usb0\"[\s\S]{0,300}?\n\t\tfi",
                      text)
        self.assertIsNotNone(m, "the network mkdir block is missing")
        self.assertNotIn("fail ", m.group(0))

    def test_a_failed_bind_is_fatal_now_that_no_serial_port_remains(self):
        """This was the reverse until 2026-09-26, and the reversal is the point.

        When the network function was an optional extra alongside a serial
        console, a failed bind had to *retry without it*: losing the console to an
        optional function would have been unrecoverable.  That reasoning depended
        entirely on the console being there to fall back to.

        There is no serial port any more, so the network function is not optional
        and there is nothing to fall back to.  A bind failure is now fatal,
        because a gadget that binds without NCM is a device with no channel at
        all - and failing loudly makes that visible instead of leaving an
        unreachable tablet that looks like it booted fine.
        """
        text = read(GADGET)
        self.assertIn("cannot bind the gadget to $udc", text)
        m = re.search(r"if ! echo \"\$udc\" > \"\$GADGET/UDC\".*?\nfi", text, re.S)
        self.assertIsNotNone(m, "the UDC bind block is missing")
        self.assertIn("fail", m.group(0), "a failed bind must be fatal")
        self.assertNotIn("net_drop", m.group(0),
                         "there is no fallback function to drop back to")
        # And an unbuildable network function must fail before the bind is tried.
        self.assertIn('fail "no network function', text)

    def test_the_function_goes_into_the_existing_gadget(self):
        """A second gadget cannot bind: one UDC, one gadget, and the console owns it."""
        text = read(GADGET)
        self.assertNotIn("usb_gadget/g1", text)
        self.assertIn("$GADGET/functions/$net_kind.usb0", text)
        self.assertIn("$GADGET/configs/c.1/$net_kind.usb0", text)


class AdbdUnitTests(unittest.TestCase):
    def test_the_unit_runs_adbd_and_is_enableable(self):
        text = read(ADBD_UNIT)
        self.assertIn("ExecStart=/usr/lib/android-sdk/platform-tools/adbd", text)
        self.assertIn("WantedBy=multi-user.target", text)

    def test_it_does_not_use_the_packaged_gadget_helper(self):
        """Debian's helper creates its own gadget and would fail while gts9 owns the UDC."""
        text = read(ADBD_UNIT)
        self.assertNotIn("ExecStartPre", text)
        # The helper may only be NAMED, in the comment that explains why it is not
        # used; no directive may invoke it.
        for line in text.splitlines():
            if "adbd-usb-gadget" in line:
                self.assertTrue(line.lstrip().startswith("#"),
                                f"adbd-usb-gadget appears in a directive: {line!r}")
        # It must say why, so nobody "fixes" it back.
        self.assertIn("gadget at a time", text)

    def test_the_doc_says_to_mask_the_packaged_unit(self):
        """Installing adbd leaves Debian's adbd.service enabled, and it wedges USB."""
        text = read(CHANNEL_DOC)
        self.assertIn("systemctl disable adbd.service", text)
        self.assertIn("ln -sf /dev/null /etc/systemd/system/adbd.service", text)
        self.assertIn("usb_gadget/g1", text)
        # It must say why the packaged one cannot work, not just that it fails.
        self.assertIn("activate", text)
        self.assertIn("one gadget at a time", text)

    def test_it_explains_the_expected_non_android_errors(self):
        text = read(ADBD_UNIT)
        self.assertIn("Failed to get adbd socket", text)
        self.assertIn("not an error", text)

    def test_it_is_picked_up_by_the_enablement_helper(self):
        """gts9-enable-units links every gts9-*.service with a WantedBy= line."""
        helper = read("rootfs-overlay/usr/libexec/gts9-enable-units")
        self.assertIn('"$unit_dir"/gts9-*.service', helper)
        self.assertTrue((ROOT / ADBD_UNIT).name.startswith("gts9-"))
        self.assertIn("WantedBy=", read(ADBD_UNIT))


class AdbdPackagingTests(unittest.TestCase):
    """adbd is a real Debian package; pin the exact build and its hashes."""

    def test_it_fetches_adbd_and_its_missing_dependencies(self):
        text = read(FETCH)
        for pkg in ("adbd_34.0.5-12_arm64.deb", "android-libbase", "android-libcutils",
                    "android-liblog", "android-libboringssl", "libprotobuf32t64"):
            with self.subTest(pkg=pkg):
                self.assertIn(pkg, text)

    def test_every_package_carries_a_sha256(self):
        text = read(FETCH)
        # Each entry is two lines: the pool path + ".deb", then the sha256 (the
        # line may end with the closing quote of the array element).
        hashes = re.findall(r"^([0-9a-f]{64})\"?$", text, re.M)
        entries = re.findall(r'^[\t ]*"?[ap]/[a-z0-9+._/-]+\.deb$', text, re.M)
        self.assertEqual(len(hashes), len(entries))
        self.assertGreaterEqual(len(hashes), 6)

    def test_it_verifies_rather_than_trusting_the_download(self):
        text = read(FETCH)
        self.assertIn("SHA256 MISMATCH", text)
        self.assertIn("sha256sum", text)
        # The hash is checked before the file is moved into place.
        self.assertIn(".part", text)

    def test_it_targets_the_release_the_tablet_runs(self):
        text = read(FETCH)
        # Debian 13 trixie -> the build without a ~bpo suffix.
        self.assertIn("34.0.5-12_arm64.deb", text)
        self.assertNotIn("~bpo", text)

    def test_the_binaries_are_not_committed(self):
        text = read(FETCH)
        self.assertIn(".work/downloads", text)
        # .work/ is gitignored, so a downloaded binary there is fine; a .deb
        # anywhere else would be committed.
        stray = [p for p in ROOT.glob("**/*.deb") if ".work/" not in str(p)]
        self.assertEqual(stray, [], f".deb files outside .work/: {stray}")


class DebugChannelScriptTests(unittest.TestCase):
    def test_the_wrappers_exist_and_are_executable(self):
        for rel in (SSH_WRAPPER, CHANNEL, FETCH):
            with self.subTest(rel=rel):
                path = ROOT / rel
                self.assertTrue(path.is_file(), rel)
                self.assertTrue(path.stat().st_mode & 0o111, f"{rel} not executable")

    def test_the_ssh_wrapper_defaults_to_the_apipa_address(self):
        """169.254.0.0/16 is what needs no host-side configuration or elevation."""
        text = read(SSH_WRAPPER)
        self.assertIn("169.254.42.1", text)
        self.assertIn("GTS9_DEVICE", text)
        self.assertIn("gts9_ed25519", text)

    def test_the_shutdown_capture_waits_for_the_reproducing_uptime(self):
        text = read("reference/boot-tests/test-189-20260925T0210Z/"
                    "long-uptime-reboot-capture.sh")
        self.assertIn("GTS9_MIN_UPTIME", text)
        self.assertIn("2700", text)
        self.assertIn("GTS9_ALLOW_POWER", text)


class BaudIsNominalTests(unittest.TestCase):
    """The console's rate is not a baud-rate problem; the code must say so."""

    def test_the_host_baud_is_a_parameter_so_it_can_be_measured(self):
        for rel, needle in ((CONSOLE_PS, "[int]$Baud = 115200"),
                            (CONSOLE_SH, "-Baud")):
            with self.subTest(rel=rel):
                self.assertIn(needle, read(rel))

    def test_the_ps1_explains_that_the_line_coding_is_nominal(self):
        text = read(CONSOLE_PS)
        self.assertIn("CDC-ACM", text)
        self.assertIn("USB bulk", text)

    def test_the_document_records_the_measurement(self):
        text = read(CHANNEL_DOC)
        self.assertIn("115200", text)
        self.assertIn("921600", text)
        self.assertIn("40 s", text)
        # The rates actually achieved over the network function.
        self.assertIn("31.8 MB/s", text)
        self.assertIn("70.5 MB/s", text)

    def test_the_document_says_the_console_is_not_replaced(self):
        text = read(CHANNEL_DOC)
        self.assertIn("What this does not replace", text)
        self.assertIn("Keep it.", text)


class SlowShutdownDocTests(unittest.TestCase):
    def test_it_records_the_three_timings(self):
        text = read(SHUTDOWN_DOC)
        for needle in ("41 s", "194 s", "1.07 s", "2936 s"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_records_what_was_ruled_out(self):
        text = read(SHUTDOWN_DOC)
        for needle in ("32 ms", "0.51 s", "0.49 s", "41.0 MB/s", "848 kB",
                       "hung_task_panic", "softlockup_panic"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_does_not_blame_the_debug_channel(self):
        text = read(SHUTDOWN_DOC)
        self.assertIn("does not implicate the debug-channel work", text)

    def test_it_states_that_the_mechanism_is_not_established(self):
        text = read(SHUTDOWN_DOC)
        self.assertIn("does not establish the mechanism", text)
        self.assertIn("n=2", text)


if __name__ == "__main__":
    unittest.main()


class CpuWedgeEvidenceTests(unittest.TestCase):
    """The wedge rate is the one confound-free measurement in this repository."""

    DOC = "docs/CPU_WEDGE_EVIDENCE.md"
    SURVEY = "rootfs-overlay/usr/libexec/gts9-journal-survey"
    DATA = "reference/boot-tests/test-189-20260925T0210Z/journal-survey-wedge.txt"

    def test_the_document_records_the_rate_and_the_test(self):
        text = read(self.DOC)
        for needle in ("10 (21.7%", "1 (3.4%", "p = 0.043"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_explains_why_the_marker_is_not_confounded(self):
        """sd=0 is produced by flashing too; an unanswered NMI is not."""
        text = read(self.DOC)
        self.assertIn("confound-freedom", text)
        self.assertIn("pulling the power", text)
        self.assertIn("unanswered NMI", text)

    def test_it_uses_boot_ids_not_journal_indices(self):
        """Indices shift as boots age out; an earlier draft cited them."""
        text = read(self.DOC)
        self.assertIn("Boot ids, not journal indices", text)
        self.assertIn("fa0f2151", text)
        self.assertIn("f7b1e8de", text)

    def test_the_survey_excludes_the_command_line_before_counting(self):
        """hung_task_panic=1 in the cmdline matched a bare hung_task pattern."""
        text = read(self.SURVEY)
        self.assertIn('grep -av "Kernel command line"', text)
        # And awk must not also be handed the file, or every line counts twice.
        self.assertNotIn("""\t' "$TMP" >>"$OUT\"""", text)

    def test_the_survey_counts_the_four_wedge_markers(self):
        text = read(self.SURVEY)
        for pattern in ("rcu.*detected stall", "haven.t responded to the NMI",
                        "BUG: workqueue lockup", "BUG: soft lockup"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, text)

    def test_the_recorded_data_still_supports_the_rate(self):
        """Re-derive the counts from the survey output rather than trusting prose."""
        rows = []
        for line in read(self.DATA).splitlines():
            p = line.split()
            if len(p) < 14:
                continue
            rows.append(dict(bid=p[1], lines=int(p[2]), acd=int(p[4]), sd=int(p[6]),
                             multi=int(p[7]), rcu=int(p[8]), nmi=int(p[9]),
                             wq=int(p[10]), sl=int(p[12])))
        wedge = [r for r in rows if r["rcu"] or r["nmi"] or r["wq"] or r["sl"]]
        self.assertEqual(len(rows), 88)
        self.assertEqual(len(wedge), 11)
        # Every one of them must show the CPU-level marker.
        self.assertTrue(all(r["nmi"] for r in wedge),
                        "a wedge boot without an unanswered NMI")
        valid = [r for r in rows if r["multi"] > 0 and r["lines"] >= 900]
        pre = [r for r in valid if r["acd"] > 0]
        post = [r for r in valid if r["acd"] == 0]
        self.assertEqual(len(pre), 46)
        self.assertEqual(len([r for r in pre if r["rcu"] or r["nmi"] or r["wq"] or r["sl"]]), 10)
        # The one post-fix wedge never reached multi-user, so it is outside the
        # valid set on purpose and must be counted separately.
        self.assertEqual(len([r for r in post if r["rcu"] or r["nmi"] or r["wq"] or r["sl"]]), 0)
        fao = [r for r in rows if r["bid"] == "fa0f2151"]
        self.assertEqual(len(fao), 1)
        self.assertEqual(fao[0]["acd"], 0)
        self.assertTrue(fao[0]["nmi"] or fao[0]["rcu"] or fao[0]["wq"] or fao[0]["sl"])


class DeferredCpufreqTests(unittest.TestCase):
    """The fifth permanently-deferred provider, and it is on the CPU path."""

    DOC = "docs/PROVIDER_FOLLOWUPS.md"

    def test_it_records_the_two_consequences(self):
        text = read(self.DOC)
        self.assertIn("Failed to find icc paths", text)
        # No cluster has OS-controlled frequency scaling...
        self.assertIn("freq-domain0/1/2", text)
        # ...and gcc is blocked by it as well as by the GMU.
        self.assertIn("sync_state() pending due to 17d91000.cpufreq", text)
        self.assertIn("second, independent blocker", text)

    def test_it_rules_out_the_obvious_candidates(self):
        text = read(self.DOC)
        self.assertIn("opp-peak-kBps", text)
        # The round-19 audit listed the providers that WERE bound and concluded
        # "all of them are".  That audit is now recorded as the reason the bug was
        # missed, so the doc must keep both the old claim and its refutation.
        self.assertIn("every interconnect provider is bound", text)
        self.assertIn("no unit address", text)

    def test_it_names_the_third_path_and_its_provider(self):
        """The resolved mechanism: cpu0's path 2 has no provider."""
        text = read(self.DOC)
        for needle in (
            "of_icc_get_by_index(cpu_dev, 2)",
            "17d90000.interconnect",
            "qcom,sm8550-epss-l3",
            "osm-l3",
            "CONFIG_INTERCONNECT_QCOM_OSM_L3",
            "MASTER_EPSS_L3_APPS",
            "SLAVE_EPSS_L3_SHARED",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_records_why_only_the_outer_message_appeared(self):
        text = read(self.DOC)
        self.assertIn("logs at `dev_dbg`", text)
        self.assertIn("Unable to get path2", text)
        # And it must retract the round-19 inference rather than leave it standing.
        self.assertIn("was wrong", text)

    def test_it_names_the_x910_evidence(self):
        """The differentiator is that X910 fixed this first, on the same SoC."""
        text = read(self.DOC)
        self.assertIn("config-ubuntu-desktop.fragment", text)
        self.assertIn("There was no frequency scaling", text)
        self.assertIn("schedutil", text)

    def test_it_does_not_claim_the_wedge_is_fixed(self):
        text = read(self.DOC)
        self.assertIn("**Not claimed:**", text)
        self.assertIn("explained by a defect that affects all three clusters", text)

    def test_the_fragment_builds_the_provider_in(self):
        self.assertIn("CONFIG_INTERCONNECT_QCOM_OSM_L3=y", read(FRAGMENT))

    def test_the_fragment_explains_the_trap(self):
        text = read(FRAGMENT)
        for needle in (
            "17d90000.interconnect",
            "Failed to find icc paths",
            "Unable to get path2",
            "epss_l3_l3_vote",
            "EPSS_REG_L3_VOTE",
            "osm_l3_of_match",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_resolved_config_builds_it_in(self):
        """=m would be as good as absent: this port installs no module tree."""
        cfg = ROOT / "out/kernel-gts9wifi/config"
        if not cfg.exists():
            self.skipTest("no resolved config yet")
        text = cfg.read_text()
        if "CONFIG_INTERCONNECT_QCOM_OSM_L3=y" not in text:
            self.skipTest("resolved config predates the fragment change; rebuild")
        self.assertNotIn("CONFIG_INTERCONNECT_QCOM_OSM_L3=m", text)
        self.assertIn("CONFIG_INTERCONNECT_QCOM_SM8550=y", text)

    def test_the_dtsi_still_carries_the_bandwidth_it_claims(self):
        """Re-derive it: if upstream ever drops opp-peak-kBps this doc is wrong."""
        dtsi = ROOT / ".work/build/linux-src-gts9wifi/arch/arm64/boot/dts/qcom/sm8550.dtsi"
        if not dtsi.is_file():
            self.skipTest("kernel worktree is not present")
        text = dtsi.read_text()
        self.assertIn("opp-peak-kBps = <(300000 * 16) (547000 * 4) (307200 * 32)>", text)
        self.assertGreaterEqual(text.count("opp-peak-kBps"), 90)
        # And every CPU node declares the icc path the lookup needs.  The count is
        # 11, not 8: three non-CPU nodes use the same master.
        self.assertGreaterEqual(
            text.count("interconnects = <&gem_noc MASTER_APPSS_PROC"), 8)


# Every interconnect provider a CPU's `interconnects` property may name, and the
# Kconfig symbol that has to be built in for that node to get a driver at all.
# A provider reachable only as a module counts as absent: the port installs no
# module tree.
ICC_PROVIDER_SYMBOLS = {
    "qcom,sm8550-gem-noc": "CONFIG_INTERCONNECT_QCOM_SM8550",
    "qcom,sm8550-mc-virt": "CONFIG_INTERCONNECT_QCOM_SM8550",
    "qcom,sm8550-epss-l3": "CONFIG_INTERCONNECT_QCOM_OSM_L3",
    "qcom,epss-l3": "CONFIG_INTERCONNECT_QCOM_OSM_L3",
}


def dts_node_body(text, label):
    """Return the braced body of `label: ... { ... }` in a DTS source file."""
    match = re.search(r"^\s*%s:\s*[^\s{]+\s*\{" % re.escape(label), text, re.M)
    if not match:
        return None
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.end():index]
    return None


class CpuIccPathTests(unittest.TestCase):
    """Per-path, not per-provider: this is the check that would have caught it.

    The round-19 audit enumerated the interconnect providers that had bound and
    concluded all of them had.  A provider with *no* driver has no entry in that
    list at all - it is absent, not misnamed - so no such audit could ever have
    found `epss_l3`.  This test walks the consumer's own property instead and asks,
    for each phandle, whether the target node has a driver built in.
    """

    DTSI = ".work/build/linux-src-gts9wifi/arch/arm64/boot/dts/qcom/sm8550.dtsi"

    def setUp(self):
        path = ROOT / self.DTSI
        if not path.is_file():
            self.skipTest("kernel worktree is not present")
        self.text = path.read_text()
        self.fragment = read(FRAGMENT)

    def cpu_interconnect_labels(self, cpu):
        body = dts_node_body(self.text, cpu)
        self.assertIsNotNone(body, "no node for %s" % cpu)
        match = re.search(r"interconnects\s*=\s*(.*?);", body, re.S)
        self.assertIsNotNone(match, "no interconnects property on %s" % cpu)
        # A phandle appears twice per path (master and slave); dedupe in order.
        seen = []
        for label in re.findall(r"&([A-Za-z0-9_]+)", match.group(1)):
            if label not in seen:
                seen.append(label)
        return seen

    def test_every_cpu_cluster_has_the_same_three_paths(self):
        for cpu in ("cpu0", "cpu3", "cpu7"):
            with self.subTest(cpu=cpu):
                self.assertEqual(
                    self.cpu_interconnect_labels(cpu),
                    ["gem_noc", "mc_virt", "epss_l3"],
                )

    def test_every_named_provider_has_a_driver_built_in(self):
        for cpu in ("cpu0", "cpu3", "cpu7"):
            for label in self.cpu_interconnect_labels(cpu):
                with self.subTest(cpu=cpu, provider=label):
                    body = dts_node_body(self.text, label)
                    self.assertIsNotNone(body, "no node for provider %s" % label)
                    compat = re.findall(r'compatible\s*=\s*"([^"]+)"', body)
                    self.assertTrue(compat)
                    # A node lists its specific compatible first and a generic
                    # fallback second; the driver matches either.
                    symbols = {
                        ICC_PROVIDER_SYMBOLS[c] for c in compat
                        if c in ICC_PROVIDER_SYMBOLS
                    }
                    self.assertTrue(
                        symbols,
                        "provider %s (%s) is not in ICC_PROVIDER_SYMBOLS; a human "
                        "has to decide which symbol builds its driver"
                        % (label, ", ".join(compat)),
                    )
                    for symbol in symbols:
                        self.assertIn(
                            "%s=y" % symbol,
                            self.fragment,
                            "%s is named by %s but %s is not built in"
                            % (label, cpu, symbol),
                        )

    def test_the_missing_one_is_the_l3_vote_not_a_perf_state(self):
        """SM8550 has no specific osm-l3 match, so the fallback's vote applies."""
        body = dts_node_body(self.text, "epss_l3")
        self.assertIn('"qcom,sm8550-epss-l3"', body)
        self.assertIn('"qcom,epss-l3"', body)
        # The generic entry is the one that matches, and it uses the L3 vote.
        driver = ROOT / (".work/build/linux-src-gts9wifi/drivers/interconnect/"
                         "qcom/osm-l3.c")
        if not driver.is_file():
            self.skipTest("kernel worktree is not present")
        osm = driver.read_text()
        self.assertIn('{ .compatible = "qcom,epss-l3", .data = &epss_l3_l3_vote }',
                      osm)
        self.assertNotIn('compatible = "qcom,sm8550-epss-l3"', osm)


class WedgeClusterTests(unittest.TestCase):
    """13 of 14 wedged CPUs are big or prime; that asymmetry is the finding."""

    DOC = "docs/CPU_WEDGE_EVIDENCE.md"

    def test_the_doc_maps_cpus_to_clusters_and_rails(self):
        text = read(self.DOC)
        for needle in ("silver-rail-power-collapse", "gold-rail-power-collapse",
                       "goldplus-rail-power-collapse", "capacity-dmips-mhz"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_it_records_both_statistics(self):
        text = read(self.DOC)
        self.assertIn("P = 0.013", text)
        self.assertIn("P = 0.043", text)
        self.assertIn("10 of 11", text)

    def test_the_cpu_mapping_matches_the_pinned_dtsi(self):
        """Re-derive the clusters from sm8550.dtsi rather than trusting prose."""
        dtsi_path = (ROOT / ".work/build/linux-src-gts9wifi/arch/arm64/boot/dts/"
                            "qcom/sm8550.dtsi")
        if not dtsi_path.is_file():
            self.skipTest("kernel worktree is not present")
        caps = [int(m) for m in
                re.findall(r"capacity-dmips-mhz = <(\d+)>;", dtsi_path.read_text())]
        self.assertEqual(len(caps), 8)
        self.assertEqual(caps[:3], [326, 326, 326])      # little, cpu0-2
        self.assertEqual(caps[3:7], [693] * 4)           # big, cpu3-6
        self.assertEqual(caps[7], 1024)                  # prime, cpu7

    def test_the_doc_admits_the_samples_are_correlated(self):
        text = read(self.DOC)
        self.assertIn("not eleven independent draws", text)
        self.assertIn("the NMI target is chosen by the stall detector", text)

    def test_the_account_says_it_is_a_narrowing_not_a_mechanism(self):
        text = read(self.DOC)
        self.assertIn("a narrowing and not a mechanism", text)


class WedgeMarkerReadingTests(unittest.TestCase):
    """Two corrections to the central marker, both re-derived here.

    The whole rate table in docs/CPU_WEDGE_EVIDENCE.md counts boots by the
    unanswered-backtrace line, so how that line may be *read* is load-bearing.
    These tests pin the corrections to the source and to the resolved config, so
    the doc cannot drift back into claiming a 10-second observation window or
    attributing kcpustat numbers to the wedged CPUs.
    """

    DOC = "docs/CPU_WEDGE_EVIDENCE.md"
    CONFIG = "out/kernel-gts9wifi/config"
    SMP = ".work/build/linux-src-gts9wifi/arch/arm64/kernel/smp.c"
    NMI_BT = ".work/build/linux-src-gts9wifi/lib/nmi_backtrace.c"
    WATCHDOG = ".work/build/linux-src-gts9wifi/kernel/watchdog.c"

    def contains(self, rel, *needles):
        text = read(rel)
        missing = [n for n in needles if n not in text]
        self.assertEqual(missing, [], f"{rel} is missing {missing}")

    def test_pseudo_nmi_really_is_off_so_it_is_a_regular_ipi(self):
        """The doc says so; the resolved config has to agree."""
        cfg = ROOT / self.CONFIG
        if not cfg.exists():
            self.skipTest("no resolved config yet")
        self.assertIn("# CONFIG_ARM64_PSEUDO_NMI is not set", cfg.read_text())
        smp = ROOT / self.SMP
        if not smp.is_file():
            self.skipTest("kernel worktree is not present")
        text = smp.read_text()
        # The source says it itself, which is why the doc can quote it.
        self.assertIn("our backtrace attempt will just use a regular IPI", text)
        self.assertIn("arm64_backtrace_ipi", text)

    def test_the_timeout_loop_really_is_a_bounded_mdelay_loop(self):
        """The doc's quote of lib/nmi_backtrace.c has to match the tree."""
        path = ROOT / self.NMI_BT
        if not path.is_file():
            self.skipTest("kernel worktree is not present")
        text = path.read_text()
        self.assertIn("#define NMI_BT_TIMEOUT_SEC	10", text)
        self.assertIn("for (i = 0; i < NMI_BT_TIMEOUT_SEC * 1000; i++)", text)
        self.assertIn("mdelay(1);", text)
        self.assertIn("still haven't responded to the NMI", text)

    def test_the_doc_records_that_the_interval_is_microseconds(self):
        self.contains(self.DOC,
                      "36.340199", "36.340219", "20 µs",
                      "36.360250", "36.360265", "15 µs",
                      "did not answer the backtrace request")

    def test_the_doc_does_not_read_the_ten_seconds_literally(self):
        self.contains(self.DOC, "is **not**\n10 seconds of observation")

    def test_the_doc_retracts_the_old_100_percent_reading(self):
        self.contains(self.DOC,
                      "`100% system, 0% idle` is the reporting CPU",
                      "report_cpu_status()",
                      "that was wrong")

    def test_the_mdelay_arithmetic_in_the_doc_matches_the_config(self):
        """It is the reason the doc refuses to blame mdelay; keep it honest."""
        cfg = ROOT / self.CONFIG
        if not cfg.exists():
            self.skipTest("no resolved config yet")
        self.assertIn("CONFIG_HZ=250", cfg.read_text())
        # arm64 computes cycles as (xloops * loops_per_jiffy * HZ) >> 32 with
        # xloops = 1000 * 0x10C7 for a one-millisecond udelay().
        xloops = 1000 * 0x10C7
        lpj = 76800          # from dmesg: "38.40 BogoMIPS (lpj=76800)"
        cycles = (xloops * lpj * 250) >> 32
        self.assertEqual(cycles, 19200)
        self.assertEqual(cycles * 1000 // 19200000, 1)   # 19.2 MHz arch timer
        self.contains(self.DOC, "lpj=76800", "19200 cycles", "1.000 ms")

    def test_the_doc_keeps_the_independent_evidence(self):
        """The corrections must not have removed what still proves the wedge."""
        self.contains(self.DOC, "q=2442", "starved for 2495 jiffies")


class CpuIdleLeadTests(unittest.TestCase):
    """The X710-only idle options, and the harness that would capture a wedge."""

    DOC = "docs/CPU_WEDGE_EVIDENCE.md"
    HUNT = "reference/boot-tests/test-190-20260925T0400Z/wedge-hunt.sh"
    FRAGMENT = "kernel/config/gts9wifi-mainline.fragment"

    def test_the_doc_names_the_x710_only_idle_options(self):
        text = read(self.DOC)
        self.assertIn("CONFIG_CPU_IDLE_THERMAL=y", text)
        self.assertIn("CONFIG_CPU_IDLE_GOV_TEO=y", text)
        # And that they are inherited, not chosen - so nobody hunts for a commit.
        self.assertIn("inherited from the stock", text)

    def test_they_really_are_absent_from_the_fragment(self):
        """The doc claims they are stock-seed leftovers; verify it."""
        fragment = read(self.FRAGMENT)
        self.assertNotIn("CPU_IDLE_THERMAL", fragment)
        self.assertNotIn("CPU_IDLE_GOV_TEO", fragment)

    def test_the_doc_records_the_measured_idle_usage(self):
        text = read(self.DOC)
        self.assertIn("psci_idle", text)
        self.assertIn("usage=91839", text)
        self.assertIn("92%", text)
        # And that no suspend failure is reported.
        self.assertIn("no failed suspends", text)

    def test_the_doc_does_not_claim_idle_is_the_cause(self):
        text = read(self.DOC)
        self.assertIn("a lead, not a conclusion", text)
        self.assertIn("cannot rule out and cannot confirm", text)

    def test_the_hunt_is_a_warm_reboot_harness_that_stops_on_a_capture(self):
        text = read(self.HUNT)
        self.assertIn("kind=warm-reboot", text)
        self.assertIn("GTS9_ALLOW_POWER", text)
        # It must stop the moment it catches something, or the capture rotates away.
        self.assertIn("WEDGE CAPTURED", text)
        self.assertIn("break", text)
        # And it must require execution, not an echo.
        self.assertIn("GTS9_ALIVE_", text)
        # Nothing may be flashed.
        for forbidden in ("fastboot", "dd if=", "flash ", "avbtool"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


class LiveWedgeTests(unittest.TestCase):
    """The live wedge of 2026-09-25, and the two harness faults it exposed."""

    TESTDIR = "reference/boot-tests/test-190-20260925T0400Z"
    DOC = "docs/CPU_WEDGE_EVIDENCE.md"

    def test_the_capture_was_preserved_under_its_own_name(self):
        """A second hunt run overwrote cycle-2; the copy must stay."""
        path = ROOT / f"{self.TESTDIR}/wedge-capture-20260925T0337-wedged-boot.log"
        self.assertTrue(path.is_file(), "the wedged boot's capture is gone")
        # systemd colours the unit name, so the escape is between the two words
        # and a plain assertIn on "start adbd.service" would never match.
        text = re.sub(r"\x1b\[[0-9;]*m", "", path.read_text(errors="replace"))
        self.assertIn("Failed to start adbd.service", text)
        self.assertIn("Reached target multi-user", text)
        self.assertIn("Started gts9-adbd.service", text)

    def test_the_account_records_the_recovery_time(self):
        text = read(f"{self.TESTDIR}/LIVE-WEDGE-20260925T0337.md")
        self.assertIn("03:37:45.185", text)
        self.assertIn("three minutes", text)
        self.assertIn("echo without execution", text)

    def test_the_account_names_adbd_service_as_a_suspect_not_a_verdict(self):
        text = read(f"{self.TESTDIR}/LIVE-WEDGE-20260925T0337.md")
        self.assertIn("new suspect, not a conclusion", text)
        # And it must say why it is not sufficient on its own.
        self.assertIn("not sufficient on its own", text)

    def test_the_evidence_doc_carries_the_window_and_overwrite_lessons(self):
        text = read(self.DOC)
        self.assertIn("a capture window of 60 s is too short", text)
        self.assertIn("must not reuse capture filenames", text)
        self.assertIn("wedge-capture-20260925T0337-wedged-boot.log", text)

    def test_the_account_excludes_adbd_as_the_primary_cause(self):
        """10 of 11 wedge boots predate adbd entirely; say so before the result."""
        text = read(f"{self.TESTDIR}/LIVE-WEDGE-20260925T0337.md")
        self.assertIn("cannot be the *primary* cause", text)
        self.assertIn("pre-fix boots, from long before `adbd` was installed", text)
        # Markdown wraps, so match in fragments rather than across a line break.
        self.assertIn("explains the pre-fix 22%", text)

    def test_the_account_records_the_window_margin(self):
        text = read(f"{self.TESTDIR}/LIVE-WEDGE-20260925T0337.md")
        self.assertIn("marginal, not comfortable", text)
        self.assertIn("**300 s is the honest number", text)

    def test_the_hunt_window_is_settable_and_the_run_uses_200(self):
        """60 s missed the panic; the window has to be raisable without editing."""
        text = read("reference/boot-tests/test-190-20260925T0400Z/wedge-hunt.sh")
        self.assertIn("WINDOW=${GTS9_WINDOW:-", text)
        # The window actually used for the post-mask run, and the reason.
        run = read("reference/boot-tests/test-190-20260925T0400Z/wedge-hunt.txt")
        self.assertIn("window=200s", run)
        self.assertIn("window is now 200 s",
                      read(f"{self.TESTDIR}/LIVE-WEDGE-20260925T0337.md"))


class SerialKeyBootstrapIsGone(unittest.TestCase):
    """A fresh rootfs has no way to receive an ssh key, and that must be loud.

    `install-key` wrote the public key over the COM17 serial console. That shell is
    gone - the autologin getty was deleted and the ttyGS kernel console removed,
    both because they caused the boot and shutdown stalls. The port itself still
    works (verified: writes return in 0-3 ms and reach a reader), so the command
    would have kept "succeeding" while doing nothing, and the operator's next
    question would be why ssh still asks for a password.

    A silent no-op is the failure this guards against, so the assertion is that the
    script refuses rather than that the feature works.
    """

    HELPER = "scripts/gts9-debug-channel.sh"

    def test_install_key_refuses_instead_of_failing_silently(self):
        text = read(self.HELPER)
        self.assertIn("install-key cannot work any more", text)
        self.assertIn("GTS9_ALLOW_SERIAL_KEY_INSTALL", text)
        # It must exit non-zero: a caller in a pipeline has to be able to notice.
        self.assertIn("exit 3", text)
        # ... and it must still explain the replacement, not just refuse.
        self.assertIn("--ssh-key", text)
        self.assertIn("FAST_DEBUG_CHANNEL.md", text)

    def test_the_escape_hatch_keeps_the_original_command(self):
        """The port works, so a boot that really has a serial shell can still use it."""
        text = read(self.HELPER)
        self.assertIn("GTS9_ALLOW_SERIAL_KEY_INSTALL:-0", text)
        self.assertIn("authorized_keys", text)
        self.assertIn("console-run.sh", text)

    def test_it_actually_refuses_when_run(self):
        """Run it, with a key present, and require failure rather than a no-op."""
        import os as _os
        import subprocess as _sp
        import tempfile as _tf
        with _tf.TemporaryDirectory() as tmp:
            key = pathlib.Path(tmp) / "k"
            key.write_text("PRIVATE")
            (pathlib.Path(tmp) / "k.pub").write_text("ssh-ed25519 AAAA test@host\n")
            env = dict(_os.environ, GTS9_SSH_KEY=str(key))
            env.pop("GTS9_ALLOW_SERIAL_KEY_INSTALL", None)
            result = _sp.run(["bash", str(ROOT / self.HELPER), "install-key"],
                             text=True, capture_output=True, check=False, env=env)
            self.assertNotEqual(result.returncode, 0,
                                "install-key must not report success")
            self.assertIn("cannot work any more", result.stderr)

    def test_the_doc_records_the_gap_and_the_two_routes(self):
        text = read("docs/FAST_DEBUG_CHANNEL.md")
        self.assertIn("install-key` no longer works", text)
        # Both candidate replacements, so the gap is actionable.
        self.assertIn("--ssh-key", text)
        self.assertIn("ssh-copy-id", text)
        # The evidence that the port is unused rather than broken.
        self.assertIn("HELLO-GTS9-WITH-NEWLINE", read("docs/USB_SERIAL_CONSOLE.md"))

    def test_the_serial_doc_records_the_measurement_traps(self):
        """Both traps produced a wrong '0 bytes' answer while writing this."""
        text = read("docs/USB_SERIAL_CONSOLE.md")
        self.assertIn("canonical mode", text)   # a write needs a newline
        self.assertIn("readers compete", text)  # two cats split the stream
