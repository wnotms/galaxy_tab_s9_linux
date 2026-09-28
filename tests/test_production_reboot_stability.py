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


if __name__ == "__main__":
    unittest.main()
