"""Test340 manual handoff is OFF/unbound, sole activation requires fixed9."""
import copy, importlib.util, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import test_sm5440_bounded_direct as old
import test_sm5440_preentry_guard as previous
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-340-confirmed-source-activation'
s=importlib.util.spec_from_file_location('g340',R/'guard.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class PriorGuardTests(old.BoundedGuardianTests):
    def setUp(self):
        p=patch.object(old,'g',g);p.start();self.addCleanup(p.stop)
class PriorCleanupTests(previous.CleanupTests):
    def setUp(self):
        p=patch.object(previous,'g',g);p.start();self.addCleanup(p.stop)
class ActivationTests(unittest.TestCase):
    def sample(self,mv=5000000):
        s=old.sample(False);s['registers']={0x10:1};s['usb']=dict(POWER_SUPPLY_ONLINE='1',POWER_SUPPLY_INPUT_CURRENT_LIMIT='1800000' if mv==5000000 else '1500000')
        s['roles']=['sink','device'];s['pack_mode']='enabled';s['pack_temp']=int(s['battery']['POWER_SUPPLY_TEMP'])
        s['tcpm'].update(POWER_SUPPLY_ONLINE='1',POWER_SUPPLY_VOLTAGE_NOW=str(mv),POWER_SUPPLY_CURRENT_MAX='1800000' if mv==5000000 else '1500000')
        return s
    def rows(self):return [old.row('Linux boot',0)]
    def marker(self):return dict(boot_id=old.BOOT,token='unique',owner_confirmed_C1=True)
    def test_manual_wait_accepts_pc_offline_fixed9_only_off_unbound(self):
        for mv in (5000000,9000000):self.assertTrue(g.preparation_proof(self.rows(),old.BOOT,self.sample(mv),False)['pre_entry'])
        s=self.sample();s['usb']['POWER_SUPPLY_ONLINE']='0';s['tcpm'].update(POWER_SUPPLY_ONLINE='0',POWER_SUPPLY_VOLTAGE_NOW='0')
        self.assertTrue(g.preparation_proof(self.rows(),old.BOOT,s,False)['pre_entry'])
    def test_activation_requires_marker_fixed9_roles_thermal_and_off(self):
        self.assertTrue(g.preparation_proof(self.rows(),old.BOOT,self.sample(9000000),False,self.marker(),'unique')['pre_entry'])
        for mv in (5000000,8940000):self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,self.sample(mv),False,self.marker(),'unique')
        for key,value in (('boot_id','b'*32),('token','stale'),('owner_confirmed_C1',False)):
            m=self.marker();m[key]=value;self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,self.sample(9000000),False,m,'unique')
        for key,value in (('roles',['sink','host']),('pack_temp',999),('pack_mode','disabled')):
            s=self.sample(9000000);s[key]=value;self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,s,False,self.marker(),'unique')
    def test_prior_entry_stop_fault_missing_journal_or_bound_forbid_reprobe(self):
        for rows in ([],[old.row('late',9000000)],self.rows()+[old.row('one-shot entry begins: fixed9=1',1000000)],self.rows()+[old.row('one-shot pump stopped: primary=-110 cleanup=0 lease=0 no_restart=1',1000000)],self.rows()+[old.row('I2C timeout',1000000)]):
            self.assertRaises(ValueError,g.preparation_proof,rows,old.BOOT,self.sample(9000000),False,self.marker(),'unique')
        self.assertRaises(ValueError,g.preparation_proof,self.rows(),old.BOOT,self.sample(9000000),True,self.marker(),'unique')
    def test_wait_does_not_bind_without_confirmation_then_binds_exactly_once(self):
        owner=self
        class Clock:
            now=0
            def __call__(self):return self.now
            def sleep(self,n):self.now+=n
        clock=Clock()
        class HW:
            token='unique';binds=0;readies=0
            def activation(self):return owner.marker() if clock.now>=610 else None
            def sample(self):return owner.sample(9000000 if clock.now>=610 else 5000000)
            def is_bound(self):return False
            def ready(self):self.readies+=1
            def bind_once(self):self.binds+=1
        hw=HW();g.await_activation(hw,self.rows,lambda *a:None,old.BOOT,clock,clock.sleep)
        self.assertEqual((hw.binds,hw.readies,clock.now),(1,1,610))
    def test_bind_failure_and_handoff_timeout_stop_with_cleanup_no_retry(self):
        owner=self
        for kind in ('bind-error','timeout','i2c-error'):
            class Clock:
                now=0
                def __call__(self):return self.now
                def sleep(self,n):self.now+=n
            clock=Clock()
            class HW:
                token='unique';binds=0;stops=0
                def activation(self):return owner.marker() if kind=='bind-error' else None
                def sample(self):
                    if kind=='i2c-error':raise OSError('I2C timeout')
                    return owner.sample(9000000)
                def is_bound(self):return False
                def ready(self):pass
                def bind_once(self):self.binds+=1;raise RuntimeError('bind failed')
                def stop(self):self.stops+=1;return dict(pump_mode=1)
            hw=HW()
            self.assertRaises(Exception,g.observe,hw,self.rows,lambda *a:None,old.BOOT,clock,clock.sleep)
            self.assertEqual(hw.stops,1);self.assertEqual(hw.binds,1 if kind=='bind-error' else 0)
    def test_exclusive_activation_witness_survives_failed_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            hw=g.Hardware.__new__(g.Hardware);hw.out=Path(tmp)
            with patch.object(g.subprocess,'run',side_effect=RuntimeError('bind failed')) as run:
                self.assertRaises(RuntimeError,hw.bind_once)
                self.assertRaises(FileExistsError,hw.bind_once)
                self.assertEqual(run.call_count,1)
    def test_sysfs_role_selection(self):
        self.assertEqual(g.selected_role('source [sink]'),'sink');self.assertEqual(g.selected_role('[device] host'),'device')
if __name__=='__main__':unittest.main()
