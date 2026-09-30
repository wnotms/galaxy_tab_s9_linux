"""NCM host readiness, source binding and first-failure preservation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gts9_ncm_ready as n

BOOT = 'a' * 32
SOURCE = '169.254.74.160'


def fixtures():
    windows = {'adapters': [{'PnPDeviceID': 'USB\\' + n.PNP,
                            'InterfaceDescription': 'UsbNcm Host Device #3',
                            'Status': 'Up', 'ifIndex': 9}],
               'addresses': [{'InterfaceIndex': 9, 'IPAddress': SOURCE,
                              'AddressState': 4, 'PrefixLength': 16}],
               'routes': [], 'code43': []}
    route = [{'dst': n.TARGET, 'dev': 'eth2', 'prefsrc': SOURCE}]
    addr = [{'ifname': 'eth2', 'flags': ['UP', 'LOWER_UP'],
             'addr_info': [{'family': 'inet', 'local': SOURCE, 'prefixlen': 16}]}]
    return windows, route, addr


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeRecorder:
    def __init__(self, folder):
        self.folder = folder
        self.calls = []
        self.windows, self.route, self.addresses = fixtures()
        self.windows_samples = []
        self.ps_status = self.ssh_status = self.route_status = self.addr_status = 0
        self.after_boot = BOOT
        self.clock = FakeClock()

    def ps(self, name, script, **kwargs):
        self.calls.append(('ps', name, script))
        self.clock.now += 0.1
        row = self.windows_samples.pop(0) if self.windows_samples else self.windows
        return json.dumps(row), self.ps_status

    def command(self, name, argv, **kwargs):
        self.calls.append(('command', name, argv))
        if name.endswith('-route'):
            return json.dumps(self.route), self.route_status
        if name.endswith('-addresses'):
            return json.dumps(self.addresses), self.addr_status
        return self.after_boot + '\n15000.0 1000.0\n', self.ssh_status

    def adb(self, name, script, **kwargs):
        self.calls.append(('adb', name, script))
        return BOOT + '\n15000.0 1000.0\n', 0


class NcmTopologyTests(unittest.TestCase):
    def setUp(self):
        self.w, self.r, self.a = fixtures()

    def gate(self):
        return n.topology_gate(self.w, self.r, self.a)

    def test_current_mirrored_topology_ready(self):
        gate = self.gate()
        self.assertTrue(gate['ready'])
        self.assertEqual(gate['source_ipv4'], SOURCE)
        self.assertEqual(gate['windows_interface_index'], 9)

    def test_absent_or_down_adapter_waits(self):
        self.w['adapters'][0]['Status'] = 'Disconnected'
        self.assertFalse(self.gate()['ready'])
        self.w['adapters'] = []
        self.assertFalse(self.gate()['ready'])

    def test_other_usb_nic_cannot_identify_tablet(self):
        self.w['adapters'][0]['PnPDeviceID'] = 'USB\\VID_1234'
        self.assertFalse(self.gate()['ready'])

    def test_tentative_windows_apipa_waits(self):
        self.w['addresses'][0]['AddressState'] = 1
        self.assertFalse(self.gate()['ready'])

    def test_wrong_prefix_waits(self):
        self.w['addresses'][0]['PrefixLength'] = 24
        self.assertFalse(self.gate()['ready'])

    def test_missing_windows_apipa_waits(self):
        self.w['addresses'] = []
        self.assertFalse(self.gate()['ready'])

    def test_code43_stops(self):
        self.w['code43'] = [{'ConfigManagerErrorCode': 43}]
        with self.assertRaisesRegex(n.p.CaptureError, 'Code43'):
            self.gate()

    def test_duplicate_nic_stops(self):
        self.w['adapters'].append(copy.deepcopy(self.w['adapters'][0]))
        with self.assertRaisesRegex(n.p.CaptureError, 'ambiguous'):
            self.gate()

    def test_duplicate_windows_ip_stops(self):
        self.w['addresses'].append(copy.deepcopy(self.w['addresses'][0]))
        with self.assertRaisesRegex(n.p.CaptureError, 'ambiguous'):
            self.gate()

    def test_address_conflict_stops(self):
        self.w['addresses'][0]['IPAddress'] = n.TARGET
        with self.assertRaisesRegex(n.p.CaptureError, 'conflict'):
            self.gate()

    def test_missing_evidence_stops(self):
        del self.w['code43']
        with self.assertRaisesRegex(n.p.CaptureError, 'missing'):
            self.gate()

    def test_missing_wsl_route_waits(self):
        self.r = []
        self.assertFalse(self.gate()['ready'])

    def test_wifi_gateway_not_accepted_as_ncm(self):
        self.r[0].update(dev='eth3', prefsrc='10.191.121.63', gateway='10.191.121.1')
        self.assertFalse(self.gate()['ready'])

    def test_wrong_source_even_with_same_interface_waits(self):
        self.r[0]['prefsrc'] = '169.254.1.2'
        self.assertFalse(self.gate()['ready'])

    def test_missing_mirror_waits(self):
        self.a = []
        self.assertFalse(self.gate()['ready'])

    def test_down_mirrored_link_waits(self):
        self.a[0]['flags'] = ['UP']
        self.assertFalse(self.gate()['ready'])

    def test_tentative_linux_address_waits(self):
        self.a[0]['addr_info'][0]['tentative'] = True
        self.assertFalse(self.gate()['ready'])

    def test_duplicate_linux_source_stops(self):
        other = copy.deepcopy(self.a[0]); other['ifname'] = 'eth3'
        self.a.append(other)
        with self.assertRaisesRegex(n.p.CaptureError, 'ambiguous'):
            self.gate()


class NcmConnectTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.rec = FakeRecorder(Path(tmp.name))
        self.key = self.rec.folder / 'key'; self.key.touch()

    def wait(self, window=3):
        return n.wait_ready(self.rec, window, self.rec.clock, self.rec.clock.sleep)

    def connect(self):
        from unittest.mock import patch
        real_wait = n.wait_ready
        with patch.object(n, 'wait_ready', side_effect=lambda rec, window:
                          real_wait(rec, window, self.rec.clock, self.rec.clock.sleep)):
            return n.connect(self.rec, self.key, 3)

    def ssh_calls(self):
        return [x for x in self.rec.calls if x[1] == 'ncm-auth']

    def test_apipa_wait_then_ready_retains_first_unready_state(self):
        unready = copy.deepcopy(self.rec.windows); unready['addresses'] = []
        self.rec.windows_samples = [unready]
        result = self.connect()
        self.assertTrue(result['delayed_readiness'])
        self.assertEqual(result['samples'], 2)
        samples = json.loads((self.rec.folder / 'readiness.json').read_text())
        self.assertFalse(samples[0]['ready'])
        self.assertEqual(len(self.ssh_calls()), 1)
        self.assertEqual(self.rec.calls[-1][1], 'ncm-auth')

    def test_readiness_deadline_never_attempts_ssh(self):
        self.rec.windows['addresses'] = []
        with self.assertRaisesRegex(n.p.CaptureError, 'deadline'):
            self.connect()
        self.assertFalse(self.ssh_calls())

    def test_code43_never_attempts_ssh(self):
        self.rec.windows['code43'] = ['Code43']
        with self.assertRaisesRegex(n.p.CaptureError, 'Code43'):
            self.connect()
        self.assertFalse(self.ssh_calls())

    def test_windows_capture_failure_stops_without_retry(self):
        self.rec.ps_status = 'timeout'
        with self.assertRaisesRegex(n.p.CaptureError, 'capture failed'):
            self.connect()
        self.assertEqual(len([x for x in self.rec.calls if x[0] == 'ps']), 1)
        self.assertFalse(self.ssh_calls())

    def test_wsl_capture_failure_stops(self):
        self.rec.addr_status = 1
        with self.assertRaisesRegex(n.p.CaptureError, 'capture failed'):
            self.connect()
        self.assertFalse(self.ssh_calls())

    def test_missing_route_status_two_waits_until_deadline(self):
        self.rec.route_status = 2
        with self.assertRaisesRegex(n.p.CaptureError, 'deadline'):
            self.connect()
        self.assertFalse(self.ssh_calls())

    def test_ssh_failure_never_retried(self):
        self.rec.ssh_status = 255
        with self.assertRaisesRegex(n.p.CaptureError, 'first NCM SSH failed'):
            self.connect()
        self.assertEqual(len(self.ssh_calls()), 1)

    def test_ssh_command_timeout_never_retried(self):
        self.rec.ssh_status = 'timeout'
        with self.assertRaisesRegex(n.p.CaptureError, 'first NCM SSH failed'):
            self.connect()
        self.assertEqual(len(self.ssh_calls()), 1)

    def test_boot_mismatch_stops(self):
        self.rec.after_boot = 'b' * 32
        with self.assertRaisesRegex(n.p.CaptureError, 'boot mismatch'):
            self.connect()

    def test_source_binding_and_no_proxy_or_user_config(self):
        result = self.connect()
        argv = self.ssh_calls()[0][2]
        self.assertEqual(argv[argv.index('-b') + 1], SOURCE)
        self.assertEqual(argv[argv.index('-F') + 1], '/dev/null')
        self.assertIn('ConnectionAttempts=1', argv)
        self.assertIn('BatchMode=yes', argv)
        self.assertIn('root@' + n.TARGET, argv)
        self.assertEqual(result['boot_id'], BOOT)
        self.assertFalse(result['device_configuration_changed'])

    def test_missing_key_stops_before_device_probes(self):
        self.key.unlink()
        with self.assertRaisesRegex(n.p.CaptureError, 'missing existing SSH key'):
            self.connect()
        self.assertFalse(self.rec.calls)


if __name__ == '__main__':
    unittest.main()
