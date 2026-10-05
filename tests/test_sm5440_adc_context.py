"""Execute the exact device collector against temporary files; no tablet access."""
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('adc_context', ROOT / 'scripts/sm5440-adc-context.py')
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class ADCContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.request = dict(boot_id='ecaa3c64-5c69-4bbe-b755-1a2aff6a88ca',
                            config=hashlib.sha256(b'# CONFIG_HVC_DCC is not set\n').hexdigest(),
                            notes=hashlib.sha256(b'notes').hexdigest())
        files = {'proc/sys/kernel/random/boot_id': self.request['boot_id'].encode(),
                 'proc/config.gz': gzip.compress(b'# CONFIG_HVC_DCC is not set\n'),
                 'proc/cmdline': b'console=tty0 nowatchdog', 'sys/kernel/notes': b'notes',
                 'sys/kernel/debug/regmap/0-0063/range': b'0-2b\n',
                 'sys/kernel/debug/sm5440-0-0063/snapshot': b'sample_valid=1\nsample_age_ms=20\n',
                 'sys/class/power_supply/sm5714-battery/uevent': b'POWER_SUPPLY_CAPACITY=30\n',
                 'sys/class/power_supply/sm5714-usb/uevent': b'POWER_SUPPLY_ONLINE=1\n'}
        self.regs = {4: 0xc0, 5: 0xf7, 6: 0x18, 7: 0xf8, 0x10: 1,
                     0x1c: 0x0c, 0x1d: 0xdf, 0x2b: 0x21}
        for name, data in files.items():
            self.write(name, data)
        self.registers()

    def write(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def registers(self):
        self.write('sys/kernel/debug/regmap/0-0063/registers',
                   ''.join(f'{i:02x}: {self.regs.get(i, 0):02x}\n' for i in range(0x2c)).encode())

    def test_exact_mask_reads_never_consume_interrupt_or_write(self):
        calls = []
        pread = os.pread
        def observed(fd, n, offset):
            calls.append((n, offset))
            return pread(fd, n, offset)
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(TOOL.os, 'pread', observed):
            result = TOOL.capture(self.request, self.root)
        self.assertEqual(calls, [(7, r * 7) for r in [0x10, 4, 5, 6, 7, 0x1c, 0x1d, 0x2b, 0x10]])
        self.assertEqual(result['masks'], dict(MSK1=0xc0, MSK2=0xf7, MSK3=0x18, MSK4=0xf8))
        self.assertTrue(result['matches_vendor_msk4'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        for key in ['adc_request_executed', 'read_to_clear_registers_read', 'device_writes',
                    'conversion_freshness_proven', 'calibration_proven',
                    'software_ocp_verified', 'pump_activation_granted']:
            self.assertFalse(result[key])

    def test_different_mask_retained_without_claiming_timeout_cause(self):
        self.regs[7] = 0xff
        self.registers()
        result = TOOL.capture(self.request, self.root)
        self.assertFalse(result['matches_vendor_msk4'])
        self.assertTrue(result['msk4_bit0_set'])
        self.assertFalse(result['conversion_freshness_proven'])

    def test_wrong_boot_config_or_notes_stop_before_any_regmap_read(self):
        for key in self.request:
            request = dict(self.request, **{key: 'wrong'})
            with patch.object(TOOL.os, 'pread') as read:
                with self.assertRaisesRegex(ValueError, 'mismatch'):
                    TOOL.capture(request, self.root)
                read.assert_not_called()

    def test_lpcharge_stops_before_register_reads(self):
        for cmdline in [b'lpcharge=1', b'console=tty0 sec-battery.lpcharge=1 nowatchdog',
                        b'sec_pon_alarm.lpcharge=1']:
            self.write('proc/cmdline', cmdline)
            with patch.object(TOOL.os, 'pread') as read:
                with self.assertRaisesRegex(ValueError, 'lpcharge'):
                    TOOL.capture(self.request, self.root)
                read.assert_not_called()

    def test_malformed_register_or_range_refused(self):
        self.write('sys/kernel/debug/regmap/0-0063/range', b'0-ff\n')
        with self.assertRaisesRegex(ValueError, 'range'):
            TOOL.capture(self.request, self.root)
        self.write('sys/kernel/debug/regmap/0-0063/range', b'0-2b\n')
        self.write('sys/kernel/debug/regmap/0-0063/registers', b'invalid')
        with self.assertRaisesRegex(ValueError, 'line'):
            TOOL.capture(self.request, self.root)

    def test_running_pump_and_wrong_chip_refused(self):
        for register, value in [(0x10, 5), (0x2b, 0x22)]:
            original = self.regs[register]
            self.regs[register] = value
            self.registers()
            with self.assertRaises(ValueError):
                TOOL.capture(self.request, self.root)
            self.regs[register] = original

    def test_mid_capture_boot_change_refused(self):
        pread = os.pread
        def changed(fd, n, offset):
            result = pread(fd, n, offset)
            self.write('proc/sys/kernel/random/boot_id', b'newboot')
            return result
        with patch.object(TOOL.os, 'pread', changed):
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                TOOL.capture(self.request, self.root)

    def test_clock_regression_refused(self):
        with patch.object(TOOL.time, 'clock_gettime_ns', side_effect=[100, 99]):
            with self.assertRaisesRegex(ValueError, 'clock'):
                TOOL.capture(self.request, self.root)

    def test_generated_program_executes_the_same_collector(self):
        program = TOOL.device_program(self.request)
        program = program.replace('capture(' + repr(self.request) + ')',
                                  'capture(' + repr(self.request) + ',Path(' + repr(str(self.root)) + '))')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(program, '<device-program>', 'exec'), {})
        self.assertEqual(json.loads(output.getvalue())['identity']['boot_id'], self.request['boot_id'])

    def run_cli(self, response=None, error=None):
        output = self.root / 'host-output'
        argv = ['sm5440-adc-context.py', '--expected-boot-id', self.request['boot_id'],
                '--expected-config', self.request['config'], '--expected-notes', self.request['notes'],
                '--output', str(output)]
        with patch.object(sys, 'argv', argv), patch.object(TOOL.subprocess, 'run',
                return_value=response, side_effect=error) as run, contextlib.redirect_stdout(io.StringIO()):
            code = TOOL.main()
        self.assertEqual(run.call_count, 1, 'no retry of the physical command')
        hashes = json.loads((output / 'SHA256.json').read_text())
        for name, expected in hashes.items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)
        return code, json.loads((output / 'summary.json').read_text())

    def test_host_seals_success_without_adc_qualification(self):
        data = TOOL.capture(self.request, self.root)
        code, result = self.run_cli(subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b''))
        self.assertEqual(code, 0)
        self.assertEqual(result['verdict'], 'CONTEXT_CAPTURED_NOT_ADC_QUALIFIED')
        self.assertFalse(result['device_writes'])

    def test_transport_unavailable_and_timeout_preserve_stop(self):
        for error, rc in [(FileNotFoundError('missing adb'), 127),
                          (subprocess.TimeoutExpired([], 12, output=b'partial'), 124)]:
            with self.subTest(error=error):
                output = self.root / 'host-output'
                if output.exists():
                    import shutil
                    shutil.rmtree(output)
                code, result = self.run_cli(error=error)
                self.assertEqual(code, 1)
                self.assertEqual(result['verdict'], 'STOP_IDENTITY_OR_CAPTURE')
                self.assertEqual(result['command']['returncode'], rc)

    def test_malformed_or_mismatched_output_is_never_qualification(self):
        data = TOOL.capture(self.request, self.root)
        data['identity']['notes'] = 'wrong'
        code, result = self.run_cli(subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b''))
        self.assertEqual(code, 1)
        self.assertEqual(result['verdict'], 'STOP_IDENTITY_OR_CAPTURE')


if __name__ == '__main__':
    unittest.main()
