"""Test342 separates source5V/Rp capability from actual switching input."""
import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
import test_sm5440_temperature_activation as previous
import test_sm5440_bounded_direct as old
R=Path(__file__).resolve().parents[1]/'reference/boot-tests/test-342-source-capability-observer'
s=importlib.util.spec_from_file_location('g342',R/'guard.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class NativeRegression(previous.PriorGuardTests):
    def setUp(self):
        p=patch.object(previous,'g',g);p.start();self.addCleanup(p.stop);super().setUp()
class CleanupRegression(previous.PriorCleanupTests):
    def setUp(self):
        p=patch.object(previous,'g',g);p.start();self.addCleanup(p.stop);super().setUp()
class ActivationRegression(previous.ActivationTests):
    def setUp(self):
        p=patch.object(previous,'g',g);p.start();self.addCleanup(p.stop)
class CapabilityTests(unittest.TestCase):
    def sample(self,mv=5000000):return previous.ActivationTests().sample(mv)
    def rows(self):return [old.row('Linux boot',0)]
    def test_three_amp_rp_source_is_not_three_amp_actual_input(self):
        s=self.sample();s['tcpm']['POWER_SUPPLY_CURRENT_MAX']='3000000'
        proof=g.preparation_proof(self.rows(),old.BOOT,s,False)
        self.assertTrue(proof['pre_entry']);self.assertFalse(proof['fixed9_restored'])
        self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,s,False,dict(boot_id=old.BOOT,token='token',owner_confirmed_C1=True),'token')
    def test_actual_input_and_source_capability_upper_bounds_still_stop(self):
        for field,value in (('input','1800001'),('input','3000000'),('source','3000001')):
            s=self.sample();s['tcpm']['POWER_SUPPLY_CURRENT_MAX']='3000000'
            if field=='input':s['usb']['POWER_SUPPLY_INPUT_CURRENT_LIMIT']=value
            else:s['tcpm']['POWER_SUPPLY_CURRENT_MAX']=value
            self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,s,False)
    def test_fixed9_caps_and_postentry_strict_restore_are_unchanged(self):
        s=self.sample(9000000)
        for where in ('tcpm','usb'):
            changed=self.sample(9000000);changed[where]['POWER_SUPPLY_CURRENT_MAX' if where=='tcpm' else 'POWER_SUPPLY_INPUT_CURRENT_LIMIT']='1500001'
            self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,changed,False)
        s=self.sample();s['tcpm']['POWER_SUPPLY_CURRENT_MAX']='3000000'
        rows=self.rows()+[old.row('one-shot entry begins: fixed9=1',1000000)]
        self.assertRaises(ValueError,g.validate_cleanup,rows,old.BOOT,1,s['tcpm'],s['usb'])
    def test_rejected_sample_is_saved_before_fault_and_no_bind(self):
        owner=self;events=[]
        class HW:
            token='token';binds=0;stops=0
            def activation(self):return None
            def sample(self):
                s=owner.sample();s['tcpm']['POWER_SUPPLY_CURRENT_MAX']='3000000';s['usb']['POWER_SUPPLY_INPUT_CURRENT_LIMIT']='3000000';return s
            def is_bound(self):return False
            def ready(self):pass
            def bind_once(self):self.binds+=1
            def stop(self):self.stops+=1;return dict(pump_mode=1)
        hw=HW()
        self.assertRaises(ValueError,g.observe,hw,self.rows,lambda *a:events.append(a),old.BOOT)
        self.assertEqual([x[0] for x in events],['preparation-sample','first-failure','cleanup'])
        self.assertEqual(events[0][1]['usb']['POWER_SUPPLY_INPUT_CURRENT_LIMIT'],'3000000')
        self.assertEqual((hw.binds,hw.stops),(0,1))
if __name__=='__main__':unittest.main()
