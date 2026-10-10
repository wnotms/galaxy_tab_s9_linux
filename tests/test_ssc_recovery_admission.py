import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ssc_recovery_admission',ROOT/'scripts/ssc-recovery-admission.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
BOOT='11111111-1111-1111-1111-111111111111'

def raw(uptime=30,boot=BOOT):
    return 'gts9wifi\n5.15.94-Foldiby-+\n0\n'+boot+'\n'+str(uptime)+' 2.1\n'

class RecoveryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.rec=Mock();self.rec.folder=Path(self.tmp.name)
        self.rec.host_adb.return_value=('recovery\n',0)
        self.rec.adb.side_effect=[(raw(u),0) for u in (30,34,38)]
        self.seconds=0
    def clock(self):return self.seconds
    def sleep(self,seconds):self.seconds+=seconds
    def run_gate(self):return H.admit(self.rec,clock=self.clock,sleep=self.sleep)
    def test_three_same_boot_root_snapshots_over_eight_seconds(self):
        result=self.run_gate();self.assertEqual(result['seconds'],8)
        self.assertFalse(result['mutation']);self.assertEqual(len(result['samples']),3)
        self.assertEqual(self.rec.host_adb.call_count,3);self.assertEqual(self.rec.adb.call_count,3)
    def test_first_closed_shell_stops_no_failed_command_retry(self):
        self.rec.adb.side_effect=OSError('closed')
        with self.assertRaises(OSError):self.run_gate()
        names=[x.args[0] for x in self.rec.adb.call_args_list]
        self.assertEqual(names,['recovery-stable-shell-00','recovery-fault-kernel'])
    def test_second_sample_failure_never_calls_third(self):
        self.rec.adb.side_effect=[(raw(),0),OSError('closed'),('',1)]
        with self.assertRaises(OSError):self.run_gate()
        self.assertNotIn('recovery-stable-shell-02',[x.args[0] for x in self.rec.adb.call_args_list])
    def test_debian_device_state_is_rejected(self):
        self.rec.host_adb.return_value=('device\n',0)
        with self.assertRaises(ValueError):self.run_gate()
    def test_recovery_reboot_stops(self):
        self.rec.adb.side_effect=[(raw(),0),(raw(34,'22222222-2222-2222-2222-222222222222'),0),('',0)]
        with self.assertRaisesRegex(ValueError,'reboot'):self.run_gate()
    def test_uptime_goes_backwards(self):
        self.rec.adb.side_effect=[(raw(),0),(raw(29),0),('',0)]
        with self.assertRaises(ValueError):self.run_gate()
    def test_frozen_uptime_not_a_stability_pass(self):
        self.rec.adb.side_effect=[(raw(),0)]*4
        with self.assertRaises(ValueError):self.run_gate()
    def test_slow_gate_fails_deadline(self):
        self.sleep=lambda _:setattr(self,'seconds',self.seconds+31)
        with self.assertRaises(TimeoutError):self.run_gate()
    def test_no_sleep_under_mutation_or_module_lock(self):
        self.run_gate()
        for call in self.rec.adb.call_args_list:self.assertEqual(call.args[1],H.COMMAND)
    def test_wrong_kernel_device_uid_and_boot(self):
        for text in [raw().replace('gts9wifi','gts9ultra'),raw().replace('5.15.94-Foldiby-+','7.2.0'),raw().replace('\n0\n','\n1000\n'),raw().replace(BOOT,'not-a-boot')]:
            with self.assertRaises(ValueError):H.parse(text)
    def test_invalid_or_nonfinite_uptime(self):
        for value in (-1,'nan','inf','bad'):
            with self.assertRaises(ValueError):H.parse(raw(value))
    def test_malformed_shell_fails(self):
        for text in ('',raw()+'extra\n',raw().replace('\n0\n','\n')):
            with self.assertRaises(ValueError):H.parse(text)
    def test_crlf_native_adb_output(self):self.assertEqual(H.parse(raw().replace('\n','\r\n'))['boot_id'],BOOT)
    def test_failed_optional_evidence_cannot_replace_first_error(self):
        self.rec.host_adb.side_effect=OSError('state-closed')
        self.rec.adb.side_effect=OSError('evidence-closed')
        with self.assertRaisesRegex(OSError,'state-closed'):self.run_gate()
        self.assertTrue((self.rec.folder/'recovery-kernel-error.json').exists())
    def test_existing_fault_evidence_is_never_overwritten_or_requeried(self):
        (self.rec.folder/'recovery-fault-devices.txt').write_text('first raw devices')
        (self.rec.folder/'recovery-kernel-error.json').write_text('first kernel error')
        H.capture_fault(self.rec)
        self.rec.host_adb.assert_not_called();self.rec.adb.assert_not_called()
        self.assertEqual((self.rec.folder/'recovery-fault-devices.txt').read_text(),'first raw devices')

if __name__=='__main__':unittest.main()
