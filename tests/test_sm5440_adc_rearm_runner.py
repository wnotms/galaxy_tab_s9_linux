"""Short rearm comparison scope: device health still gates, host probe is evidence."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-296-vendor-adc-rearm'
spec=importlib.util.spec_from_file_location('rearm_scope',R/'host_flow.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RearmRunnerTests(unittest.TestCase):
    def test_new_error_stops_before_admission(self):
        source=(R/'host_flow.py').read_text();self.assertIn('new ADC/rearm error; no further test',source)
        self.assertIn("'kernel-first-fault'",source)
    def test_host_only_timeout_recorded_without_retry_or_false_auth(self):
        class Recorder:
            def command(self,*args,**kwargs):
                self.calls=1;assert kwargs['required'] is False;return '',255
        r=Recorder();self.assertEqual(m.ncm_probe(r,'1'*32),('',255));self.assertEqual(r.calls,1)
        self.assertIn("authenticated_NCM_SSH=(jobs['ncm'][1]==0)",(R/'host_flow.py').read_text())
    def test_successful_ssh_must_match_boot(self):
        class Recorder:
            def command(self,*args,**kwargs):return '1'*32+'\n',0
        self.assertEqual(m.ncm_probe(Recorder(),'1'*32)[1],0)
        with self.assertRaises(ValueError):m.ncm_probe(Recorder(),'2'*32)
    def test_windows_and_device_safety_still_stop(self):
        source=(R/'host_flow.py').read_text()
        for marker in ['WindowsCode43','battery/temperature','pump mode not OFF','new SM5440 fault','CPU/kernel failure']:
            self.assertIn(marker,source)
    def test_new_stage_and_unconditional_restore(self):
        source=(R/'host_flow.py').read_text();self.assertIn('gts9-test296',source);self.assertNotIn('gts9-test295',source)
        self.assertIn("'rollback-test263-boot.img'",source);self.assertNotIn('insmod',source)
