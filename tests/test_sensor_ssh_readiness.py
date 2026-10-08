"""Mock network/device health, including first Test364 banner failure."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('sensor_readiness',ROOT/'userspace/sensors/ssh_readiness.py')
M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
MID='a'*32
BOOT='11111111-1111-1111-1111-111111111111'
OK=dict(status=0,stdout=MID+'\n'+BOOT+'\n',stderr='')
TIMEOUT=dict(status=255,stdout='',stderr='Connection timed out during banner exchange\nConnection to UNKNOWN port 65535 timed out\n')


class SensorSSHReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tick=0
        self.device=Mock(return_value=BOOT)
    def clock(self):return self.tick
    def pause(self,n):self.tick+=n
    def run_gate(self,probe,**kwargs):
        return M.admit(probe,self.device,machine_id=MID,boot_id=BOOT,clock=self.clock,pause=self.pause,**kwargs)

    def test_first_ready(self):
        probe=Mock(return_value=OK);d=self.run_gate(probe)
        self.assertEqual(d['verdict'],'READY');self.assertFalse(d['reboot_requested'])
        self.assertEqual(probe.call_count,1);self.assertEqual(self.device.call_count,2)
    def test_test364_banner_failure_retained_then_same_boot_recovers(self):
        probe=Mock(side_effect=[TIMEOUT,OK]);d=self.run_gate(probe)
        self.assertEqual(d['verdict'],'READY_WITH_RECORDED_TRANSIENT')
        self.assertEqual(d['first_failure']['stderr'],TIMEOUT['stderr'])
        self.assertEqual(len(d['attempts']),2);self.assertEqual(self.device.call_count,3)
    def test_attempts_exhausted_stops(self):
        probe=Mock(return_value=TIMEOUT)
        with self.assertRaises(M.ReadinessError) as ctx:self.run_gate(probe)
        self.assertEqual(probe.call_count,3);self.assertEqual(len(ctx.exception.summary['attempts']),3)
    def test_changed_key_no_retry(self):
        probe=Mock(return_value=dict(status=255,stdout='',stderr='Host key verification failed. Connection timed out'))
        with self.assertRaises(M.ReadinessError):self.run_gate(probe)
        self.assertEqual(probe.call_count,1)
    def test_unknown_error_no_retry(self):
        probe=Mock(return_value=dict(status=255,stdout='',stderr='broken pipe'))
        with self.assertRaises(M.ReadinessError):self.run_gate(probe)
        self.assertEqual(probe.call_count,1)
    def test_unclassified_exception_no_retry(self):
        probe=Mock(side_effect=OSError('local executable missing'))
        with self.assertRaises(M.ReadinessError):self.run_gate(probe)
        self.assertEqual(probe.call_count,1)
    def test_wrong_peer_stops(self):
        with self.assertRaises(M.ReadinessError):self.run_gate(Mock(return_value=dict(OK,stdout='b'*32+'\n'+BOOT+'\n')))
    def test_boot_changes_between_attempts(self):
        self.device.side_effect=[BOOT,'22222222-2222-2222-2222-222222222222']
        probe=Mock(return_value=TIMEOUT)
        with self.assertRaises(M.ReadinessError):self.run_gate(probe)
        self.assertEqual(probe.call_count,1)
    def test_boot_changes_after_success(self):
        self.device.side_effect=[BOOT,'22222222-2222-2222-2222-222222222222']
        with self.assertRaises(M.ReadinessError):self.run_gate(Mock(return_value=OK))
    def test_lost_device_after_banner_timeout(self):
        self.device.side_effect=[BOOT,ValueError('battery temp invalid')]
        probe=Mock(return_value=TIMEOUT)
        with self.assertRaises(M.ReadinessError):self.run_gate(probe)
        self.assertEqual(probe.call_count,1)
    def test_deadline_stops_before_another_probe(self):
        def delayed(remaining):self.tick+=remaining;return TIMEOUT
        probe=Mock(side_effect=delayed)
        with self.assertRaises(M.ReadinessError):self.run_gate(probe,seconds=3)
        self.assertEqual(probe.call_count,1)
    def test_late_success_not_admitted(self):
        def late(remaining):self.tick+=remaining;return OK
        with self.assertRaises(M.ReadinessError):self.run_gate(late,seconds=3)
    def test_post_probe_read_also_bound(self):
        def health(remaining):
            if self.device.call_count==2:self.tick+=remaining
            return BOOT
        self.device.side_effect=health
        with self.assertRaises(M.ReadinessError):self.run_gate(Mock(return_value=OK),seconds=3)
    def test_host_timeout_unknown_not_masked(self):
        probe=Mock(return_value=dict(status='timeout',stdout='',stderr='Connection timed out'))
        with self.assertRaises(M.ReadinessError):self.run_gate(probe)
        self.assertEqual(probe.call_count,1)
    def test_invalid_bounds(self):
        for d in (dict(max_attempts=4),dict(seconds=91),dict(seconds=0)):
            with self.assertRaises(ValueError):self.run_gate(Mock(),**d)


if __name__=='__main__':unittest.main()
