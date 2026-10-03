"""Test313 actual runner, ADC gate and unconditional accepted311 restoration."""
from unittest import mock
import unittest
import json

import test_sm5440_condition_device_runner as parent
import test_sm5440_condition_device_gate as evidence
import test_sm5714_ordinary_device_runner as ordinary
import test_sm5714_serial_device_acceptance as serial

R=parent.ROOT/'reference/boot-tests/test-313-adc-condition-comparison'
m=parent.load('condition313_runner',R/'host_flow.py')
b=parent.load('condition313_package',R/'build_package.py')
c=parent.load('condition313_controls',R/'read-controls.py')

class Runner:
    def setUp(self):
        ctx=mock.patch.object(parent,'m',m);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

class IdentityTests(Runner,parent.IdentityTests):
    def test_baseline_is_accepted311_not_old299(self):
        self.assertEqual(m.PLAN['baseline_config_sha256'],'55365a030f56ecddf77322a202790842d0d41a0cf5df2ed2812369ce75af8d89')
        self.assertEqual(m.PACKAGE['baseline_partitions']['boot'],'f4efa07e88ca3bc012b373827529fe4f92f35105e0040623da6486f1509fdacb')
        self.assertEqual(m.PACKAGE['kernel_qualification'],'Test312')

class LifecycleTests(Runner,parent.LifecycleTests):pass
class PartitionAndStageTests(Runner,parent.PartitionAndStageTests):pass

class AdmissionTests(Runner,parent.AdmissionTests):
    def adb(self,name,script,**kwargs):
        if name=='program-controls':
            self.calls.append(name)
            return json.dumps(ordinary.registers()),0
        return super().adb(name,script,**kwargs)

    def test_controls_and_thermal_precede_one_history_query(self):
        self.admit()
        self.assertLess(self.calls.index('program-controls'),self.calls.index('kernel-json'))
        self.assertLess(self.calls.index('thermal'),self.calls.index('kernel-json'))
        self.assertLess(self.calls.index('kernel-json'),self.calls.index('boots-after'))
        history=[x for x in self.rec.adb.call_args_list if x.args[0]=='boots-after']
        self.assertEqual(len(history),1);self.assertEqual(history[0].kwargs['timeout'],20)

    def test_bad_switching_controls_stop_before_history(self):
        with mock.patch.object(m,'controls',side_effect=ValueError('Q4 mismatch')):
            with self.assertRaisesRegex(ValueError,'Q4 mismatch'):self.admit()
        self.assertNotIn('boots-after',self.calls)

    def test_missing_history_does_not_accept_or_reissue_conversion(self):
        original=self.adb
        def fail(name,script,**kwargs):
            if name=='boots-after':
                self.calls.append(name);raise TimeoutError('history absent')
            return original(name,script,**kwargs)
        self.rec.adb.side_effect=fail
        with self.assertRaises(TimeoutError):self.admit()
        self.assertEqual(self.calls.count('boots-after'),1)
        self.assertTrue((self.folder/'journal-classification.json').is_file())
        self.sleep.assert_not_called()

class Gate:
    def setUp(self):
        ctx=mock.patch.object(evidence,'m',m.gate);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()
class ConditionEvidenceTests(Gate,evidence.ConditionEvidenceTests):pass
class BatteryEntryTests(Gate,evidence.BatteryEntryTests):pass

class ProviderTests(serial.ProviderTests):
    def setUp(self):
        ctx=mock.patch.object(serial,'c',c);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

class PreflightTests(ordinary.PreflightTests):
    def setUp(self):
        ctx=mock.patch.object(ordinary,'m',m);ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(m,'controls',return_value={'verdict':'fixture_verified'});ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

class PackageTests(parent.PackageTests):
    def setUp(self):
        ctx=mock.patch.object(parent,'b',b);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

if __name__=='__main__':unittest.main()
