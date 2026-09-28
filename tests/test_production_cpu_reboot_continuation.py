"""Host-only checks for the CPU-focused continuation decision rule."""

import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import production_cpu_reboot_continuation as runner


class DecisionTests(unittest.TestCase):
    def report(self, message, priority=3):
        return {"fault_counts": {}, "suspects": [{"row": 1, "priority": priority,
                                                    "message": message}],
                "cpu_relevant_suspects": [{"row": 1, "priority": priority,
                                           "message": message}]
                if runner.CPU_SUSPECT.search(message) else []}

    def test_cpu_signatures_stop(self):
        for message in ("CPU 4 non-responsive", "RCU stall", "CSD: lock timeout",
                        "Kernel panic", "Oops:", "BUG:", "SError", "hung task",
                        "workqueue lockup", "unexpected CPU backtrace"):
            with self.subTest(message=message):
                self.assertTrue(runner.cpu_fault(self.report(message)))

    def test_transport_and_bluetooth_are_recorded_without_cpu_stop(self):
        for message in ("Bluetooth: hci0: unexpected event for opcode 0xfc48",
                        "Windows Code43", "NCM TCP timeout", "aux_bridge deferred probe"):
            with self.subTest(message=message):
                self.assertFalse(runner.cpu_fault(self.report(message)))

    def test_existing_fault_counts_always_stop(self):
        self.assertTrue(runner.cpu_fault({"fault_counts": {"soft_lockup": 1},
                                          "cpu_relevant_suspects": []}))

    def test_prior_round_must_be_cpu_clear(self):
        original = runner.P
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as root:
                runner.P = Path(root)
                self.assertEqual(runner.previous(13), runner.SOURCE_BOOT)
                directory = runner.P / "round-13"
                directory.mkdir()
                verdict = directory / "verdict.json"
                verdict.write_text(json.dumps({"verdict": "inconclusive",
                                               "registered_window_completed": True,
                                               "after_boot_id": "f" * 32}))
                with self.assertRaises(runner.old.CaptureError):
                    runner.previous(14)
                verdict.write_text(json.dumps({"verdict": "cpu_clear",
                                               "registered_window_completed": True,
                                               "after_boot_id": "f" * 32}))
                self.assertEqual(runner.previous(14), "f" * 32)
        finally:
            runner.P = original


if __name__ == "__main__":
    unittest.main()
