"""Offline evidence-verdict regression; never accesses a device."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest

import low_address as low


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.stats = {str(cpu): "entries: 8\noverrun: 0\ncommit overrun: 0\ndropped events: 0\n"
                      for cpu in range(8)}
        self.lines = [f" child-123 [00{cpu}] d..1. 1.000000: {low.EVENT}: "
                      f"(modify_prot_start_ptes+0x0/0x2c4) addr=4096 nr=1 pte={pte:#x}"
                      for cpu in low.CPUS for _ in range(low.CYCLES)
                      for pte in (low.PTE_UXN | 0x443, 0x443)]

    def check(self, lines=None, stats=None):
        return low.verify_trace("\n".join(self.lines if lines is None else lines),
                                self.stats if stats is None else stats, 123)

    def test_complete_low_path(self):
        result = self.check()
        self.assertEqual(result["probe_hits"], 16)
        self.assertEqual(result["executable_old_pte_hits"], 8)
        self.assertFalse(result["physical_erratum_reproduced"])
        self.assertFalse(result["cpu_stall_fix_established"])

    def test_negative_trace_mutations(self):
        mutations = {
            "high address": ("addr=4096", "addr=548386549760"),
            "wrong batch": ("nr=1", "nr=2"),
            "wrong pid": ("child-123", "child-124"),
            "wrong cpu": ("[003]", "[002]"),
            "invalid pte": ("pte=0x443", "pte=0x442"),
            "nonexecutable pte": ("pte=0x443", f"pte={low.PTE_UXN | 0x443:#x}"),
            "pte read fault": ("pte=0x443", "pte=(fault)"),
            "missing pte": (" pte=0x443", ""),
        }
        for name, (before, after) in mutations.items():
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                self.check([line.replace(before, after) for line in self.lines])

    def test_missing_duplicate_or_reordered_events(self):
        for lines in ([], self.lines[:-1], self.lines + self.lines[:1],
                      [self.lines[1], self.lines[0]] + self.lines[2:]):
            with self.subTest(lines=len(lines)), self.assertRaises(RuntimeError):
                self.check(lines)

    def test_missing_or_nonzero_loss_accounting(self):
        for field in ("overrun", "commit overrun", "dropped events"):
            for replacement in (field + ": 1", "absent: 0"):
                stats = copy.deepcopy(self.stats)
                stats["3"] = stats["3"].replace(field + ": 0", replacement)
                with self.subTest(field=field, replacement=replacement), self.assertRaises(RuntimeError):
                    self.check(stats=stats)
        del self.stats["7"]
        with self.assertRaises(RuntimeError):
            self.check()

    def test_archived_test240_is_insufficient(self):
        root = Path(__file__).resolve().parents[3]
        old = (root / "reference/boot-tests/test-240-bbm-range/workload-retry/run.txt").read_text()
        start = old.index("GTS9_BBM_TRACE_BEGIN")
        end = old.index("GTS9_BBM_TRACE_END", start)
        # Normalize only the event name; preserve actual high addresses/no old PTE.
        trace = old[start:end].replace("gts9_bbm_240", low.EVENT)
        with self.assertRaisesRegex(RuntimeError, "malformed probe"):
            low.verify_trace(trace, self.stats, 1659)


class ExecutionGuards(unittest.TestCase):
    def invoke(self, args, data=None):
        return subprocess.run([sys.executable, str(Path(low.__file__)), *args],
                              input=data, capture_output=True, timeout=3)

    def test_no_implicit_execution(self):
        self.assertEqual(self.invoke([]).returncode, 2)
        self.assertEqual(self.invoke(["--run"]).returncode, 2)

    def test_worker_requires_parent_handshake(self):
        result = self.invoke(["--worker"], b"")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"missing parent handshake", result.stderr)

    def test_wrong_boot_stops_before_trace_or_mapping(self):
        result = self.invoke(["--run", "--expected-boot", "invalid",
                              "--expected-notes-sha256", "invalid"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"wrong boot", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
