import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


D = load('ssc_rpmsg_diagnostic', ROOT / 'userspace/sensors/rpmsg_diagnostic.py')
B = load('ssc_rpmsg_builder', ROOT / 'scripts/build-ssc-rpmsg-control.py')


class FakeNative:
    def __init__(self, failure=None):
        self.failure = failure; self.calls = []; self.packet = b'\x7e\x00\x01\x7e'

    def step(self, name, result=None):
        self.calls.append(name)
        if self.failure == name:
            raise OSError(name + ' injected fault')
        return result

    def admit(self, plan):return self.step('admit', 'owned-controller')
    def open_control(self, path):return self.step('control', 10)
    def create(self, fd):return self.step('create')
    def owned_endpoint(self, path):return self.step('owned', 'owned-endpoint')
    def open_endpoint(self, path):return self.step('open', 11)
    def receive(self, fd):return self.step('receive', self.packet)
    def destroy(self, fd):return self.step('destroy')
    def close(self, fd):self.calls.append('close-' + str(fd))


class EndpointProbeTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.ledger = Path(t.name) / 'probe.json'
        self.plan = dict(boot_id='11111111-1111-1111-1111-111111111111',
                         channel='DIAG', payload_writes=False)

    def test_linux_uapi_layout_and_ioctl_values(self):
        request = D.endpoint_request()
        self.assertEqual(len(request), 40)
        self.assertEqual(struct.unpack('<32sII', request), (b'DIAG' + b'\0'*28, 0xffffffff, 0xffffffff))
        self.assertEqual(D.CREATE_EPT, (1 << 30) | (40 << 16) | (0xb5 << 8) | 1)
        self.assertEqual(D.DESTROY_EPT, (0xb5 << 8) | 2)

    def test_forbidden_names_cannot_target_existing_transport_or_control(self):
        for name in ('IPCRTR', 'fastrpcglink-apps-dsp', 'DIAG_CNTL', 'DIAG_CMD', '', 'diag'):
            with self.assertRaises(ValueError):D.endpoint_request(name)

    def test_create_open_passive_receive_destroy_same_fd(self):
        native = FakeNative(); result = D.probe(self.plan, native, self.ledger)
        self.assertTrue(result['complete']); self.assertEqual(result['payload_writes'], 0)
        self.assertEqual(result['masks_sent'], 0); self.assertTrue(result['endpoint_destroyed'])
        self.assertFalse(result['requires_registered_reboot'])
        self.assertEqual(native.calls, ['admit', 'control', 'create', 'owned', 'open', 'receive', 'destroy', 'close-11', 'close-10'])
        self.assertEqual(json.loads(self.ledger.read_text()), result)

    def test_no_packet_is_handshake_only_not_a_log_or_sensor_proof(self):
        native = FakeNative(); native.packet = b''
        result = D.probe(self.plan, native, self.ledger)
        self.assertTrue(result['complete']); self.assertEqual(result['packet_bytes'], 0)
        self.assertNotIn('SSC_verified', result)

    def test_create_failure_never_opens_endpoint(self):
        native = FakeNative('create'); result = D.probe(self.plan, native, self.ledger)
        self.assertFalse(result['complete']); self.assertNotIn('open', native.calls)
        self.assertEqual(native.calls[-1], 'close-10')

    def test_open_timeout_requires_rollback_never_reopens_failed_endpoint(self):
        native = FakeNative('open'); result = D.probe(self.plan, native, self.ledger)
        self.assertFalse(result['complete']); self.assertTrue(result['requires_registered_reboot'])
        self.assertEqual(native.calls.count('open'), 1); self.assertNotIn('destroy', native.calls)
        self.assertNotIn('receive', native.calls)

    def test_unowned_or_duplicate_endpoint_stops_before_open(self):
        native = FakeNative('owned'); result = D.probe(self.plan, native, self.ledger)
        self.assertFalse(result['complete']); self.assertNotIn('open', native.calls)
        self.assertTrue(result['requires_registered_reboot'])

    def test_read_fault_still_destroys_already_open_endpoint(self):
        native = FakeNative('receive'); result = D.probe(self.plan, native, self.ledger)
        self.assertFalse(result['complete']); self.assertTrue(result['endpoint_destroyed'])
        self.assertIn('close-11', native.calls)

    def test_cleanup_fault_stops_and_requires_registered_reboot(self):
        native = FakeNative('destroy'); result = D.probe(self.plan, native, self.ledger)
        self.assertFalse(result['complete']); self.assertTrue(result['requires_registered_reboot'])
        self.assertEqual(native.calls[-2:], ['close-11', 'close-10'])

    def test_evidence_cap_preserves_cleanup(self):
        native = FakeNative(); native.packet = b'x' * (D.MAX_PACKET + 1)
        result = D.probe(self.plan, native, self.ledger)
        self.assertFalse(result['complete']); self.assertTrue(result['endpoint_destroyed'])

    def test_stale_ledger_prevents_second_create(self):
        self.ledger.write_text('previous boot')
        native = FakeNative()
        with self.assertRaises(FileExistsError):D.probe(self.plan, native, self.ledger)
        self.assertEqual(native.calls, ['admit'])
        self.assertEqual(self.ledger.read_text(), 'previous boot')

    def test_native_eof_is_a_failure_not_empty_success(self):
        with patch.object(D.select, 'select', return_value=([11], [], [])), patch.object(D.os, 'read', return_value=b''):
            with self.assertRaises(ConnectionError):D.Native().receive(11)

    def test_native_idle_channel_does_not_read(self):
        with patch.object(D.select, 'select', return_value=([], [], [])), patch.object(D.os, 'read') as reader:
            self.assertEqual(D.Native().receive(11), b''); reader.assert_not_called()

    def test_created_ledger_is_saved_before_blocking_kernel_open(self):
        native = FakeNative('open')
        original = native.open_endpoint
        def check(entry):
            phase = json.loads(self.ledger.read_text())
            self.assertEqual(phase['phase'], 'endpoint-device-created')
            self.assertTrue(phase['requires_registered_reboot'])
            return original(entry)
        native.open_endpoint = check
        D.probe(self.plan, native, self.ledger)

    def test_bad_scope_rejected_before_native_operations(self):
        for extra in ({'payload_writes': True}, {'channel': 'IPCRTR'}):
            native = FakeNative()
            with self.assertRaises(ValueError):D.probe(self.plan | extra, native, self.ledger)
            self.assertFalse(native.calls)

    def test_failed_identity_never_creates_ledger_or_endpoint(self):
        native = FakeNative('admit')
        with self.assertRaises(OSError):D.probe(self.plan, native, self.ledger)
        self.assertFalse(self.ledger.exists()); self.assertEqual(native.calls, ['admit'])


class ProviderCRCTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.sym = Path(t.name) / 'Module.symvers'
        self.sym.write_text('0x12345678\trpmsg_create_ept\tvmlinux\tEXPORT_SYMBOL\n')

    def test_matching_crc_is_accepted(self):
        with patch.object(B, 'call', return_value='0x12345678 rpmsg_create_ept\n'):
            self.assertEqual(B.imported_versions(Path('module.ko'), self.sym), {'rpmsg_create_ept': '0x12345678'})

    def test_crc_mismatch_and_unknown_symbol_are_rejected(self):
        for row in ('0x87654321 rpmsg_create_ept\n', '0x12345678 unknown\n'):
            with patch.object(B, 'call', return_value=row):
                with self.assertRaises(ValueError):B.imported_versions(Path('module.ko'), self.sym)

    def test_empty_import_table_is_not_pairing_proof(self):
        with patch.object(B, 'call', return_value=''):
            with self.assertRaises(ValueError):B.imported_versions(Path('module.ko'), self.sym)

    def test_duplicate_symbol_is_rejected(self):
        with patch.object(B, 'call', return_value='0x12345678 rpmsg_create_ept\n'*2):
            with self.assertRaises(ValueError):B.imported_versions(Path('module.ko'), self.sym)


class LedgerNamespaceTests(unittest.TestCase):
    def test_original_namespace_default_preserved(self):
        with patch.object(Path, 'is_dir', return_value=True), patch.object(Path, 'is_symlink', return_value=False):
            D.admit_ledger({}, Path('/run/gts9-test384/probe.json'))

    def test_new_registered_namespace_is_exact(self):
        with patch.object(Path, 'is_dir', return_value=True), patch.object(Path, 'is_symlink', return_value=False):
            D.admit_ledger({'ledger_directory': '/run/gts9-test385'}, Path('/run/gts9-test385/probe.json'))
            with self.assertRaises(ValueError):
                D.admit_ledger({'ledger_directory': '/run/gts9-test385'}, Path('/run/gts9-test384/probe.json'))

    def test_foreign_escaped_or_invalid_namespace_rejected(self):
        for owner in ('/tmp/gts9-test385', '/run/gts9-test385/../other', '/run/gts9-test385/', None, 385):
            with self.assertRaises(ValueError):
                D.admit_ledger({'ledger_directory': owner}, Path('/run/gts9-test385/probe.json'))

    def test_missing_symlink_parent_or_other_filename_rejected(self):
        for directory, symlink, filename in ((False, False, 'probe.json'), (True, True, 'probe.json'), (True, False, 'another.json')):
            with patch.object(Path, 'is_dir', return_value=directory), patch.object(Path, 'is_symlink', return_value=symlink):
                with self.assertRaises(ValueError):
                    D.admit_ledger({}, Path('/run/gts9-test384') / filename)


if __name__ == '__main__':unittest.main()
