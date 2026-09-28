"""Offline Test250 attribution, parser and stop-rule tests; never contact a device."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import production_stability_evidence as ev  # noqa: E402
import production_reboot_stability as runner  # noqa: E402

A, B, C = (digit * 32 for digit in "abc")


def boots(*ids):
    return "IDX  BOOT ID FIRST ENTRY LAST ENTRY\n" + "".join(
        f"{index + 1 - len(ids)} {value} date date\n" for index, value in enumerate(ids))


def journal(*messages, boot=B, priority=6):
    start = json.dumps({"_BOOT_ID": boot, "_SOURCE_BOOTTIME_TIMESTAMP": "0",
                        "PRIORITY": "6", "MESSAGE": "Linux version test-production"}) + "\n"
    return start + "".join(json.dumps({"_BOOT_ID": boot,
                               "_SOURCE_BOOTTIME_TIMESTAMP": str(index * 1000),
                               "PRIORITY": str(priority), "MESSAGE": message}) + "\n"
                   for index, message in enumerate(messages, 1))


def clean_gate(**overrides):
    values = dict(attribution="attributed", journal=ev.inspect_journal(journal("booted"), B),
                  identity_ok=True, dcc_absent=True, uptime=150.01,
                  adb_ok=True, ssh_ok=True, ncm_ok=True,
                  ncm_initial_failure=False, failed_units=[])
    values.update(overrides)
    return ev.round_verdict(**values)


class AttributionTests(unittest.TestCase):
    def test_exactly_one_changed_boot(self):
        self.assertEqual(ev.attribute(A, B, boots(A), boots(A, B)), "attributed")

    def test_unchanged_boot_id_is_not_a_reboot(self):
        self.assertEqual(ev.attribute(A, A, boots(A), boots(A)), "boot_id_unchanged")
        self.assertEqual(clean_gate(attribution="boot_id_unchanged"), "suspect")

    def test_extra_or_missing_boot_is_not_attributed(self):
        self.assertEqual(ev.attribute(A, C, boots(A), boots(A, B, C)),
                         "unexpected_boot_or_history")
        self.assertEqual(ev.attribute(A, C, boots(A), boots(B, C)), "previous_boot_missing")
        self.assertEqual(clean_gate(attribution="unexpected_boot_or_history"), "suspect")

    def test_malformed_or_duplicate_history_rejected(self):
        for text in ("", "journalctl failed", boots(A, A)):
            with self.subTest(text=text), self.assertRaises(ValueError):
                ev.boot_list(text)


class JournalTests(unittest.TestCase):
    def test_truncated_journal_without_startup_record_rejected(self):
        partial = journal("later boot message").split("\n", 1)[1]
        with self.assertRaises(ValueError):
            ev.inspect_journal(partial, B)

    def test_missing_empty_wrong_boot_and_missing_source_time_rejected(self):
        for raw in (None, "", journal("booted", boot=C),
                    json.dumps({"_BOOT_ID": B, "MESSAGE": "booted"}) + "\n"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ev.inspect_journal(raw, B)

    def test_real_test249_accepted_journal_replays_without_new_fault(self):
        base = runner.baseline()
        raw = (runner.BASE / "final-acceptance/kernel-json.txt").read_text()
        result = ev.inspect_journal(raw, "38a30c1d-68b2-4e10-8bb4-42dce8bb0385",
                                    base["known_priority3"])
        self.assertEqual(result["rows"], 1091)
        self.assertEqual(result["fault_counts"], {})
        self.assertEqual(result["suspects"], [])

    def test_cpu_lockup_rcu_csd_panic_hung_task_are_failures(self):
        cases = {
            "watchdog: BUG: soft lockup - CPU#4 stuck for 22s!": "soft_lockup",
            "rcu: INFO: rcu_preempt detected stalls on CPUs/tasks": "rcu_stall",
            "csd: Detected non-responsive CSD lock": "csd_nonresponse",
            "Kernel panic - not syncing: watchdog": "panic",
            "INFO: task systemd:1 blocked for more than 120 seconds": "hung_task",
            "BUG: workqueue lockup - pool cpus=0": "workqueue_lockup",
            "CPU 5 is non-responsive": "cpu_nonresponse",
        }
        for message, category in cases.items():
            with self.subTest(message=message):
                result = ev.inspect_journal(journal(message), B)
                self.assertIn(category, result["fault_counts"])
                self.assertEqual(clean_gate(journal=result), "failure_observed")

    def test_known_aux_and_regulator_warnings_are_not_cpu_failures(self):
        result = ev.inspect_journal(journal(
            "auxiliary aux_bridge.aux_bridge.0: deferred probe pending: "
            "aux_bridge.aux_bridge: failed to acquire drm_bridge",
            "regulator: Not disabling unused regulators", priority=3), B)
        self.assertEqual(result["fault_counts"], {})
        self.assertEqual(result["suspects"], [])
        self.assertEqual(result["known_warning_count"], 2)

    def test_new_kernel_error_or_unexpected_trace_is_suspect(self):
        for message in ("arm-smmu: Unhandled context fault: fsr=0x404",
                        "Call trace:", "[drm] *ERROR* new failure",
                        ev.AUX_WARNING + " changed error"):
            with self.subTest(message=message):
                result = ev.inspect_journal(journal(message, priority=3), B)
                self.assertTrue(result["suspects"])
                self.assertEqual(clean_gate(journal=result), "suspect")

    def test_old_priority_three_warning_is_only_known_by_exact_message(self):
        old = "OF: reserved mem: pre-existing warning"
        self.assertEqual(ev.inspect_journal(journal(old, priority=3), B, {old})["suspects"], [])
        self.assertTrue(ev.inspect_journal(journal(old + " changed", priority=3), B, {old})["suspects"])


class GateTests(unittest.TestCase):
    def test_read_only_state_gate_rejects_reappearing_hvc0(self):
        answers = {
            "boot-id": A, "boot-id-confirm": A,
            "uname": f"Linux gts9 {runner.RELEASE} #1 SMP",
            "cmdline": "console=tty0 panic=0 regulator_ignore_unused",
            "uptime": "321.5 200.0", "kernel-notes": "1" * 64 + "  /sys/kernel/notes",
            "config-sha256": "2" * 64 + "  -",
            "embedded-config": "", "dcc-state": "dev=absent\nsysfs=absent\ngetty=inactive\nsymbol=",
            "production-profile": "0\n0\n0\n0\n0\n",
            "systemd-failed": "", "usb-state": "configured\nusb0 UP\n",
        }
        base = {"notes_sha256": "1" * 64, "config_sha256": "2" * 64}
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock(folder=Path(temp))
            rec.adb.side_effect = lambda name, _script, _timeout=15: (answers[name], 0)
            self.assertTrue(runner.production_state(rec, base)["identity_ok"])
            answers["dcc-state"] = "dev=present\nsysfs=present\ngetty=active\n"
            with self.assertRaises(runner.CaptureError):
                runner.production_state(rec, base)

    def test_clean_round(self):
        self.assertEqual(clean_gate(), "clean")
        self.assertTrue(ev.may_continue("clean"))

    def test_ssh_or_adb_unavailable_stops(self):
        for change in (dict(ssh_ok=False), dict(adb_ok=False), dict(ncm_ok=False)):
            with self.subTest(change=change):
                self.assertEqual(clean_gate(**change), "suspect")

    def test_ncm_transient_stops_even_if_later_recovered(self):
        self.assertEqual(clean_gate(ncm_initial_failure=True), "usb-transient")
        self.assertFalse(ev.may_continue("usb-transient"))

    def test_hvc_dcc_restored_or_identity_changed_stops(self):
        self.assertEqual(clean_gate(dcc_absent=False), "suspect")
        self.assertEqual(clean_gate(identity_ok=False), "suspect")

    def test_failed_unit_and_short_window_stop(self):
        self.assertEqual(clean_gate(failed_units=["new-broken.service"]), "suspect")
        self.assertEqual(clean_gate(uptime=149.9), "suspect")

    def test_present_windows_code43_stops_before_ncm_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock()
            rec.folder = Path(temp)
            rec.host_adb.return_value = (f"{runner.SERIAL} device\n", 0)
            rec.ps.side_effect = [
                ("Status : Error\nProblemCode : 43\nInstanceId : USB\\VID_0000&PID_0002", 0),
                ("Kernel-PnP event 411", 0),
            ]
            result = runner.transport(rec, B)
            self.assertTrue(result["code43"])
            self.assertEqual(rec.ps.call_count, 2)
            rec.ssh.assert_not_called()

    def test_code43_is_problem_code_not_digits_in_instance_id(self):
        self.assertFalse(runner.has_code43("Status : OK\nProblemCode : 0\nInstanceId : USB\\VID_0525\\abc43"))
        self.assertTrue(runner.has_code43("Status : Error\nProblemCode : 43\nInstanceId : USB\\VID_0525"))

    def test_live_fault_stops_before_window_completes(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock(folder=Path(temp))
            rec.adb.return_value = (B + "\n20.0 30.0\n", 0)
            proc = mock.Mock()
            proc.poll.return_value = None
            proc.wait.return_value = -15
            def start(_argv, stdout, stderr):
                stdout.write(journal("Kernel panic - not syncing: test").encode())
                stdout.flush()
                return proc
            with mock.patch.object(runner.subprocess, "Popen", side_effect=start), \
                 mock.patch.object(runner.time, "sleep") as sleep:
                with self.assertRaises(runner.KernelEvidenceError) as caught:
                    runner.observe_window(rec, B, 18.0, {"known_priority3": set()})
                self.assertIn("panic", caught.exception.scan["fault_counts"])
                sleep.assert_not_called()
                proc.terminate.assert_called_once()
                progress = json.loads((rec.folder / "observation-progress.json").read_text())
                self.assertEqual(progress["last_successful_poll_uptime_seconds"], 20.0)
                meta = json.loads((rec.folder / "kernel-follow.command.json").read_text())
                self.assertFalse(meta["registered_window_completed"])
                self.assertFalse(meta["host_stopped_at_window_end"])

    def test_shutdown_fault_stops_before_new_boot_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rec = mock.Mock(folder=root / "round-01")
            def make_recorder(_folder):
                rec.folder.mkdir()
                return rec
            rec.adb.side_effect = lambda name, *args, **kwargs: (
                boots(A) if name == "boots-before" else boots(A, B), 0)
            with mock.patch.object(runner, "P", root), \
                 mock.patch.object(runner, "Recorder", side_effect=make_recorder), \
                 mock.patch.object(runner, "production_state", return_value={"boot_id": A}), \
                 mock.patch.object(runner, "transport", return_value={
                     "adb_ok": True, "ssh_ok": True, "ncm_banner_ok": True,
                     "code43": False, "ncm_initial_failure": False}), \
                 mock.patch.object(runner, "journal", side_effect=[
                     journal("normal", boot=A), journal("BUG: shutdown failure", boot=A)]), \
                 mock.patch.object(runner, "wait_new_boot", return_value=(B, 20)), \
                 mock.patch.object(runner, "observe_window") as observe, \
                 mock.patch.object(runner, "collect_failure"):
                result = runner.round_run(1, {"known_priority3": set()}, A)
                self.assertEqual(result["verdict"], "failure_observed")
                self.assertIn("oops_bug", result["kernel_fault_counts"])
                observe.assert_not_called()

    def test_runner_does_not_start_round_two_after_first_non_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            test_root = Path(temp)
            (test_root / "preflight").mkdir()
            base = {"test249_manifest_sha256": "abc", "config_sha256": "x", "notes_sha256": "y"}
            (test_root / "preflight/summary.json").write_text(json.dumps(
                {"verdict": "accepted_production", "test249_manifest_sha256": "abc", "boot_id": A}))
            first = {"round": 1, "verdict": "usb-transient", "before_boot_id": A,
                     "after_boot_id": B, "observation_seconds": 150,
                     "kernel_fault_counts": {}, "transport": {"adb_ok": True}}
            with mock.patch.object(runner, "P", test_root), \
                 mock.patch.object(runner, "ROOT", test_root), \
                 mock.patch.object(runner, "assert_registration_pushed"), \
                 mock.patch.object(runner, "baseline", return_value=base), \
                 mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(returncode=0)), \
                 mock.patch.object(runner.subprocess, "check_output", return_value=b""), \
                 mock.patch.object(runner, "round_run", return_value=first) as execute, \
                 mock.patch.object(runner, "final_acceptance") as final:
                with self.assertRaises(runner.CaptureError):
                    runner.run()
                execute.assert_called_once()
                final.assert_not_called()
                saved = json.loads((test_root / "summary.json").read_text())
                self.assertEqual(saved["first_non_clean_round"], 1)


class StartupVariantTests(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-02"):
            self.base = runner.baseline()

    def scan(self, rows):
        raw = "".join(json.dumps(row) + "\n" for row in rows)
        return runner.inspect(raw, rows[0]["_BOOT_ID"], self.base)

    def rows(self):
        p = runner.TEST250_ROOT / "preflight/kernel-journal-json.txt"
        return [json.loads(line) for line in p.read_text().splitlines()]

    def test_both_accepted_production_captures_and_stopped_preflight_replay(self):
        for path in (runner.BASE / "production-twrp-continued/kernel-follow.jsonl",
                     runner.BASE / "final-acceptance/kernel-json.txt",
                     runner.TEST250_ROOT / "preflight/kernel-journal-json.txt"):
            with self.subTest(path=path):
                scan = self.scan([json.loads(line) for line in path.read_text().splitlines()])
                self.assertEqual(scan["fault_counts"], {})
                self.assertEqual(scan["suspects"], [])
                self.assertEqual(scan["startup_variant_counts"]["smmu_context_fault"], 10)

    def test_unknown_smmu_syndrome_sid_bank_and_address_remain_suspect(self):
        original = self.rows()
        idx = next(i for i, row in enumerate(original) if ev.SMMU_CONTEXT.fullmatch(row["MESSAGE"]))
        for old, new in (("fsr=0x402", "fsr=0x404"), ("fsynr=0x620021", "fsynr=0x640021"),
                         ("cbfrsynra=0x1c00", "cbfrsynra=0x1c01"), ("cb=9", "cb=10"),
                         ("iova=0xb8000100", "iova=0xb8200000")):
            with self.subTest(change=new):
                rows = [dict(row) for row in original]
                rows[idx]["MESSAGE"] = rows[idx]["MESSAGE"].replace(old, new)
                self.assertTrue(self.scan(rows)["suspects"])

    def test_late_smmu_fault_not_whitelisted_even_if_exact_accepted_text(self):
        rows = self.rows()
        idx = next(i for i, row in enumerate(rows) if row["MESSAGE"] == ev.SMMU_FSR)
        rows[idx]["_SOURCE_BOOTTIME_TIMESTAMP"] = "200001"
        self.assertTrue(self.scan(rows)["suspects"])

    def test_more_than_ten_early_context_faults_stop(self):
        rows = self.rows()
        row = next(row for row in rows if ev.SMMU_CONTEXT.fullmatch(row["MESSAGE"]))
        rows.append(dict(row))
        scan = self.scan(rows)
        self.assertEqual(scan["startup_variant_counts"]["smmu_context_fault"], 11)
        self.assertTrue(scan["suspects"])

    def test_new_boot_register_warning_shape_or_time_stops(self):
        for replacement in ("0000000080000001",):
            rows = self.rows()
            row = next(row for row in rows if ev.BOOT_REGISTER_WARNING.fullmatch(row["MESSAGE"]))
            row["MESSAGE"] = row["MESSAGE"].replace("0000000080000000", replacement)
            self.assertTrue(self.scan(rows)["suspects"])
        rows = self.rows()
        next(row for row in rows if ev.BOOT_REGISTER_WARNING.fullmatch(row["MESSAGE"]))[
            "_SOURCE_BOOTTIME_TIMESTAMP"] = "1"
        self.assertTrue(self.scan(rows)["suspects"])

    def test_new_cpu_fault_and_usb_transient_still_stop(self):
        rows = self.rows()
        rows.append({"_BOOT_ID": rows[0]["_BOOT_ID"], "_SOURCE_BOOTTIME_TIMESTAMP": "30000000",
                     "PRIORITY": "3", "MESSAGE": "Kernel panic - not syncing: watchdog"})
        self.assertIn("panic", self.scan(rows)["fault_counts"])
        self.assertEqual(clean_gate(ncm_initial_failure=True), "usb-transient")

    def test_original_attempt_retains_conservative_exact_gate(self):
        scan = runner.inspect((runner.TEST250_ROOT / "preflight/kernel-journal-json.txt").read_text(),
                              self.rows()[0]["_BOOT_ID"], runner.baseline())
        self.assertEqual(len(scan["suspects"]), 21)


class ProductionRegionAndNcmTests(unittest.TestCase):
    def test_verified_dtb_region_recognizes_old_suspect_addresses_without_new_kernel(self):
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-03"):
            base = runner.baseline()
        self.assertEqual(base["startup_iova_range"], (0xb8000000, 0xbab00000))
        raw = (runner.TEST250_ROOT / "attempt-02/round-01/kernel-journal-json.txt").read_text()
        boot = json.loads(raw.splitlines()[0])["_BOOT_ID"]
        scan = runner.inspect(raw, boot, base)
        self.assertEqual(scan["suspects"], [])
        self.assertEqual(scan["fault_counts"], {})
        self.assertEqual(scan["startup_variant_counts"]["smmu_context_fault"], 10)

    def test_real_region_boundaries_and_late_faults_still_stop(self):
        raw = (runner.TEST250_ROOT / "attempt-02/round-01/kernel-journal-json.txt").read_text()
        rows = [json.loads(line) for line in raw.splitlines()]
        index = next(i for i, row in enumerate(rows) if ev.SMMU_CONTEXT.fullmatch(row["MESSAGE"]))
        base = {"known_priority3": runner.baseline()["known_priority3"],
                "accepted_startup_variants": True, "startup_iova_range": (0xb8000000, 0xbab00000)}
        for address in ("0xb7ffffff", "0xbab00000"):
            trial = [dict(row) for row in rows]
            trial[index]["MESSAGE"] = trial[index]["MESSAGE"].replace("0xb82a6d00", address)
            scan = runner.inspect("\n".join(json.dumps(row) for row in trial), rows[0]["_BOOT_ID"], base)
            self.assertTrue(scan["suspects"])
        rows[index]["_SOURCE_BOOTTIME_TIMESTAMP"] = "200001"
        self.assertTrue(runner.inspect("\n".join(json.dumps(row) for row in rows),
                                       rows[0]["_BOOT_ID"], base)["suspects"])

    def bound_row(self):
        return {"ok": True, "interface_index": 11, "socket_interface": 11,
                "source_ipv4": "169.254.254.208", "local_endpoint": "169.254.254.208:1358",
                "remote_endpoint": "169.254.42.1:22", "banner": "SSH-2.0-OpenSSH_test\r\n"}

    def test_bound_banner_rejects_wrong_interface_source_target_and_empty_banner(self):
        good = self.bound_row()
        self.assertTrue(runner.bound_banner_ok(json.dumps(good)))
        for changes in ({"socket_interface": 12}, {"source_ipv4": "127.0.0.1"},
                        {"local_endpoint": "172.22.1.2:1234"},
                        {"remote_endpoint": "169.254.42.2:22"}, {"banner": ""}, {"ok": False}):
            self.assertFalse(runner.bound_banner_ok(json.dumps({**good, **changes})))

    def test_bound_probe_retains_transient_verdict_after_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock(folder=Path(temp))
            rec.host_adb.return_value = (runner.SERIAL + " device\n", 0)
            rec.ps.side_effect = [("ProblemCode : 0", 0),
                (json.dumps({"ok": False, "error": "TCP connect timeout"}), 1),
                (json.dumps(self.bound_row()), 0)]
            rec.ssh.return_value = (B, 0)
            with mock.patch.object(runner.time, "sleep"):
                link = runner.transport(rec, B, source_bound=True)
            self.assertTrue(link["ncm_source_bound"])
            self.assertTrue(link["ncm_initial_failure"])
            self.assertTrue(link["ssh_ok"])
            self.assertEqual(clean_gate(ncm_initial_failure=link["ncm_initial_failure"]), "usb-transient")

    def test_corrupt_accepted_dtb_identity_stops_before_using_bounds(self):
        real_check = runner.checked_file
        def changed(path, manifest):
            raw = real_check(path, manifest)
            if path.name == "build-check.json":
                data = json.loads(raw)
                data["artifacts"]["out/kernel-no-dcc-production/sm8550-samsung-gts9wifi.dtb"]["sha256"] = "0" * 64
                return json.dumps(data).encode()
            return raw
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-03"), \
             mock.patch.object(runner, "checked_file", side_effect=changed):
            with self.assertRaises(ValueError):
                runner.baseline()


class QcaBaudrateClassificationTests(unittest.TestCase):
    def rows(self):
        messages = ((0, "Linux version test-production", 6),
                    (6_000_000, ev.QCA_SETUP, 6),
                    (8_000_000, ev.QCA_BAUDRATE_EVENT, 3),
                    (8_800_000, ev.QCA_READY, 6))
        return [{"_BOOT_ID": B, "_SOURCE_BOOTTIME_TIMESTAMP": str(t),
                 "PRIORITY": str(priority), "MESSAGE": message}
                for t, message, priority in messages]

    def scan(self, rows=None, **kwargs):
        raw = "\n".join(json.dumps(row) for row in (self.rows() if rows is None else rows))
        return ev.inspect_journal(raw, B, accepted_qca_baudrate=True, **kwargs)

    def health(self):
        return (f"boot_id={B}\nuptime=151.3 300\nbluetooth=active\naddress=active\n"
                "controllers=hci0 \ncontroller:\nController 38:8A:06:59:04:E7 (public)\n"
                "\tPowered: yes\n\tPowerState: on\n")

    def test_exact_early_recovered_warning_is_counted(self):
        scan = self.scan()
        self.assertEqual(scan["suspects"], [])
        self.assertEqual(scan["known_warning_count"], 1)
        self.assertEqual(scan["qca_baudrate_warning"]["state"], "accepted")
        self.assertEqual(scan["qca_baudrate_warning"]["recovery_seconds"], 0.8)
        self.assertEqual(clean_gate(journal=scan), "clean")

    def test_default_and_old_attempts_keep_event_suspect(self):
        raw = "\n".join(json.dumps(row) for row in self.rows())
        for path in (runner.TEST250_ROOT, runner.TEST250_ROOT / "attempt-02",
                     runner.TEST250_ROOT / "attempt-03"):
            with self.subTest(path=path), mock.patch.object(runner, "P", path):
                base = runner.baseline()
                self.assertFalse(base["accepted_qca_baudrate"])
                self.assertTrue(runner.inspect(raw, B, base)["suspects"])

    def test_late_zero_time_and_repeated_event_stop(self):
        for time_us in (0, 20_000_001):
            rows = self.rows()
            rows[2]["_SOURCE_BOOTTIME_TIMESTAMP"] = str(time_us)
            rows[3]["_SOURCE_BOOTTIME_TIMESTAMP"] = str(time_us + 800_000)
            self.assertTrue(self.scan(rows)["suspects"])
        rows = self.rows()
        rows.append(dict(rows[2]))
        scan = self.scan(rows)
        self.assertEqual(scan["qca_baudrate_warning"]["event_count"], 2)
        self.assertEqual(clean_gate(journal=scan), "suspect")
        self.assertFalse(ev.may_continue(clean_gate(journal=scan)))

    def test_exact_twenty_second_boundary_is_allowed(self):
        rows = self.rows()
        rows[2]["_SOURCE_BOOTTIME_TIMESTAMP"] = "20000000"
        rows[3]["_SOURCE_BOOTTIME_TIMESTAMP"] = "25000000"
        self.assertEqual(self.scan(rows)["qca_baudrate_warning"]["state"], "accepted")

    def test_other_opcode_controller_and_priority_remain_suspect(self):
        for message in (ev.QCA_BAUDRATE_EVENT.replace("fc48", "fc49"),
                        ev.QCA_BAUDRATE_EVENT.replace("hci0", "hci1")):
            rows = self.rows()
            rows[2]["MESSAGE"] = message
            self.assertTrue(self.scan(rows)["suspects"])
        for priority in (2, 4, 6):
            rows = self.rows()
            rows[2]["PRIORITY"] = str(priority)
            self.assertTrue(self.scan(rows)["suspects"])

    def test_missing_wrong_soc_or_restarted_setup_stops(self):
        for message in ("unrelated", ev.QCA_SETUP.replace("wcn6855", "wcn7850")):
            rows = self.rows()
            rows[1]["MESSAGE"] = message
            self.assertTrue(self.scan(rows)["suspects"])
        rows = self.rows()
        rows.insert(3, {**rows[1], "_SOURCE_BOOTTIME_TIMESTAMP": "8100000"})
        self.assertTrue(self.scan(rows)["suspects"])

    def test_missing_late_or_prior_completion_stops(self):
        self.assertTrue(self.scan(self.rows()[:-1])["suspects"])
        for time_us in (7_000_000, 13_000_001):
            rows = self.rows()
            rows[3]["_SOURCE_BOOTTIME_TIMESTAMP"] = str(time_us)
            self.assertTrue(self.scan(rows)["suspects"])

    def test_live_pending_has_deadline_and_cannot_be_clean(self):
        rows = self.rows()[:-1]
        scan = self.scan(rows, observed_uptime=10)
        self.assertEqual(scan["suspects"], [])
        self.assertEqual(scan["qca_baudrate_warning"]["state"], "pending")
        self.assertEqual(clean_gate(journal=scan), "suspect")
        self.assertTrue(self.scan(rows, observed_uptime=13.000001)["suspects"])

    def test_cpu_fault_stops_even_while_qca_pending(self):
        rows = self.rows()[:-1]
        rows.append({**rows[0], "_SOURCE_BOOTTIME_TIMESTAMP": "10000000",
                     "MESSAGE": "Kernel panic - not syncing: test"})
        scan = self.scan(rows, observed_uptime=10)
        self.assertIn("panic", scan["fault_counts"])
        self.assertEqual(clean_gate(journal=scan), "failure_observed")

    def test_live_runner_stops_when_setup_deadline_expires(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock(folder=Path(temp))
            rec.adb.return_value = (B + "\n14.0 30.0\n", 0)
            proc = mock.Mock()
            proc.poll.return_value = None
            proc.wait.return_value = -15
            raw = "\n".join(json.dumps(row) for row in self.rows()[:-1]) + "\n"
            def start(_argv, stdout, stderr):
                stdout.write(raw.encode())
                stdout.flush()
                return proc
            with mock.patch.object(runner.subprocess, "Popen", side_effect=start), \
                 mock.patch.object(runner.time, "sleep") as sleep:
                with self.assertRaises(runner.KernelEvidenceError) as caught:
                    runner.observe_window(rec, B, 10.0,
                        {"known_priority3": set(), "accepted_qca_baudrate": True})
                self.assertEqual(caught.exception.scan["qca_baudrate_warning"]["state"], "suspect")
                sleep.assert_not_called()
                proc.terminate.assert_called_once()

    def test_registration_cannot_silently_increase_event_limit(self):
        read_text = Path.read_text
        def altered(path, *args, **kwargs):
            raw = read_text(path, *args, **kwargs)
            if path == runner.TEST250_ROOT / "attempt-04/policy.json":
                value = json.loads(raw)
                value["maximum_count"] = 2
                return json.dumps(value)
            return raw
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-04"), \
             mock.patch.object(Path, "read_text", altered):
            with self.assertRaises(ValueError):
                runner.baseline()

    def test_pushed_registration_compares_each_file_to_its_own_blob(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            test_root = root / "reference/test250"
            registration = test_root / "attempt-04"
            registration.mkdir(parents=True)
            (root / "scripts").mkdir()
            paths = ("scripts/production-reboot-stability.sh", "scripts/production_reboot_stability.py",
                     "scripts/production_stability_evidence.py",
                     "reference/test250/attempt-04/README.md", "reference/test250/attempt-04/policy.json")
            for index, path in enumerate(paths):
                (root / path).write_text(f"different registered file {index}\n")
            changed_remote_policy = False
            def git_output(argv, **kwargs):
                if argv[1] == "branch":
                    return b"test\n"
                if argv[1] == "rev-parse":
                    return b"same-pushed-commit\n"
                self.assertEqual(argv[1], "show")
                path = argv[2].split(":", 1)[1]
                if changed_remote_policy and path.endswith("policy.json"):
                    return b"different remote policy\n"
                return (root / path).read_bytes()
            with mock.patch.object(runner, "ROOT", root), \
                 mock.patch.object(runner, "TEST250_ROOT", test_root), \
                 mock.patch.object(runner, "P", registration), \
                 mock.patch.object(runner.subprocess, "check_output", side_effect=git_output), \
                 mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(returncode=0)):
                runner.assert_registration_pushed()
                changed_remote_policy = True
                with self.assertRaises(runner.CaptureError):
                    runner.assert_registration_pushed()

    def test_other_bluetooth_error_cannot_use_known_error_set(self):
        rows = self.rows()
        error = "Bluetooth: hci0: command 0xfc00 tx timeout"
        rows.append({**rows[0], "_SOURCE_BOOTTIME_TIMESTAMP": "14000000",
                     "PRIORITY": "4", "MESSAGE": error})
        self.assertTrue(self.scan(rows, known_priority3={error})["suspects"])

    def test_bluetooth_health_requires_same_boot_power_and_units(self):
        good = self.health()
        self.assertTrue(runner.parse_bluetooth_health(good, B)["healthy"])
        for old, new in ((B, C), ("bluetooth=active", "bluetooth=failed"),
                         ("address=active", "address=inactive"),
                         ("controllers=hci0 ", "controllers=hci0 hci1 "),
                         ("Powered: yes", "Powered: no")):
            self.assertFalse(runner.parse_bluetooth_health(good.replace(old, new), B)["healthy"])
        with self.assertRaises(ValueError):
            runner.parse_bluetooth_health("", B)

    def test_unpowered_controller_capture_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock(folder=Path(temp))
            rec.adb.return_value = (self.health().replace("Powered: yes", "Powered: no"), 0)
            with self.assertRaises(runner.CaptureError):
                runner.bluetooth_health(rec, B)
            self.assertFalse(json.loads((Path(temp) / "bluetooth-health.json").read_text())["healthy"])

    def test_approved_attempt_replays_evidence_without_amending_old_verdict(self):
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-04"):
            base = runner.baseline()
        raw = (runner.TEST250_ROOT / "attempt-03/round-01/kernel-journal-json.txt").read_text()
        boot = json.loads(raw.splitlines()[0])["_BOOT_ID"]
        scan = runner.inspect(raw, boot, base)
        self.assertEqual(scan["suspects"], [])
        self.assertEqual(scan["fault_counts"], {})
        self.assertEqual(scan["qca_baudrate_warning"]["recovery_seconds"], 0.808107)
        old = json.loads((runner.TEST250_ROOT / "attempt-03/round-01/verdict.json").read_text())
        self.assertEqual(old["verdict"], "suspect")


class QcaCycleClassificationTests(unittest.TestCase):
    def rows(self, specs=None):
        specs = specs or [(4, ev.QCA_SETUP, 6), (4.1, ev.QCA_BAUDRATE_EVENT, 3),
                          (4.9, ev.QCA_READY, 6), (8, ev.QCA_SETUP, 6),
                          (8.1, ev.QCA_BAUDRATE_EVENT, 3), (8.9, ev.QCA_READY, 6)]
        return [{"_BOOT_ID": B, "_SOURCE_BOOTTIME_TIMESTAMP": str(round(t * 1e6)),
                 "PRIORITY": str(priority), "MESSAGE": message}
                for t, message, priority in [(0, "Linux version test-production", 6)] + specs]

    def scan(self, rows=None, **kwargs):
        raw = "\n".join(json.dumps(row) for row in (self.rows() if rows is None else rows))
        return ev.inspect_journal(raw, B, accepted_qca_cycles=True, **kwargs)

    def test_two_events_in_distinct_completed_cycles_are_counted(self):
        result = self.scan()
        self.assertEqual(result["suspects"], [])
        self.assertEqual(result["known_warning_count"], 2)
        self.assertEqual(result["qca_baudrate_warning"]["setup_count"], 2)
        self.assertEqual(result["qca_baudrate_warning"]["state"], "accepted")
        self.assertEqual(clean_gate(journal=result), "clean")

    def test_same_two_events_still_stop_under_single_event_policy(self):
        raw = "\n".join(json.dumps(row) for row in self.rows())
        result = ev.inspect_journal(raw, B, accepted_qca_baudrate=True)
        self.assertEqual(clean_gate(journal=result), "suspect")

    def test_two_events_in_same_cycle_stop(self):
        result = self.scan(self.rows([(4, ev.QCA_SETUP, 6),
            (4.1, ev.QCA_BAUDRATE_EVENT, 3), (4.2, ev.QCA_BAUDRATE_EVENT, 3), (5, ev.QCA_READY, 6)]))
        self.assertEqual(result["qca_baudrate_warning"]["reason"], "more than one event in a setup cycle")
        self.assertFalse(ev.may_continue(clean_gate(journal=result)))

    def test_third_event_in_third_completed_cycle_stops(self):
        rows = self.rows() + self.rows([(12, ev.QCA_SETUP, 6),
            (12.1, ev.QCA_BAUDRATE_EVENT, 3), (13, ev.QCA_READY, 6)])[1:]
        self.assertEqual(self.scan(rows)["qca_baudrate_warning"]["event_count"], 3)
        self.assertEqual(clean_gate(journal=self.scan(rows)), "suspect")

    def test_three_complete_cycles_and_no_event_are_absent(self):
        specs = [(t + offset, msg, 6) for t in (4, 8, 12)
                 for offset, msg in ((0, ev.QCA_SETUP), (1, ev.QCA_READY))]
        result = self.scan(self.rows(specs))
        self.assertEqual(result["qca_baudrate_warning"]["state"], "absent")
        self.assertEqual(result["qca_baudrate_warning"]["setup_count"], 3)
        self.assertEqual(clean_gate(journal=result), "clean")

    def test_four_cycles_without_event_stop_with_structured_suspect(self):
        specs = [(t + offset, msg, 6) for t in (4, 8, 12, 16)
                 for offset, msg in ((0, ev.QCA_SETUP), (1, ev.QCA_READY))]
        result = self.scan(self.rows(specs))
        self.assertTrue(result["suspects"])
        self.assertEqual(result["qca_baudrate_warning"]["state"], "suspect")
        self.assertEqual(clean_gate(journal=result), "suspect")

    def test_orphan_completion_or_missing_preceding_setup_stop(self):
        for specs in ([(4, ev.QCA_READY, 6)], [(4, ev.QCA_BAUDRATE_EVENT, 3)]):
            with self.subTest(specs=specs):
                self.assertTrue(self.scan(self.rows(specs))["suspects"])

    def test_overlap_or_wrong_soc_or_controller_stop_without_event(self):
        cases = [[(4, ev.QCA_SETUP, 6), (5, ev.QCA_SETUP, 6), (6, ev.QCA_READY, 6)],
                 [(4, ev.QCA_SETUP.replace("6855", "7850"), 6)],
                 [(4, ev.QCA_SETUP.replace("hci0", "hci1"), 6)]]
        for specs in cases:
            with self.subTest(specs=specs):
                self.assertEqual(clean_gate(journal=self.scan(self.rows(specs))), "suspect")

    def test_late_completion_zero_event_and_wrong_priority_stop(self):
        cases = [[(18, ev.QCA_SETUP, 6), (19, ev.QCA_BAUDRATE_EVENT, 3), (20.000001, ev.QCA_READY, 6)],
                 [(21, ev.QCA_SETUP, 6), (22, ev.QCA_READY, 6)],
                 [(0, ev.QCA_SETUP, 6), (0, ev.QCA_BAUDRATE_EVENT, 3), (1, ev.QCA_READY, 6)],
                 [(4, ev.QCA_SETUP, 6), (5, ev.QCA_BAUDRATE_EVENT, 4), (6, ev.QCA_READY, 6)],
                 [(4, ev.QCA_SETUP, 6), (5, ev.QCA_BAUDRATE_EVENT, 3), (10.000001, ev.QCA_READY, 6)]]
        for specs in cases:
            with self.subTest(specs=specs):
                self.assertEqual(clean_gate(journal=self.scan(self.rows(specs))), "suspect")

    def test_completion_at_twenty_seconds_is_allowed(self):
        specs = [(14, ev.QCA_SETUP, 6), (15, ev.QCA_BAUDRATE_EVENT, 3), (20, ev.QCA_READY, 6)]
        self.assertEqual(clean_gate(journal=self.scan(self.rows(specs))), "clean")

    def test_exact_microsecond_five_second_boundary_is_preserved(self):
        specs = [(2, ev.QCA_SETUP, 6), (3.000006, ev.QCA_BAUDRATE_EVENT, 3), (8.000006, ev.QCA_READY, 6)]
        result = self.scan(self.rows(specs))
        self.assertEqual(clean_gate(journal=result), "clean")
        self.assertEqual(result["qca_baudrate_warning"]["cycles"][0]["events"][0]["recovery_seconds"], 5)
        specs[-1] = (8.000007, ev.QCA_READY, 6)
        self.assertEqual(clean_gate(journal=self.scan(self.rows(specs))), "suspect")

    def test_pending_second_cycle_deadline_cannot_be_clean(self):
        rows = self.rows()[:-1]
        scan = self.scan(rows, observed_uptime=10)
        self.assertEqual(scan["qca_baudrate_warning"]["state"], "pending")
        self.assertFalse(scan["suspects"])
        self.assertEqual(clean_gate(journal=scan), "suspect")
        self.assertTrue(self.scan(rows, observed_uptime=13.100001)["suspects"])

    def test_no_event_pending_setup_expires_at_twenty_seconds(self):
        rows = self.rows([(18, ev.QCA_SETUP, 6)])
        self.assertEqual(self.scan(rows, observed_uptime=19)["qca_baudrate_warning"]["state"], "pending")
        self.assertTrue(self.scan(rows, observed_uptime=20.000001)["suspects"])

    def test_other_bluetooth_error_and_cpu_panic_are_not_masked(self):
        for message in ("Bluetooth: hci0: command 0xfc00 tx timeout", "Kernel panic - not syncing: test"):
            rows = self.rows() + self.rows([(14, message, 4)])[1:]
            result = self.scan(rows, known_priority3={message})
            self.assertNotEqual(clean_gate(journal=result), "clean")
            if message.startswith("Kernel panic"):
                self.assertIn("panic", result["fault_counts"])
            else:
                self.assertTrue(result["suspects"])

    def test_approved_real_cycle_replay_keeps_old_suspect_immutable(self):
        folder = runner.TEST250_ROOT / "attempt-04/round-05"
        before = (folder / "verdict.json").read_bytes()
        raw = (folder / "kernel-journal-json.txt").read_text()
        boot = json.loads(raw.splitlines()[0])["_BOOT_ID"]
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-05"):
            base = runner.baseline()
        self.assertTrue(base["accepted_qca_cycles"])
        scan = runner.inspect(raw, boot, base)
        self.assertEqual(scan["suspects"], [])
        self.assertEqual(scan["qca_baudrate_warning"]["setup_count"], 3)
        self.assertEqual(scan["qca_baudrate_warning"]["event_count"], 2)
        self.assertEqual((folder / "verdict.json").read_bytes(), before)
        self.assertEqual(json.loads(before)["verdict"], "suspect")

    def test_registered_cycle_limits_cannot_be_silently_broadened(self):
        read_text = Path.read_text
        for key, value in (("maximum_count", 3), ("maximum_setup_count", 4),
                           ("maximum_per_setup_count", 2), ("maximum_completion_source_seconds", 25)):
            def altered(path, *args, **kwargs):
                raw = read_text(path, *args, **kwargs)
                if path == runner.TEST250_ROOT / "attempt-05/policy.json":
                    payload = json.loads(raw); payload[key] = value
                    return json.dumps(payload)
                return raw
            with self.subTest(key=key), mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-05"), \
                 mock.patch.object(Path, "read_text", altered), self.assertRaises(ValueError):
                runner.baseline()

    def test_live_cycle_failure_stops_observer_without_extra_wait(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = mock.Mock(folder=Path(temp))
            rec.adb.return_value = (B + "\n14.0 30.0\n", 0)
            proc = mock.Mock(); proc.poll.return_value = None; proc.wait.return_value = -15
            raw = "\n".join(json.dumps(row) for row in self.rows()[:-1]) + "\n"
            def start(_argv, stdout, stderr):
                stdout.write(raw.encode()); stdout.flush(); return proc
            with mock.patch.object(runner.subprocess, "Popen", side_effect=start), \
                 mock.patch.object(runner.time, "sleep") as sleep:
                with self.assertRaises(runner.KernelEvidenceError):
                    runner.observe_window(rec, B, 10,
                        {"known_priority3": set(), "accepted_qca_baudrate": True, "accepted_qca_cycles": True})
                sleep.assert_not_called()
                proc.terminate.assert_called_once()

    def test_fresh_attempt_policy_is_in_pushed_registration_gate(self):
        def git_output(argv, **kwargs):
            if argv[1] == "branch":
                return b"test\n"
            if argv[1] == "rev-parse":
                return b"same-pushed-commit\n"
            path = argv[2].split(":", 1)[1]
            if path.endswith("attempt-05/policy.json"):
                return b"unpublished policy bytes\n"
            return (ROOT / path).read_bytes()
        with mock.patch.object(runner, "P", runner.TEST250_ROOT / "attempt-05"), \
             mock.patch.object(runner.subprocess, "check_output", side_effect=git_output), \
             mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(returncode=0)):
            with self.assertRaises(runner.CaptureError):
                runner.assert_registration_pushed()


if __name__ == "__main__":
    unittest.main()
