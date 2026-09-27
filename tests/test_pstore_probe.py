import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('probe', ROOT / 'scripts/pstore-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
BOOT = 'a80804be-229c-46f7-aae8-bd797fb22883'
ID = '12345678-1234-4321-9876-123456789abc'


class ProbeTests(unittest.TestCase):
    def test_exact_binary_with_unrelated_prefix_and_ecc_suffix(self):
        data = probe.make_probe(BOOT, ID)
        self.assertLess(len(data), 40000)
        self.assertIn(bytes([0]) * 4096, data)
        result = probe.compare(data, b'old\xff' + data + b'ECC notice')
        self.assertEqual(result['verdict'], 'exact')
        self.assertEqual(result['exact_offsets'], [4])
        self.assertFalse(result['ready_for_wedge_series'])

    def test_bit_flip_and_truncation_do_not_pass(self):
        data = probe.make_probe(BOOT, ID)
        damaged = bytearray(data)
        damaged[1024] ^= 0x81
        result = probe.compare(data, bytes(damaged))
        self.assertEqual(result['verdict'], 'absent_or_corrupt')
        self.assertEqual(result['changed_bytes'], 1)
        self.assertEqual(result['changed_bits'], 2)
        self.assertTrue(probe.compare(data, data[:-1])['truncated'])

    def test_stale_duplicate_and_damaged_identity_rejected(self):
        data = probe.make_probe(BOOT, ID)
        other = probe.make_probe(BOOT, '22345678-1234-4321-9876-123456789abc')
        for bad in (other, data + data, b'X' + data[1:]):
            self.assertEqual(probe.compare(data, bad)['verdict'], 'absent_or_corrupt')
        self.assertNotIn('changes', probe.compare(data, b'X' + data[1:]))

    def test_bad_reference_is_never_accepted(self):
        for bad in (b'', b'abc', probe.make_probe(BOOT, ID)[:-1]):
            with self.assertRaises(ValueError):
                probe.compare(bad, bad)
