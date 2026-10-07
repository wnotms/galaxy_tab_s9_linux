"""Test339 guardian: primary/cleanup separation and phase-bound cleanup."""
import importlib.util, unittest
from pathlib import Path
from unittest.mock import patch
import test_sm5440_bounded_direct as old
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('guard339',ROOT/'reference/boot-tests/test-339-preentry-detach-wait/guard.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class GuardRegressionTests(old.BoundedGuardianTests):
    def setUp(self):
        p=patch.object(old,'g',g);p.start();self.addCleanup(p.stop)
class CleanupTests(unittest.TestCase):
    def source(self,online=0,mv=0,limit=0):
        return dict(POWER_SUPPLY_ONLINE=str(online),POWER_SUPPLY_VOLTAGE_NOW=str(mv),POWER_SUPPLY_CURRENT_MAX=str(limit))
    def usb(self,online=0,limit=100000):
        return dict(POWER_SUPPLY_ONLINE=str(online),POWER_SUPPLY_INPUT_CURRENT_LIMIT=str(limit))
    def rows(self,entered=False,cleanup=0,lease=0):
        rows=[old.row('Linux boot',0)]
        if entered:rows.append(old.row('one-shot entry begins: fixed9=1',1000000))
        rows.append(old.row(f'one-shot pump stopped: primary=-61 cleanup={cleanup} lease={lease} no_restart=1',2000000))
        return rows
    def test_known_preentry_offline_and_pc5_or_fixed9(self):
        for online,mv,ma in ((0,0,0),(1,5000000,1800000),(1,9000000,1500000)):
            d=g.validate_cleanup(self.rows(),old.BOOT,1,self.source(online,mv,ma),self.usb(online,ma or 100000))
            self.assertTrue(d['pre_entry']);self.assertFalse(d['fixed9_restored'])
    def test_entry_requires_fixed9_even_without_pump_start(self):
        for online,mv,ma in ((0,0,0),(1,5000000,1800000),(2,8940000,1800000)):
            self.assertRaises(ValueError,g.validate_cleanup,self.rows(True),old.BOOT,1,self.source(online,mv,ma),self.usb(online,ma or 100000))
        self.assertTrue(g.validate_cleanup(self.rows(True),old.BOOT,1,self.source(1,9000000,1500000),self.usb(1,1500000))['fixed9_restored'])
    def test_unknown_journal_lease_cleanup_mode_and_pps_fail_closed(self):
        for rows in ([],self.rows()[1:],self.rows(cleanup=-5),self.rows(lease=7),[dict(old.row('boot',0),_BOOT_ID='b'*32)]):
            self.assertRaises(ValueError,g.validate_cleanup,rows,old.BOOT,1,self.source(),self.usb())
        self.assertRaises(ValueError,g.validate_cleanup,self.rows(),old.BOOT,4,self.source(),self.usb())
        self.assertRaises(ValueError,g.validate_cleanup,self.rows(),old.BOOT,1,self.source(2,8940000,1800000),self.usb(1,1800000))
    def test_primary_native_failure_is_not_masked_by_cleanup(self):
        class HW:
            def stop(self):raise ValueError('fixed9 not restored')
        events=[]
        rows=self.rows()
        with self.assertRaises(g.CleanupFailure) as cm:
            g.observe(HW(),lambda:rows,lambda *a:events.append(a),old.BOOT)
        self.assertIn('one-shot pump stopped',cm.exception.primary_error)
        self.assertIn('fixed9 not restored',cm.exception.cleanup_error)
        self.assertEqual([e[0] for e in events],['first-failure','cleanup-failure'])
    def test_cleanup_error_does_not_invent_primary(self):
        error=g.CleanupFailure(None,ValueError('cleanup'))
        self.assertIsNone(error.primary_error);self.assertIn('cleanup',error.cleanup_error)
if __name__=='__main__':unittest.main()
