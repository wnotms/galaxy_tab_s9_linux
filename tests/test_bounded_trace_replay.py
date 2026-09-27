import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bounded_trace", ROOT / "scripts/bounded-trace-replay.py")
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


class BoundedTraceTests(unittest.TestCase):
    def test_actual_ramoops_rounding_header_and_reserve(self):
        spec = importlib.util.spec_from_file_location("prepare_trace", ROOT / "scripts/prepare-csd-trace.py")
        prep = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prep)
        budget = prep.retention_budget(4408371, 30, 896 * 1024)
        self.assertEqual(budget["console_zone_bytes"], 512 * 1024)
        self.assertEqual(budget["trace_budget_bytes"], trace.DEFAULT_BUDGET)
        self.assertEqual(trace.DEFAULT_BUDGET, 393204)
        self.assertLess(budget["optimistic_text_retention_s"], 2.68)
        self.assertEqual(prep.retention_budget(1000, 1, 512 * 1024)["console_zone_bytes"], 512 * 1024)
        with self.assertRaises(ValueError):
            prep.retention_budget(1000, 1, 200 * 1024)

    def test_real_capture_fits_budget_but_never_claims_complete_or_ready(self):
        rows, source = trace.read_capture(trace.DEFAULT_CAPTURE)
        for overhead in (0, 32, 64):
            with self.subTest(overhead=overhead):
                payload, report = trace.serialize(rows, source, prefix_bytes=overhead)
                self.assertLessEqual(len(payload), trace.DEFAULT_BUDGET)
                self.assertEqual(len(payload), report["serialized_bytes"])
                self.assertFalse(report["complete_all_cpu_window"])
                self.assertFalse(report["ready_for_wedge_series"])
                self.assertEqual(report["cross_cpu_missing_event_inference"], "inconclusive")
                self.assertEqual({c["cpu"] for c in report["per_cpu"]}, set(range(8)))
                self.assertTrue(all(c["kept_records"] > 0 for c in report["per_cpu"]))
                self.assertIn(b"csd_queue_cpu:", payload)
                self.assertIn(b"ipi_raise:", payload)
                self.assertTrue(report["per_cpu"][7]["truncated"])
                metadata = json.loads(payload.splitlines()[0][overhead:])
                self.assertEqual(metadata["per_cpu"], report["per_cpu"])

    def test_sufficient_space_preserves_all_window_records_but_not_hardware_readiness(self):
        rows, source = trace.read_capture(trace.DEFAULT_CAPTURE)
        payload, report = trace.serialize(rows, source, budget=16 * 1024 * 1024)
        expected = [r for r in rows if report["cutoff_us"] <= r[0] <= source["trigger_us"]]
        self.assertTrue(report["complete_all_cpu_window"])
        self.assertEqual(sum(c["kept_records"] for c in report["per_cpu"]), len(expected))
        self.assertFalse(report["ready_for_wedge_series"])
        self.assertEqual(report["persistent_recovery"], "not_tested")
        self.assertEqual(sorted(payload.splitlines()[1:]), sorted(b"~" * 32 + r[2].rstrip(b"\n") for r in expected))

    def test_cpu_fairness_and_truncation_even_with_identical_timestamps(self):
        rows = [(1_000_000, cpu, (f"cpu{cpu} record\n").encode()) for cpu in range(8) for _ in range(100 if cpu == 7 else 1)]
        _, report = trace.serialize(rows, {"trigger_us": 41_000_000, "common_start_us": 0}, budget=trace.METADATA_BYTES + 800)
        self.assertTrue(all(c["kept_records"] >= 1 for c in report["per_cpu"]))
        self.assertTrue(report["per_cpu"][7]["truncated"])
        self.assertFalse(report["complete_all_cpu_window"])

    def test_oversized_newest_record_does_not_substitute_an_older_tail(self):
        rows = [(1, 0, b"older\n"), (2, 0, b"X" * 1000 + b"\n")]
        _, report = trace.serialize(rows, {"trigger_us": 41_000_000, "common_start_us": 0}, budget=trace.METADATA_BYTES + 800)
        self.assertEqual(report["per_cpu"][0]["kept_records"], 0)
        self.assertEqual(report["per_cpu"][0]["dropped_records"], 2)
        self.assertFalse(report["complete_all_cpu_window"])

    def test_invalid_capacity_and_missing_source_interval_fail_closed(self):
        for kwargs in ({"budget": 1}, {"prefix_bytes": -1}, {"window_seconds": 0}, {"window_seconds": 61}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                trace.serialize([], {"trigger_us": 60_000_000, "common_start_us": 0}, **kwargs)
        with self.assertRaises(ValueError):
            trace.serialize([], {"trigger_us": 60_000_000, "common_start_us": 0, "large_metadata": "x" * 20000})

    def test_corrupt_or_incomplete_capture_is_rejected(self):
        mutations = {
            "calibration/trace.txt": b"truncated\n",
            "calibration/boot-id-after.txt": b"11111111-1111-1111-1111-111111111111\n",
            "calibration/trace_clock.txt": b"[local] global\n",
            "calibration/set_event.txt": b"ipi:ipi_entry\n",
            "calibration/csd-csd_queue_cpu.filter": b"cpu == 6\n",
            "calibration/cpu7-after.stats": (trace.DEFAULT_CAPTURE / "calibration/cpu7-after.stats").read_bytes().replace(b"overrun: 0", b"overrun: 1"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(trace.DEFAULT_CAPTURE / "calibration", root / "calibration")
            (root / "final-state").mkdir()
            shutil.copyfile(trace.DEFAULT_CAPTURE / "final-state/trace-sha256.txt", root / "final-state/trace-sha256.txt")
            for path, value in mutations.items():
                original = (root / path).read_bytes()
                (root / path).write_bytes(value)
                with self.subTest(path=path), self.assertRaises(ValueError):
                    trace.read_capture(root)
                (root / path).write_bytes(original)


if __name__ == "__main__":
    unittest.main()
