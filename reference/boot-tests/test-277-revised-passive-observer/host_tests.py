"""Host execution of new runner; no physical commands. Reuse frozen gate tests."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

A = Path(__file__).resolve().parent
sys.path.insert(0, str(A))
import run as runner
OLD = A.parent / 'test-275-passive-fresh-acquisition'
# Keep historical fixture locations and gates; do not rewrite old tests.
spec = importlib.util.spec_from_file_location('frozen275_host_tests', OLD / 'host_tests.py')
old = importlib.util.module_from_spec(spec)
# Old tests use gate.HEADER; the wrapper deliberately exports reviewed parser facts.
import gate
gate.HEADER = gate._gate.HEADER
spec.loader.exec_module(old)
Observer, Baseline = old.Observer, old.Baseline


class Runner(unittest.TestCase):
    def exercise(self, *, completed=False, unload_fail=False, endpoint_fail=False):
        boot = 'a' * 32
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder/'install').mkdir(); (folder/'preflight').mkdir()
            (folder/'install/summary.json').write_text(json.dumps({'verdict':'PAIRED_INSTALLATION_READBACK_VERIFIED'}))
            (folder/'preflight/boots-before.txt').write_text('before')
            record = {'__CURSOR':'cursor', '_BOOT_ID':boot, 'MESSAGE':'boot', 'PRIORITY':'6'}
            raw = json.dumps(record)
            class Recorder:
                def __init__(self, path): self.folder=path; path.mkdir()
                def adb(self, name, command, timeout=15, required=True):
                    calls.append((name, command))
                    if name=='unload': return '', 'timeout' if unload_fail else 0
                    if name=='endpoint-state' and endpoint_fail: raise RuntimeError('ADB unavailable')
                    return raw if name in ('kernel-before-json','kernel-final-json') else 'packet', 0
                def command(self, name, argv, timeout=15, required=True):
                    calls.append((name, argv)); (self.folder/(name+'.txt')).write_text(boot)
                    return boot, 0
                def ps(self, name, script, timeout=30): calls.append((name,script)); return 'ProblemCode : 0',0
            section={'boot':boot,'uptime':'100 100','observer':'cached','kernel':''}
            parsed={'state':1 if completed else 2,'count':8 if completed else 1,'first_refusal':None if completed else 1}
            with patch.object(runner,'A',folder), patch.object(runner.p,'Recorder',Recorder), \
                 patch.object(runner.gate.baseline,'sections',return_value=section), \
                 patch.object(runner.gate,'identity',return_value=(boot,{})), \
                 patch.object(runner.gate,'observer',return_value=parsed), \
                 patch.object(runner.gate,'journal',return_value={}), \
                 patch.object(runner.gate,'wifi_address',return_value='10.0.0.2'), \
                 patch.object(runner.gate.evidence,'attribute',return_value='attributed'):
                runner.run()
            result=json.loads((folder/'observation/summary.json').read_text())
            return calls,result

    def test_refusal_ends_once_and_unloads_with_health_separate(self):
        calls,out=self.exercise()
        self.assertEqual(out['verdict'],'DEVICE_NORMAL_ACQUISITION_REFUSED')
        self.assertTrue(out['unloaded'] and out['endpoint_completed'])
        self.assertFalse(out['full_30s_observed'])
        names=[name for name,_ in calls]
        self.assertEqual(names.count('load-once'),1)
        self.assertEqual(names.count('sample-00'),1)
        self.assertNotIn('sample-01',names)
        self.assertEqual(names.count('unload'),1)
        self.assertLess(names.index('terminal-observer'),names.index('unload'))
        self.assertLess(names.index('unload'),names.index('endpoint-state'))

    def test_eight_calls_separate_from_30s_observation(self):
        _,out=self.exercise(completed=True)
        self.assertEqual(out['verdict'],'DEVICE_NORMAL_EIGHT_FRESH_DELIVERIES')
        self.assertFalse(out['full_30s_observed'])

    def test_unload_failure_never_passes(self):
        _,out=self.exercise(unload_fail=True)
        self.assertEqual(out['verdict'],'STOP_REQUIRES_ANALYSIS')
        self.assertFalse(out['unloaded'])

    def test_endpoint_failure_never_passes(self):
        _,out=self.exercise(endpoint_fail=True)
        self.assertEqual(out['verdict'],'STOP_REQUIRES_ANALYSIS')
        self.assertIn('endpoint_error',out)

    def test_revised_artifact_and_unique_slots_only(self):
        self.assertEqual(runner.PLAN['observer_revision'],'7a887eab')
        self.assertEqual(runner.PLAN['observer_sha256'],'9aafabf63a18ebf31b593c97dd3edc1d0fb43a7348936e10b02f0773e5661582')
        source=(A/'run.py').read_text()
        self.assertEqual(source.count('insmod /tmp/test277-observer.ko'),1)
        self.assertNotIn('test275-observer.ko',source)
        adapter=(A/'module-swap.sh').read_text()
        self.assertIn('.gts9-test277-original',adapter)
        self.assertNotIn('.gts9-test275-original',adapter)

    def test_existing_observation_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary); (folder/'observation').mkdir()
            with patch.object(runner,'A',folder),patch.object(runner.p,'Recorder') as recorder:
                with self.assertRaises(ValueError): runner.run()
                recorder.assert_not_called()


if __name__=='__main__': unittest.main()
