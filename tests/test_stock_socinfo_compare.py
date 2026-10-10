import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('stock_compare_tests',
    ROOT/'userspace/sensors/stock-socinfo-compare.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
NATIVE_BOOT = '11111111-2222-3333-4444-555555555555'
RECOVERY_BOOT = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def native():
    return dict(boot_id=NATIVE_BOOT, family='Snapdragon', machine='SM8550',
                soc_id='519', info_fmt='0x00000010', hardware_platform='8',
                hardware_platform_subtype='0', platform_version='65536')


def packet(changes=None):
    rows = dict(begin=RECOVERY_BOOT, device='gts9wifi', kernel='5.15.94-Foldiby-+', uid='0')
    rows.update({name: value.encode().hex() for name, value in M.MAPPER.translate(native()).items()})
    rows['end'] = RECOVERY_BOOT
    rows.update(changes or {})
    return '\r\n'.join(name+'\t'+value for name, value in rows.items())+'\r\n'


class StockSocinfoCompareTests(unittest.TestCase):
    def test_exact_bytes_match_without_sensor_acceptance(self):
        result = M.compare(packet(), RECOVERY_BOOT, native())
        self.assertEqual(result['verdict'], 'STOCK_SOCINFO_EXACT_MATCH')
        self.assertEqual(result['differences'], {})
        for name in ('SSC_verified', 'sensor_verified', 'rotation_verified'):
            self.assertFalse(result[name])

    def test_difference_retained_not_normalized_or_repaired(self):
        result = M.compare(packet({'platform_version': b'00065536\n'.hex()}), RECOVERY_BOOT, native())
        self.assertEqual(result['verdict'], 'STOCK_SOCINFO_DIFFERS')
        self.assertEqual(result['differences'], {'platform_version':
            dict(native='65536\n', stock='00065536\n')})

    def test_each_field_difference_is_reported(self):
        for name, text in (('hw_platform', 'Surf\n'), ('platform_subtype', 'charm\n'),
                           ('platform_subtype_id', '1\n'), ('platform_version', '65537\n')):
            with self.subTest(name=name):
                result = M.compare(packet({name: text.encode().hex()}), RECOVERY_BOOT, native())
                self.assertEqual(set(result['differences']), {name})

    def test_wrong_or_mixed_recovery_boot_rejected(self):
        for name in ('begin', 'end'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'boot'):
                M.compare(packet({name: NATIVE_BOOT}), RECOVERY_BOOT, native())

    def test_same_native_recovery_boot_rejected(self):
        with self.assertRaisesRegex(ValueError, 'differ'):
            M.compare(packet(), NATIVE_BOOT, native())

    def test_missing_extra_duplicate_or_malformed_row_rejected(self):
        for raw in ('\r\n'.join(x for x in packet().split('\r\n') if not x.startswith('soc_id\t')),
                    packet()+'other\t00\n', packet()+'soc_id\t00\n', packet()+'broken\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                M.compare(raw, RECOVERY_BOOT, native())

    def test_other_recovery_board_kernel_or_nonroot_rejected(self):
        for name, value in (('device', 'gts9u'), ('kernel', '7.2.0-rc3'), ('uid', '987')):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'recovery'):
                M.compare(packet({name: value}), RECOVERY_BOOT, native())

    def test_bad_hex_size_line_null_or_nonascii_rejected(self):
        for value in ('', '0', 'GG', '00'*65, b'MTP'.hex(), b'MTP\nextra\n'.hex(),
                      b'MTP\0\n'.hex(), b'\xff\n'.hex(), b'\n'.hex(), b'MTP\t\n'.hex()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                M.compare(packet({'hw_platform': value}), RECOVERY_BOOT, native())

    def test_decimal_overflow_signed_and_wrong_soc_rejected(self):
        for name, value in (('soc_id', '457\n'), ('platform_version', '4294967296\n'),
                            ('platform_subtype_id', '-1\n'), ('platform_version', '0x10000\n')):
            with self.subTest(name=name), self.assertRaises(ValueError):
                M.compare(packet({name: value.encode().hex()}), RECOVERY_BOOT, native())

    def test_invalid_native_data_rejected(self):
        current = native(); current['hardware_platform'] = '0'
        with self.assertRaises(ValueError):
            M.compare(packet(), RECOVERY_BOOT, current)

    def test_success_returns_once_after_observation(self):
        calls = []
        def observe(): calls.append('observe'); return 'read'
        def restore(): calls.append('return'); return 'desktop'
        result = M.observe_then_return(observe, restore)
        self.assertEqual(calls, ['observe', 'return'])
        self.assertEqual(result, dict(observation='read', observation_error=None,
                                     returned='desktop', return_error=None))

    def test_observation_fault_stops_and_still_returns_once(self):
        calls = []
        def observe(): calls.append('observe'); raise ValueError('missing field')
        def restore(): calls.append('return'); return 'desktop'
        result = M.observe_then_return(observe, restore)
        self.assertEqual(calls, ['observe', 'return'])
        self.assertEqual(result['observation_error'], 'missing field')
        self.assertEqual(result['returned'], 'desktop')

    def test_cleanup_fault_preserves_both_failures_without_retry(self):
        calls = []
        def observe(): calls.append('observe'); raise ValueError('read failed')
        def restore(): calls.append('return'); raise ValueError('ADB lost')
        result = M.observe_then_return(observe, restore)
        self.assertEqual(calls, ['observe', 'return'])
        self.assertEqual(result['observation_error'], 'read failed')
        self.assertEqual(result['return_error'], 'ADB lost')
        self.assertIsNone(result['returned'])

    def test_hex_capture_command_is_shell_valid_and_has_no_hardware_write(self):
        import subprocess
        result = subprocess.run(['sh', '-n'], input=M.COMMAND, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('od -An -v -tx1 /sys/devices/soc0/$name', M.COMMAND)
        for operation in (' of=', 'tee ', 'chmod ', 'echo ', 'reboot', 'systemctl', 'i2c'):
            self.assertNotIn(operation, M.COMMAND)


if __name__ == '__main__':
    unittest.main()
