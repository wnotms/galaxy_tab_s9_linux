"""Ensure Test374 waits for systemd daemon activation before probing SSC."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-374-ssc-userspace-pd-mapper'


class MapperStartOrderingTests(unittest.TestCase):
    def test_mapper_and_rpc_start_are_blocking(self):
        text = (R / 'runtime.py').read_text()
        self.assertIn("['systemctl','start','pd-mapper.service']", text)
        self.assertIn("['systemctl','start',*UNITS[1:-1]]", text)
        self.assertNotIn("['systemctl','start','--no-block','pd-mapper.service']", text)
        self.assertNotIn("['systemctl','start','--no-block',*UNITS[1:-1]]", text)

    def test_scope_remains_userspace_only(self):
        text = (R / 'README.md').read_text()
        self.assertIn('libqrtr1', text)
        self.assertIn('pd-mapper', text)
        self.assertNotIn('SM5440', text)
        self.assertNotIn('charging pump', text)


if __name__ == '__main__':
    unittest.main()
