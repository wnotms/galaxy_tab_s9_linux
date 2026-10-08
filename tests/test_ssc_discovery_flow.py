"""Integration of bounded SSH admission and actual SSC sample parsing."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reference/boot-tests/test-365-ssc-discovery'
s=importlib.util.spec_from_file_location('ssc365_flow_tests',R/'host_flow.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
old=importlib.util.spec_from_file_location('early364_fixtures',ROOT/'tests/test_early_adsp_controlled_boot.py');O=importlib.util.module_from_spec(old);old.loader.exec_module(O)


class SSCDiscoveryFlowTests(unittest.TestCase):
    def test_real_cli_measurement_shape(self):
        d=M.sample('Accelerometer sensor measurement: X=-0.221000 Y=9.802000 Z=0.154000 m/s²\n')
        self.assertEqual(d['y'],9.802);self.assertEqual(d['unit'],'m/s²')
    def test_no_measurement_is_pending(self):
        self.assertIsNone(M.sample('QMI discovery timeout; no sensor found'))
    def test_non_finite_measurement_rejected(self):
        with self.assertRaises(ValueError):M.sample('Accelerometer sensor measurement: X=nan Y=0 Z=9.8 m/s²')
    def test_zero_measurement_not_discovery_proof(self):
        with self.assertRaises(ValueError):M.sample('Accelerometer sensor measurement: X=0 Y=0 Z=0 m/s²')
    def test_absurd_measurement_rejected(self):
        with self.assertRaises(ValueError):M.sample('Accelerometer sensor measurement: X=999 Y=0 Z=0 m/s²')
    def packet(self):
        d=O.ControlledBootGateTests().packet();d['network']+='\n2: wlp1s0 inet 10.175.236.65/24';return d
    def recorder(self,folder,results):
        rec=Mock();rec.folder=Path(folder);rec.adb.return_value=(json.dumps(self.packet()),0)
        def command(name,argv,**kw):
            stdout,stderr,code=results.pop(0)
            (rec.folder/(name+'.stderr')).write_text(stderr)
            self.assertIn('ConnectTimeout=5',argv)
            self.assertTrue(kw['timeout']<=12)
            return stdout,code
        rec.command.side_effect=command;return rec
    def with_trust(self):
        trust=Mock();trust.is_symlink.return_value=False;trust.read_text.return_value=M.PLAN['alias']+' '+M.PLAN['host_ed25519_key']+'\n'
        return patch.object(M,'Path',return_value=trust)
    def test_first_banner_failure_then_ready_without_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.packet();reply=M.PLAN['machine_id']+'\n'+d['boot_id']+'\n'
            rec=self.recorder(tmp,[('','Connection timed out during banner exchange',255),(reply,'',0)])
            with self.with_trust(),patch.object(M.ready.time,'sleep'):
                self.assertEqual(M.wifi(rec,'wifi',d),'10.175.236.65')
            record=json.loads((Path(tmp)/'wifi-admission.json').read_text())
            self.assertEqual(record['verdict'],'READY_WITH_RECORDED_TRANSIENT');self.assertFalse(record['reboot_requested'])
            self.assertEqual(rec.command.call_count,2);self.assertEqual(rec.adb.call_count,3)
    def test_wrong_key_stops_single_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=self.recorder(tmp,[('','Host key verification failed',255)])
            with self.with_trust():
                with self.assertRaises(M.ready.ReadinessError):M.wifi(rec,'wifi',self.packet())
            self.assertEqual(rec.command.call_count,1)
    def test_boot_change_during_admission_stops_before_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.packet();rec=self.recorder(tmp,[]);bad=dict(d,boot_id='22222222-2222-2222-2222-222222222222');rec.adb.return_value=(json.dumps(bad),0)
            with self.with_trust():
                with self.assertRaises(M.ready.ReadinessError):M.wifi(rec,'wifi',d)
            rec.command.assert_not_called()
    def test_boot_image_is_exact_reused_qualification(self):
        source=json.loads((R.parent/'test-364-early-adsp-socinfo/PACKAGE.json').read_text())
        for n in ('boot.img','vendor_boot.img','modules-x710.tar.gz'):
            self.assertEqual(M.PACKAGE['artifacts'][n],source['artifacts'][n])
        self.assertFalse(M.PLAN['PPS']);self.assertFalse(M.PLAN['pump_ON'])


if __name__=='__main__':unittest.main()
