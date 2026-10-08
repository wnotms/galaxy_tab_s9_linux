"""Check effective overrides against the qualified upstream unit templates."""
import configparser
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ssc_runtime', ROOT/'userspace/sensors/prepare-runtime.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def parse(data):
    p = configparser.ConfigParser(interpolation=None, strict=False)
    p.optionxform = str
    p.read_string(data)
    return p


class RuntimeOverridesTests(unittest.TestCase):
    def test_all_runtime_units_gated_without_boot_activation(self):
        files = M.overrides()
        self.assertEqual(len(files), 5)
        for unit in M.UNITS:
            p = parse(files['etc/systemd/system/'+unit+'.d/90-gts9-controlled-test.conf'].decode())
            self.assertEqual(p['Unit']['ConditionPathExists'], M.GATE)
            self.assertNotIn('Install', p)
            self.assertNotIn('Requires', p['Unit'])

    def test_original_always_restart_is_overridden(self):
        patch = (ROOT/'userspace/sensors/patches/hexagonrpc/systemd-services.patch').read_text()
        self.assertIn('+Restart=always', patch)
        for unit in M.UNITS:
            p = parse(M.overrides()['etc/systemd/system/'+unit+'.d/90-gts9-controlled-test.conf'].decode())
            self.assertEqual(p['Service']['Restart'], 'no')
            self.assertEqual(p['Unit']['StartLimitBurst'], '1')
            self.assertEqual(p['Unit']['StartLimitIntervalSec'], 'infinity')

    def test_root_and_sensor_pd_commands_are_distinct_and_replace_original(self):
        for unit in M.UNITS[1:3]:
            text = M.overrides()['etc/systemd/system/'+unit+'.d/90-gts9-controlled-test.conf'].decode()
            self.assertIn('ExecStart=\nExecStart=', text)
            p = parse(text)
            command = p['Service']['ExecStart']
            self.assertIn('-f /dev/fastrpc-adsp -d adsp', command)
            self.assertEqual(' -s ' in command, 'sensorspd' in unit)
            self.assertTrue(command.endswith('-R '+M.PREFIX))
            self.assertEqual(p['Service']['ReadWritePaths'], M.PREFIX+'/sensors')
            self.assertEqual(p['Service']['ProtectSystem'], 'strict')

    def test_no_real_persist_or_remoteproc_command(self):
        data = '\n'.join(x.decode() for x in M.overrides().values())
        for forbidden in ('/mnt/vendor/persist', '/dev/sda', 'remoteproc', 'echo start', 'sleep 25'):
            self.assertNotIn(forbidden, data)

    def test_sdsp_cannot_use_normal_admission_gate(self):
        p = parse(M.overrides()['etc/systemd/system/hexagonrpcd-sdsp.service.d/90-gts9-controlled-test.conf'].decode())
        self.assertNotEqual(p['Unit']['ConditionPathExists'], M.GATE)
        self.assertEqual(p['Service']['Restart'], 'no')

    def test_offline_output_hashes_and_no_gate_created(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'staged'
            report = M.stage(target)
            self.assertEqual(json.loads((target/'RUNTIME.json').read_text()), report)
            self.assertFalse(report['device_operations'])
            self.assertFalse(report['gate_created'])
            for name, sha in report['files'].items():
                self.assertEqual(hashlib.sha256((target/name).read_bytes()).hexdigest(), sha)
            with self.assertRaises(FileExistsError):
                M.stage(target)


if __name__ == '__main__':
    unittest.main()
