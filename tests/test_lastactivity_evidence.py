import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lastactivity", ROOT / "scripts/lastactivity-evidence.py")
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)
ID = "12345678-1234-1234-1234-123456789abc"


def snapshot(invalid=None):
    lines = [f"GTS9_LA_BEGIN id={ID} trigger=manual ns=999 schema=1 cpus=8 events=6 complete_history=0"]
    for cpu in range(8):
        valid = cpu != invalid
        lines.append(f"GTS9_LA_CPU id={ID} cpu={cpu} valid={int(valid)} seq={2 if valid else 3} nested_dropped=0")
        if valid:
            for kind in range(6):
                lines.append(f"GTS9_LA_EVENT cpu={cpu} kind={kind} count=18446744073709551615 ns=18446744073709551615 a=ffffffffffffffff b=ffffffffffffffff c=ffffffffffffffff")
    lines.append(f"GTS9_LA_END id={ID} records={48 if invalid is None else 42} complete_history=0")
    return "\n".join(lines) + "\n"


class LastActivityEvidenceTests(unittest.TestCase):
    def test_cli_rejects_real_corruption_and_valid_looking_bit_flip(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.txt"
            recovered = Path(tmp) / "recovered.txt"
            source.write_text(snapshot())
            command = [sys.executable, str(ROOT / "scripts/lastactivity-evidence.py"),
                       str(recovered), "--capture-id", ID, "--reference", str(source)]
            recovered.write_text(snapshot())
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            # Still structurally valid hex: only exact reference comparison
            # catches this address corruption.
            recovered.write_text(snapshot().replace("a=ffffffffffffffff", "a=fffffffffffffffe", 1))
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"differs from reference", result.stderr)
            base = ROOT / "reference/boot-tests/test-231-lastactivity-direct-reboot"
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/lastactivity-evidence.py"),
                str(base / "observer/pstore-files/var/lib/systemd/pstore/console-ramoops-0"),
                "--capture-id", "0127f2c4-c55e-4a3a-99c3-52deffd56059",
                "--reference", str(base / "source-live/snapshot-markers.txt"),
            ], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"Snapshot rejected:", result.stderr)
            self.assertNotIn(b"Traceback", result.stderr)

    def test_full_snapshot_and_maximum_value_byte_budget(self):
        text = snapshot()
        result = evidence.parse(text, ID)
        self.assertEqual(len(result["records"]), 48)
        self.assertFalse(result["complete_history"])
        self.assertEqual(result["missing_event_inference"], "inconclusive")
        self.assertLess(len(text.encode()) + 64 * len(text.splitlines()), 20 * 1024)
        self.assertEqual(result, evidence.parse("\n".join("[ 20.0] [C3] " + line for line in text.splitlines()), ID))

    def test_inflight_cpu_remains_invalid_with_other_cpu_evidence(self):
        result = evidence.parse(snapshot(invalid=6), ID)
        self.assertFalse(result["cpus"][6]["valid"])
        self.assertEqual(len(result["records"]), 42)
        self.assertEqual(result["root_cause"], "not_established")

    def test_truncation_wrong_identity_duplicates_and_mixing_rejected(self):
        text = snapshot()
        event = next(line for line in text.splitlines(True) if "LA_EVENT" in line)
        cases = [text.rsplit("GTS9_LA_END", 1)[0], text.replace(event, "", 1),
                 text.replace(event, event + event, 1), text + text,
                 text.replace("valid=1 seq=2", "valid=1 seq=3", 1),
                 text.replace(event, "GTS9_LA_BEGIN id=other\n" + event, 1),
                 text.replace(f"id={ID}", "id=00000000-0000-0000-0000-000000000000")]
        for case in cases:
            with self.subTest(case=case[:100]), self.assertRaises(ValueError):
                evidence.parse(case, ID)


if __name__ == "__main__":
    unittest.main()
