import importlib.util
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('servreg_snapshot', ROOT / 'userspace/sensors/servreg-domain-snapshot.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
BOOT = '11111111-1111-1111-1111-111111111111'


def tlv(tag, value):
    return struct.pack('<BH', tag, len(value)) + value


def response(layout='linux-7.2', *, total=1, domains=None, extra=b'', result=b'\0\0\0\0'):
    if domains is None:
        domains = [('msm/adsp/sensor_pd', 74)]
    width = 1 if layout == 'linux-7.2' else 2
    entries = bytes([len(domains)])
    for name, instance in domains:
        entries += len(name).to_bytes(width, 'little') + name.encode() + struct.pack('<IBI', instance, 0, 0)
    body = (tlv(2, result) + tlv(0x10, struct.pack('<H', total)) +
            tlv(0x11, b'\1\0') + tlv(0x12, entries) + extra)
    return struct.pack('<BHHH', 2, 1, 0x21, len(body)) + body


class WireTests(unittest.TestCase):
    def test_request_matches_pinned_top_level_string_encoding(self):
        self.assertEqual(S.request().hex(), '00010021000e00010b00746d732f73657276726567')

    def test_native_golden_response_one_byte_nested_string(self):
        # A literal wire fixture independent of the encoder helper above.
        wire = bytes.fromhex('020100210031000204000000000010020001001102000100'
                             '121d0001126d736d2f616473702f73656e736f725f70644a0000000000000000')
        d = S.decode(wire, 'linux-7.2')
        self.assertTrue(d['complete'])
        self.assertTrue(d['sensor_domain_present'])
        self.assertFalse(d['ssc_service_verified'])
        self.assertFalse(d['accelerometer_verified'])

    def test_userspace_layout_is_explicit_not_silently_guessed(self):
        wire = response('pd-mapper-1.1')
        self.assertTrue(S.decode(wire, 'pd-mapper-1.1')['sensor_domain_present'])
        with self.assertRaises(ValueError):
            S.decode(wire, 'linux-7.2')

    def test_empty_domains_is_a_complete_negative_answer(self):
        d = S.decode(response(total=0, domains=[]), 'linux-7.2')
        self.assertTrue(d['complete'])
        self.assertFalse(d['sensor_domain_present'])

    def test_partial_page_is_not_complete(self):
        self.assertFalse(S.decode(response(total=2), 'linux-7.2')['complete'])

    def test_wrong_sensor_instance_does_not_verify_x710_domain(self):
        self.assertFalse(S.decode(response(domains=[('msm/adsp/sensor_pd', 4)]), 'linux-7.2')['sensor_domain_present'])

    def test_foreign_transaction_method_or_type_rejected(self):
        for index in (0, 1, 3):
            wire = bytearray(response()); wire[index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                S.decode(bytes(wire), 'linux-7.2')

    def test_truncated_header_payload_and_tlv_rejected(self):
        wire = response()
        for end in (0, 6, 9, len(wire) - 1):
            with self.subTest(end=end), self.assertRaises(ValueError):
                S.decode(wire[:end], 'linux-7.2')

    def test_duplicate_tlv_rejected(self):
        with self.assertRaises(ValueError):
            S.decode(response(extra=tlv(0x10, b'\1\0')), 'linux-7.2')

    def test_qmi_failure_rejected(self):
        with self.assertRaisesRegex(ValueError, 'result=1 error=2'):
            S.decode(response(result=b'\1\0\2\0'), 'linux-7.2')

    def test_duplicate_domain_and_inconsistent_total_rejected(self):
        for wire in (response(total=0), response(total=2, domains=[('a', 74), ('a', 74)])):
            with self.assertRaises(ValueError):
                S.decode(wire, 'linux-7.2')

    def test_oversize_or_nul_domain_rejected(self):
        for name in ('a' * 65, 'bad\0name'):
            with self.assertRaises(ValueError):
                S.decode(response(domains=[(name, 74)]), 'linux-7.2')


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.sock = Mock()
        self.sock.getsockname.return_value = (7, 16390)
        self.sock.recvfrom.return_value = (response(), (7, 16385))
        self.factory = Mock(return_value=self.sock)
        self.args = dict(create=self.factory, clock=lambda: 0, boot=lambda: BOOT, expected_boot=BOOT)

    def run_query(self, **kwargs):
        return S.query(7, 16385, 'linux-7.2', **(self.args | kwargs))

    def test_reads_actual_local_node_one_request_no_retry(self):
        d = self.run_query()
        self.assertTrue(d['complete'])
        self.sock.bind.assert_called_once_with((7, 0))
        self.sock.sendto.assert_called_once_with(S.request(), (7, 16385))
        self.sock.close.assert_called_once()

    def test_timeout_has_raw_request_and_closes_without_retry(self):
        self.sock.recvfrom.side_effect = socket.timeout('timed out')
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertEqual(e.exception.evidence['request_hex'], S.request().hex())
        self.assertFalse(e.exception.evidence['complete'])
        self.sock.sendto.assert_called_once()
        self.sock.close.assert_called_once()

    def test_foreign_peer_keeps_raw_reply_then_rejects(self):
        self.sock.recvfrom.return_value = (response(), (8, 16385))
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertEqual(e.exception.evidence['raw_packets'][0]['peer'], [8, 16385])
        self.sock.close.assert_called_once()

    def test_malformed_response_retained(self):
        self.sock.recvfrom.return_value = (b'bad', (7, 16385))
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query()
        self.assertEqual(e.exception.evidence['raw_packets'][0]['hex'], b'bad'.hex())

    def test_changed_boot_before_query_sends_nothing(self):
        with self.assertRaises(S.EvidenceError):
            self.run_query(boot=lambda: '22222222-2222-2222-2222-222222222222')
        self.factory.assert_not_called()

    def test_changed_boot_after_query_invalidates_complete_response(self):
        with self.assertRaises(S.EvidenceError) as e:
            self.run_query(boot=Mock(side_effect=[BOOT, '22222222-2222-2222-2222-222222222222']))
        self.assertFalse(e.exception.evidence['complete'])
        self.assertEqual(len(e.exception.evidence['raw_packets']), 1)

    def test_bind_failure_closes_without_send(self):
        self.sock.bind.side_effect = OSError('bind failed')
        with self.assertRaises(S.EvidenceError):
            self.run_query()
        self.sock.sendto.assert_not_called()
        self.sock.close.assert_called_once()

    def test_bounds_checked_before_socket(self):
        for args in ((7, 0, 'linux-7.2', 2), (7, 1, 'guess', 2),
                     (True, 1, 'linux-7.2', 2), (7, 1, 'linux-7.2', 4)):
            with self.assertRaises(ValueError):
                S.query(*args, **self.args)
        self.factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
