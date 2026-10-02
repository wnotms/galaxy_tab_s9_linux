#!/usr/bin/env python3
"""Portable wrapper tests with all hardware/process operations mocked."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

A=Path(__file__).resolve().parent
sys.path[:0]=[str(A),str(A.parent/'test-280-passive-fresh-trace'),str(A.parent/'test-279-fresh-trace-collector-offline'),str(A.parent/'test-263-sm5440-adc-snapshot/attempt-01')]
import device_ops
import health_gate
import coordinator


class Wrapper(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        base=A.parent/'test-277-revised-passive-observer'
        self.raw=(base/'observation/before-load-state.txt').read_text()
        plan=json.loads((base/'registration.json').read_text())
        boot=health_gate.sections(self.raw)['boot'].strip().replace('-','')
        self.packet=dict(plan,test='Test282',verdict='READY_FOR_REGISTERED_PASSIVE_TRACE',boot_id=boot,
                         paired_install_verified=True,health_rescue_verified=True)
        self.ops=device_ops.DeviceOps(Path(self.tmp.name)/'commands',A.parents[2]/'out/sm5440-fresh-observer-276/sm5440-fresh-observer.ko',self.packet)
        self.clock=health_gate.sections(self.raw)['boot'].strip()

    def verify(self,raw=None,loaded=False):
        with patch.object(self.ops,'command',return_value=self.raw if raw is None else raw),\
             patch.object(self.ops,'boot',return_value=self.clock),\
             patch.object(device_ops,'LOADED',Mock(exists=Mock(return_value=loaded))),\
             patch.object(device_ops,'RESULT',Mock(exists=Mock(return_value=False))):
            return self.ops.verified_identity()

    def test_valid_live_identity(self):
        result=self.verify()
        self.assertTrue(result['normal_cmdline_verified'] and result['observer_absent'])
        self.assertEqual(result['observer_sha256'],coordinator.OBSERVER_SHA256)

    def test_old_registration(self):
        self.packet['test']='Test280'
        with self.assertRaisesRegex(ValueError,'unaccepted'):self.verify()

    def test_preflight_stop(self):
        self.packet['verdict']='STOP'
        with self.assertRaisesRegex(ValueError,'unaccepted'):self.verify()

    def test_pairing_unknown(self):
        self.packet['paired_install_verified']=False
        with self.assertRaisesRegex(ValueError,'unverified'):self.verify()

    def test_old_observer_hash(self):
        self.packet['observer_sha256']='old'
        with self.assertRaisesRegex(ValueError,'observer identity'):self.verify()

    def test_preloaded_module(self):
        with self.assertRaisesRegex(ValueError,'already present'):self.verify(loaded=True)

    def test_cmdline_changed(self):
        with self.assertRaisesRegex(ValueError,'runtime cmdline'):
            self.verify(self.raw.replace('pdic_param_lpcharge=0','pdic_param_lpcharge=1'))

    def test_notes_changed(self):
        with self.assertRaisesRegex(ValueError,'config/notes'):
            self.verify(self.raw.replace(self.packet['candidate_notes_sha256'],'0'*64))

    def test_pump_not_off(self):
        with self.assertRaisesRegex(ValueError,'pump not OFF'):
            self.verify(self.raw.replace('sample_mode_before=0x01','sample_mode_before=0x05'))

    def test_battery_temperature_refused(self):
        with self.assertRaisesRegex(ValueError,'temperature'):
            self.verify(self.raw.replace('POWER_SUPPLY_TEMP='+health_gate.props(health_gate.sections(self.raw)['battery'])['POWER_SUPPLY_TEMP'],'POWER_SUPPLY_TEMP=420',1))

    def test_load_is_recorded_once_with_requested_timeout(self):
        completed=subprocess.CompletedProcess(['insmod'],0,b'',b'')
        with patch.object(device_ops.subprocess,'run',return_value=completed) as run:
            self.ops.load(5)
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.kwargs['timeout'],5)
        record=json.loads(next(self.ops.folder.glob('*.json')).read_text())
        self.assertEqual(record['argv'][0],'/sbin/insmod')
        self.assertEqual(record['status'],0)

    def test_unknown_load_timeout_preserves_raw_and_no_retry(self):
        exc=subprocess.TimeoutExpired(['insmod'],5,output=b'partial',stderr=b'blocked')
        with patch.object(device_ops.subprocess,'run',side_effect=exc) as run:
            with self.assertRaisesRegex(RuntimeError,'timeout'):self.ops.load(5)
        self.assertEqual(run.call_count,1)
        self.assertEqual(next(self.ops.folder.glob('*.txt')).read_bytes(),b'partial')
        self.assertEqual(json.loads(next(self.ops.folder.glob('*.json')).read_text())['status'],'timeout')

    def test_unload_checks_absence(self):
        with patch.object(device_ops,'LOADED',Mock(exists=Mock(side_effect=[True,False]))),\
             patch.object(device_ops,'RESULT',Mock(exists=Mock(return_value=False))),\
             patch.object(self.ops,'command') as command:
            self.ops.unload(10)
        command.assert_called_once_with('rmmod-once',['/sbin/rmmod','sm5440_fresh_observer'],10)

    def test_unload_does_not_hide_remaining_module(self):
        with patch.object(device_ops,'LOADED',Mock(exists=Mock(return_value=True))),\
             patch.object(self.ops,'command'):
            with self.assertRaisesRegex(ValueError,'remain'):self.ops.unload(10)

    def test_cache_read_cannot_issue_process_or_request(self):
        with patch.object(device_ops,'RESULT',Mock(read_text=Mock(return_value='cached'))) as result,\
             patch.object(self.ops,'command') as command:
            self.assertEqual(self.ops.cached_result(),'cached')
        result.read_text.assert_called_once();command.assert_not_called()

    def test_portable_gate_functions_ast_equal(self):
        dest=ast.parse((A/'health_gate.py').read_text())
        for name,source in [('identity','test-275-passive-fresh-acquisition'),('sections','test-271-baseline-passive-startup'),('props','test-271-baseline-passive-startup'),('battery_entry','test-271-baseline-passive-startup'),('diagnostic_sample','test-271-baseline-passive-startup')]:
            original=ast.parse((A.parent/source/'gate.py').read_text())
            a=next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in dest.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a),ast.dump(b))

    def test_module_adapter_only_changes_owned_namespace(self):
        old=(A.parent/'test-277-revised-passive-observer/module-swap.sh').read_text()
        new=(A/'module-swap.sh').read_text()
        self.assertEqual(new,old.replace('Test277','Test282').replace('test277','test282'))
        self.assertIn('.gts9-test282-original',new)
        self.assertIn('.gts9-test282-tested',new)

    def test_staged_kernel_and_observer_identity_reused(self):
        pkg=json.loads((A/'PACKAGE.json').read_text())
        self.assertEqual(pkg['write_partitions'],['boot'])
        self.assertFalse(pkg['build_executed'])
        self.assertEqual(pkg['observer']['sha256'],coordinator.OBSERVER_SHA256)
        self.assertEqual(pkg['baseline_partitions']['boot'],'cc31efa00efa6ae2e27b2229c584ccaba9541d398366c87a0ac0ee344f2237e6')


if __name__=='__main__':unittest.main(verbosity=2)
