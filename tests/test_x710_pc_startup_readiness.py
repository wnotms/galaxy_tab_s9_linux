"""Same-boot delayed Wi-Fi and exact transport command tests; no device access."""
import importlib.util,json,unittest
from pathlib import Path
from test_x710_pc_budget_acceptance import source,packet,BOOT
R=Path(__file__).resolve().parents[1]/'reference/boot-tests/test-323-pc-source-budget'
spec=importlib.util.spec_from_file_location('pc323_host_tests',R/'host_flow.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

class ReadinessTests(unittest.TestCase):
    def setUp(self):self.sec=dict(services='active\nactive\nactive\n',network='14: usb0    inet 169.254.42.1/16\n15: wlp1s0    inet 10.139.153.254/24\n')
    def test_ready(self):self.assertTrue(h.gate.debian_ready(self.sec,0))
    def test_delayed_wifi(self):
        self.sec['network']='14: usb0    inet 169.254.42.1/16\n'
        self.assertFalse(h.gate.debian_ready(self.sec,0))
    def test_no_usb(self):
        self.sec['network']='15: wlp1s0    inet 10.139.153.254/24\n'
        self.assertFalse(h.gate.debian_ready(self.sec,0))
    def test_inactive_service(self):
        self.sec['services']='active\ninactive\nactive\n';self.assertFalse(h.gate.debian_ready(self.sec,0))
    def test_transport_error(self):self.assertFalse(h.gate.debian_ready(self.sec,1))
    def test_exact_source_argv(self):
        class Recorder:
            folder=Path('/tmp')
            def adb(self,name,script,timeout):
                if name.endswith('-source'):
                    if 'test "$#" = 1; cat "$1"' not in script or '\\"' in script:raise AssertionError('shell quotes are escaped into literal path')
                    return '@@boot\n'+BOOT+'\n@@tcpm\n'+source()+'@@boot-end\n'+BOOT+'\n',0
                return json.dumps(packet(500)),0
        from unittest.mock import patch
        with patch.object(h,'write'):
            self.assertEqual(h.controls(Recorder(),'baseline-controls',BOOT)['input_limit_ma'],500)

if __name__=='__main__':unittest.main()
