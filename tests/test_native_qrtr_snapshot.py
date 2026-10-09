import importlib.util
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_qrtr_snapshot', ROOT / 'userspace/sensors/qrtr-native-snapshot.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class NativeQRTRSnapshotTests(unittest.TestCase):
    def socket(self, replies, node=7):
        sock = Mock()
        sock.getsockname.side_effect = [(node, 0), (node, 123)]
        def bind(address):
            # Model the real kernel guard that the old mock did not enforce.
            if address[0] != node:
                raise OSError(22, 'Invalid argument')
        sock.bind.side_effect = bind
        sock.recvfrom.side_effect = replies
        return sock, Mock(return_value=sock)

    def test_uses_kernel_assigned_node_not_zero_or_one(self):
        sock, factory = self.socket([(q.packet(4), (7, q.CTRL))])
        result = q.query(create=factory, clock=lambda: 0)
        sock.bind.assert_called_once_with((7, 0))
        self.assertEqual(result['local'], [7, 123])
        self.assertTrue(result['complete'])
        self.assertEqual(sock.sendto.call_args_list[0].args, (q.packet(q.NEW_LOOKUP), (7, q.CTRL)))
        self.assertEqual(sock.sendto.call_args_list[-1].args, (q.packet(q.DEL_LOOKUP), (7, q.CTRL)))
        sock.close.assert_called_once()

    def test_service_listing_preserves_raw_source_and_complete_marker(self):
        wire = struct.pack('<5I', 4, 400, 1, 2, 12)
        sock, factory = self.socket([(wire, (7, q.CTRL)), (q.packet(4), (7, q.CTRL))])
        result = q.query(create=factory, clock=lambda: 0)
        self.assertEqual(result['services'], [dict(service=400, instance=1, node=2, port=12)])
        self.assertEqual(result['raw_packets'][0]['hex'], wire.hex())
        self.assertEqual(result['raw_packets'][0]['peer'], [7, q.CTRL])

    def test_timeout_is_incomplete_and_lookup_removed(self):
        sock, factory = self.socket([socket.timeout()])
        result = q.query(create=factory, clock=lambda: 0)
        self.assertFalse(result['complete'])
        self.assertEqual(result['services'], [])
        self.assertEqual(sock.sendto.call_count, 2)
        sock.close.assert_called_once()

    def test_foreign_reply_retained_then_rejected(self):
        sock, factory = self.socket([(q.packet(4), (8, q.CTRL))])
        with self.assertRaises(q.LookupFault) as caught:
            q.query(create=factory, clock=lambda: 0)
        self.assertEqual(caught.exception.raw[0]['peer'], [8, q.CTRL])
        sock.close.assert_called_once()

    def test_malformed_reply_rejected(self):
        sock, factory = self.socket([(b'bad', (7, q.CTRL))])
        with self.assertRaises(q.LookupFault):
            q.query(create=factory, clock=lambda: 0)
        sock.close.assert_called_once()

    def test_bind_failure_does_not_send_or_leak_socket(self):
        sock, factory = self.socket([])
        sock.bind.side_effect = OSError(22, 'Invalid argument')
        with self.assertRaises(q.LookupFault):
            q.query(create=factory, clock=lambda: 0)
        sock.sendto.assert_not_called()
        sock.close.assert_called_once()

    def test_packet_limit_without_marker_is_incomplete(self):
        wire = struct.pack('<5I', 4, 400, 1, 2, 12)
        sock, factory = self.socket([(wire, (7, q.CTRL))] * 256)
        result = q.query(create=factory, clock=lambda: 0)
        self.assertFalse(result['complete'])
        self.assertEqual(sock.recvfrom.call_count, 256)

    def test_invalid_deadline_opens_no_socket(self):
        factory = Mock()
        for seconds in (0, -1, 4):
            with self.assertRaises(ValueError):
                q.query(seconds, create=factory)
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
