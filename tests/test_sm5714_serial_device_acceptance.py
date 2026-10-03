"""Test311 executes the serial host collector, preserving all device gates."""
from pathlib import Path
from unittest import mock
import unittest

import test_sm5714_provider_acceptance as parent

R=parent.ROOT/'reference/boot-tests/test-311-serial-device-acceptance'
m=parent.load('serial311_runner',R/'host_flow.py')
c=parent.load('serial311_controls',R/'read-controls.py')

class NewRunner:
    def setUp(self):
        ctx=mock.patch.object(parent,'m',m);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

class ProviderTests(parent.ProviderTests):
    def setUp(self):
        ctx=mock.patch.object(parent,'c',c);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

class GateTests(NewRunner,parent.GateTests):pass
class LifecycleTests(NewRunner,parent.LifecycleTests):pass
class PreflightTests(NewRunner,parent.PreflightTests):pass

class AdmissionTests(NewRunner,parent.AdmissionTests):
    def test_controls_thermal_kernel_precede_single_history_and_host_probes(self):
        result,_=m.admission(self.folder,'candidate',self.before,self.boots_before)
        self.assertEqual(result['program_controls']['input_limit_ma'],500)
        self.assertLess(self.calls.index('thermal'),self.calls.index('kernel-json'))
        self.assertLess(self.calls.index('program-controls'),self.calls.index('kernel-json'))
        self.assertLess(self.calls.index('kernel-json'),self.calls.index('boots-after'))
        history=[call for call in self.rec.adb.call_args_list if call.args[0]=='boots-after']
        self.assertEqual(len(history),1);self.assertEqual(history[0].kwargs['timeout'],20)
        self.assertEqual(self.rec.command.call_count,1)
        self.sleep.assert_not_called()

    def test_missing_history_still_refuses_after_preserving_primary_device_checks(self):
        original=self.adb
        def fail(name,script,**kwargs):
            if name=='boots-after':
                self.calls.append(name);raise TimeoutError('history missing')
            return original(name,script,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaises(TimeoutError):m.admission(self.folder,'candidate',self.before,self.boots_before)
        self.assertIn('program-controls',self.calls);self.assertIn('thermal',self.calls)
        self.assertEqual(self.calls.count('boots-after'),1)
        self.rec.ps.assert_not_called();self.rec.command.assert_not_called()
        self.assertTrue((self.folder/'journal-classification.json').is_file())

    def test_bad_controls_stop_before_global_history_or_host_probes(self):
        original=self.adb
        def fail(name,script,**kwargs):
            if name=='program-controls':
                self.calls.append(name);raise ValueError('unsafe Q4')
            return original(name,script,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaises(ValueError):m.admission(self.folder,'candidate',self.before,self.boots_before)
        self.assertNotIn('boots-after',self.calls)
        self.rec.ps.assert_not_called();self.rec.command.assert_not_called()

if __name__=='__main__':unittest.main()
