"""Run Test337 admission through real bounded discovery with mocked transport.

No device requests occur. Histories are original Test336 attribution evidence;
identity and endpoint transport are explicit fixtures for the new candidate.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import charging_wifi_discovery as discovery

R = ROOT / 'reference/boot-tests/test-337-async-fixed-charge-restore'
OLD = R.parent / 'test-336-pps-off-roundtrip'
BEFORE = '90274be1fa0c44f794eecceaad099b45'
AFTER = 'b6cc488f92834c2eaae21dd8caa8ed50'


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('restore337_admission', R / 'host_flow.py')
        cls.host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.host)
        cls.host.configure()

    def run_admission(self, boot=AFTER, histories=True, failure=None, unexpected=False):
        h = self.host
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pre = root / 'pre'; pre.mkdir()
            key = root / 'key'; key.write_text('mock key, no real SSH'); key.chmod(0o600)
            trust = root / 'known-hosts'; trust.write_text('fixture ssh-ed25519 AAAA\n'); trust.chmod(0o600)
            plan = dict(h.PLAN, key=str(key), known_hosts=str(trust), alias='fixture')
            (root / 'mutation-state.json').write_text(json.dumps(dict(phase='candidate-installed-awaiting-owner-C1-System-boot')))
            (pre / 'summary.json').write_text(json.dumps(dict(boot_id=BEFORE, transport=dict(wifi='10.91.255.52'))))
            folder = json.loads((OLD / 'active-preflight.json').read_text())['folder']
            (pre / 'boots-before.txt').write_bytes((OLD / folder / 'boots-before.txt').read_bytes())
            rec = type('Recorder', (), {})(); rec.folder = root / 'capture'; rec.folder.mkdir()
            match = dict(boot_id=boot, machine_id=plan['machine_id'], config_sha256=plan['candidate_config_sha256'], notes_sha256=plan['candidate_notes_sha256'])
            real_discover = discovery.discover
            authenticate = AsyncMock(return_value=match)
            async def bounded(*args):
                if failure:
                    raise failure
                return await real_discover(*args, probe=AsyncMock(return_value=False), authenticate=authenticate)
            journal = (OLD / 'first-stop-evidence/boots-after.txt').read_text() if histories else ''
            if unexpected:
                journal += '\n 1 ' + 'e' * 32 + ' mock unexpected reboot\n'
            with patch.object(h, 'R', root), patch.object(h, 'PLAN', plan), patch.object(h, 'verify_inputs'), patch.object(h, 'authorized', return_value=True), patch.object(h, 'preflight_folder', return_value=pre), patch.object(h.p, 'Recorder', return_value=rec), patch.object(h, 'wifi_command', return_value=(journal, 0)) as shell, patch.object(discovery, 'discover', side_effect=bounded):
                result = h.admit()
            self.assertEqual(shell.call_count, 1)
            self.assertEqual(authenticate.await_count, 1)
            events = [json.loads(x) for x in (rec.folder / 'discovery.jsonl').read_text().splitlines()]
            matched = next(x for x in events if x['kind'] == 'matched')
            self.assertEqual(matched['boot_id'], boot)
            self.assertNotIn('identity', matched)
            self.assertEqual(json.loads((root / 'mutation-state.json').read_text())['phase'], 'candidate-admitted')
            return result

    def test_actual_flat_discovery_result_reaches_attributed_admission(self):
        r = self.run_admission()
        self.assertEqual(r['boot_id'], AFTER)
        self.assertEqual(r['boot_attribution'], 'attributed')
        self.assertTrue(r['transport']['wifi_authenticated'])

    def test_same_boot_is_not_success(self):
        with self.assertRaisesRegex(ValueError, 'boot did not change'):
            self.run_admission(boot=BEFORE)

    def test_missing_history_stops(self):
        with self.assertRaisesRegex(ValueError, 'missing journal boot list'):
            self.run_admission(histories=False)

    def test_extra_unexplained_boot_stops(self):
        with self.assertRaisesRegex(ValueError, 'boot attribution'):
            self.run_admission(unexpected=True)

    def test_transport_timeout_does_not_reach_admission(self):
        with self.assertRaises(TimeoutError):
            self.run_admission(failure=TimeoutError('mock first timeout'))

    def test_import_is_not_an_execution_scope(self):
        self.assertFalse(self.host.authorized())


if __name__ == '__main__':
    unittest.main()
