"""Notifier wire/endpoint/lifecycle tests; never contact the tablet."""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('servreg_state', ROOT / 'userspace/sensors/servreg-state-snapshot.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
PRIOR = ROOT / 'reference/boot-tests/test-390-ssc-missing-file-status/runtime-discovery'
INVENTORY = json.loads((PRIOR / 'qrtr-after.json').read_text())
DOMAINS = json.loads((PRIOR / 'servreg-domains.json').read_text())
BOOT = INVENTORY['boot_id']
OTHER = '22222222-2222-2222-2222-222222222222'
# Literal independent wire fixtures: QMI response result0/error0, optional UP.
UP = bytes.fromhex('02010020000e0002040000000000100400ffffff1f')
NO_STATE = bytes.fromhex('0201002000070002040000000000')
REQUEST = '00010020001900010100000212006d736d2f616473702f73656e736f725f7064'


def response(body):
    return struct.pack('<BHHH', 2, 1, 0x20, len(body)) + body


class WireTests(unittest.TestCase):
    def test_literal_request_unregisters_only_own_client(self):
        self.assertEqual(S.request().hex(), REQUEST)
        self.assertEqual(S.request()[10], 0)
        self.assertEqual(S.request()[14:], b'msm/adsp/sensor_pd')

    def test_literal_up_response_is_not_sensor_acceptance(self):
        d = S.decode(UP)
        self.assertTrue(d['complete'])
        self.assertEqual(d['domain_state'], 'UP')
        self.assertEqual(d['state_value'], 0x1fffffff)
        self.assertFalse(d['SSC_service_verified'])
        self.assertFalse(d['accelerometer_verified'])

    def test_all_pinned_states(self):
        for state, name in ((1, 'LOCATOR_ERROR'), (0x0fffffff, 'DOWN'),
                            (0x1fffffff, 'UP'), (0x2fffffff, 'EARLY_DOWN'),
                            (0x7fffffff, 'UNINIT')):
            with self.subTest(state=name):
                d = S.decode(UP[:-4] + struct.pack('<I', state))
                self.assertEqual(d['domain_state'], name)
                self.assertTrue(d['complete'])

    def test_missing_optional_state_is_unknown_not_up(self):
        d = S.decode(NO_STATE)
        self.assertTrue(d['protocol_complete'])
        self.assertFalse(d['complete'])
        self.assertFalse(d['state_present'])
        self.assertEqual(d['domain_state'], 'UNKNOWN')
        self.assertNotIn('state_value', d)

    def test_nonzero_result_or_error_rejected(self):
        for result in (b'\1\0\2\0', b'\0\0\2\0', b'\1\0\0\0'):
            with self.subTest(result=result), self.assertRaises(ValueError):
                S.decode(response(b'\2\4\0' + result))

    def test_wrong_kind_transaction_or_method_rejected(self):
        for index in (0, 1, 2, 3, 4):
            wire = bytearray(UP); wire[index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                S.decode(wire)

    def test_truncated_or_extra_payload_rejected(self):
        for wire in (b'', UP[:6], UP[:-1], UP + b'\0'):
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                S.decode(wire)

    def test_tlv_shapes_duplicates_and_unknown_tags_rejected(self):
        valid = NO_STATE[7:]
        for body in (b'', b'\2\3\0\0\0\0', valid + valid,
                     valid + b'\20\4\0\0', valid + b'\20',
                     valid + b'\20\3\0\0\0\0', valid + b'\21\0\0',
                     UP[7:] + b'\20\4\0\xff\xff\xff\x1f'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                S.decode(response(body))

    def test_unrecognized_enum_including_zero_rejected(self):
        for value in (0, 2, 0xffffffff):
            with self.subTest(value=value), self.assertRaises(ValueError):
                S.decode(UP[:-4] + struct.pack('<I', value))


class EndpointTests(unittest.TestCase):
    def test_actual_native_notifier_selected_not_locator_or_sysctrl(self):
        self.assertEqual(S.endpoint(INVENTORY, DOMAINS, BOOT), (5, 3))

    def test_different_boot_or_incomplete_inventory_rejected(self):
        for source, key, value in (('inventory', 'boot_id', OTHER), ('domains', 'boot_id', OTHER),
                                   ('inventory', 'complete', False), ('domains', 'complete', False),
                                   ('inventory', 'complete', 1)):
            inv, dom = copy.deepcopy(INVENTORY), copy.deepcopy(DOMAINS)
            (inv if source == 'inventory' else dom)[key] = value
            with self.subTest(source=source, key=key), self.assertRaises(ValueError):
                S.endpoint(inv, dom, BOOT)

    def test_sensor_domain_missing_duplicate_or_wrong_instance_rejected(self):
        sensor = next(r for r in DOMAINS['domains'] if r['name'] == S.PATH.decode())
        for rows in ([], [sensor, sensor], [dict(sensor, instance=4)],
                     [dict(sensor, instance=True)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                S.endpoint(INVENTORY, dict(DOMAINS, domains=rows), BOOT)

    def test_notifier_missing_duplicate_or_wrong_version_rejected(self):
        row = dict(service=66, instance=18945, node=5, port=3)
        for rows in ([], [row, row], [dict(row, service=69)],
                     [dict(row, instance=18946)], [dict(row, instance=257)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                S.endpoint(dict(INVENTORY, services=rows), DOMAINS, BOOT)

    def test_bad_address_rejected(self):
        row = dict(service=66, instance=18945, node=5, port=3)
        for key, value in (('node', -1), ('node', True), ('port', 0),
                           ('port', 0xfffffffe), ('port', '3')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                S.endpoint(dict(INVENTORY, services=[dict(row, **{key: value})]), DOMAINS, BOOT)

    def test_malformed_evidence_rejected(self):
        for inv, dom in ((None, DOMAINS), ({}, DOMAINS),
                         (dict(INVENTORY, services=[{}]), DOMAINS),
                         (INVENTORY, dict(DOMAINS, domains=[None])),
                         (dict(INVENTORY, services={}), DOMAINS)):
            with self.subTest(inv=inv), self.assertRaises(ValueError):
                S.endpoint(inv, dom, BOOT)


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.sock = Mock()
        self.sock.getsockname.return_value = (1, 16390)
        self.sock.sendto.return_value = len(S.request())
        self.sock.recvfrom.return_value = (UP, (5, 3))
        self.factory = Mock(return_value=self.sock)
        self.kw = dict(expected_boot=BOOT, create=self.factory, clock=lambda: 0, boot=lambda: BOOT)

    def run_query(self, **kwargs):
        return S.query(INVENTORY, DOMAINS, **(self.kw | kwargs))

    def test_actual_local_node_and_one_request_always_close(self):
        d = self.run_query()
        self.sock.bind.assert_called_once_with((1, 0))
        self.sock.sendto.assert_called_once_with(bytes.fromhex(REQUEST), (5, 3))
        self.sock.recvfrom.assert_called_once_with(256)
        self.sock.close.assert_called_once()
        self.assertTrue(d['complete'])
        self.assertEqual(d['enable'], 0)
        self.assertFalse(d['listener_registered'])
        self.assertFalse(d['DSP_started'])

    def test_missing_state_does_not_subscribe_or_retry(self):
        self.sock.recvfrom.return_value = (NO_STATE, (5, 3))
        self.assertFalse(self.run_query()['complete'])
        self.sock.sendto.assert_called_once()
        self.sock.close.assert_called_once()

    def test_timeout_retains_request_and_closes(self):
        self.sock.recvfrom.side_effect = socket.timeout('timeout')
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertEqual(e.exception.evidence['request_hex'], REQUEST)
        self.assertFalse(e.exception.evidence['complete'])
        self.sock.sendto.assert_called_once()
        self.sock.close.assert_called_once()

    def test_foreign_peer_retained_and_rejected(self):
        self.sock.recvfrom.return_value = (UP, (7, 3))
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertEqual(e.exception.evidence['raw_packets'][0]['peer'], [7, 3])
        self.sock.close.assert_called_once()

    def test_malformed_reply_retained(self):
        self.sock.recvfrom.return_value = (b'bad', (5, 3))
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertEqual(e.exception.evidence['raw_packets'][0]['hex'], '626164')

    def test_changed_boot_before_sends_nothing(self):
        with self.assertRaises(S.EvidenceError):
            self.run_query(boot=lambda: OTHER)
        self.factory.assert_not_called()

    def test_changed_boot_after_invalidates_complete_reply(self):
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query(boot=Mock(side_effect=[BOOT, OTHER]))
        self.assertFalse(e.exception.evidence['complete'])
        self.assertEqual(len(e.exception.evidence['raw_packets']), 1)

    def test_inventory_admission_failure_creates_no_socket(self):
        with self.assertRaises(ValueError):
            S.query(dict(INVENTORY, complete=False), DOMAINS, **self.kw)
        self.factory.assert_not_called()

    def test_invalid_deadline_creates_no_socket(self):
        for seconds in (0, -1, 3.01, True, float('nan'), float('inf'), '2'):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.run_query(seconds=seconds)
        self.factory.assert_not_called()

    def test_socket_errors_close_created_socket(self):
        for operation in ('bind', 'sendto', 'recvfrom'):
            with self.subTest(operation=operation):
                self.setUp()
                getattr(self.sock, operation).side_effect = OSError(operation)
                with self.assertRaises(S.EvidenceError):
                    self.run_query()
                self.sock.close.assert_called_once()
                if operation == 'bind':
                    self.sock.sendto.assert_not_called()

    def test_socket_creation_error_is_recorded(self):
        self.factory.side_effect = OSError('socket')
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertFalse(e.exception.evidence['complete'])
        self.sock.sendto.assert_not_called()

    def test_short_send_rejected_without_receive(self):
        self.sock.sendto.return_value = 1
        with self.assertRaises(S.EvidenceError):
            self.run_query()
        self.sock.recvfrom.assert_not_called()
        self.sock.close.assert_called_once()

    def test_deadline_expiry_before_or_after_send(self):
        for ticks, sent in (([0, 3, 3], False), ([0, 0, 3, 3], True)):
            with self.subTest(ticks=ticks):
                self.setUp()
                with self.assertRaises(S.EvidenceError):
                    self.run_query(clock=Mock(side_effect=ticks))
                self.assertEqual(self.sock.sendto.called, sent)
                self.sock.recvfrom.assert_not_called()
                self.sock.close.assert_called_once()

    def test_late_response_retained_but_not_complete(self):
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query(clock=Mock(side_effect=[0, 0, 0, 3, 3, 3]))
        self.assertFalse(e.exception.evidence['complete'])
        self.assertEqual(len(e.exception.evidence['raw_packets']), 1)

    def test_timeout_is_remaining_absolute_budget(self):
        d = self.run_query(clock=Mock(side_effect=[0, .25, .75, 1, 1, 1.25]))
        self.assertEqual([c.args[0] for c in self.sock.settimeout.call_args_list], [1.75, 1.25])
        self.assertEqual(d['seconds'], 1.25)


if __name__ == '__main__':
    unittest.main()
