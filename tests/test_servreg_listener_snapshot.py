"""PDR private-client lifecycle with literal wire fixtures; no tablet access."""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pdr_listener', ROOT / 'userspace/sensors/servreg-listener-snapshot.py')
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
PRIOR = ROOT / 'reference/boot-tests/test-392-sensor-pd-canonical-boot/runtime-discovery'
INVENTORY = json.loads((PRIOR / 'qrtr-before.json').read_text())
DOMAINS = json.loads((PRIOR / 'servreg-domains.json').read_text())
BOOT = INVENTORY['boot_id']
OTHER = '22222222-2222-4222-8222-222222222222'
TRUE = bytes.fromhex('00010020001900010100010212006d736d2f616473702f73656e736f725f7064')
FALSE = bytes.fromhex('00020020001900010100000212006d736d2f616473702f73656e736f725f7064')
UP = bytes.fromhex('02010020000e0002040000000000100400ffffff1f')
UNREGISTER = bytes.fromhex('0202002000070002040000000000')
NO_STATE = bytes.fromhex('0201002000070002040000000000')
ERROR9 = bytes.fromhex('0201002000070002040001000900')
IND = bytes.fromhex('047b0022002100010400ffffff1f0212006d736d2f616473702f73656e736f725f70640302003412')
ACK = bytes.fromhex('00030023001a000112006d736d2f616473702f73656e736f725f70640202003412')
ACK_REPLY = bytes.fromhex('0203002300070002040000000000')


class WireTests(unittest.TestCase):
    def test_register_and_unregister_literal_bytes_distinct_transactions(self):
        self.assertEqual(L.register(1, True), TRUE)
        self.assertEqual(L.register(2, False), FALSE)

    def test_ack_echoes_body_transaction_not_indication_header_transaction(self):
        kind, header_tid, method, fields = L.packet(IND)
        self.assertEqual((kind, header_tid, method), (4, 123, 0x22))
        self.assertEqual(L.indication(fields), (0x1fffffff, 0x1234))
        self.assertEqual(L.acknowledge(3, 0x1234), ACK)

    def test_all_pinned_state_values(self):
        for state in (1, 0x0fffffff, 0x1fffffff, 0x2fffffff, 0x7fffffff):
            with self.subTest(state=state):
                self.assertEqual(L.response(L.packet(UP[:-4] + struct.pack('<I', state))[3], L.REGISTER), state)

    def test_current_state_optional_not_default_up(self):
        self.assertIsNone(L.response(L.packet(NO_STATE)[3], L.REGISTER))

    def test_invalid_result_state_and_unexpected_tags(self):
        valid = L.packet(UP)[3]
        cases = ({2: b'\1\0\11\0'}, {2: b'\0\0'}, {2: b'\0'*4, 16: b'\0'*4},
                 {2: b'\0'*4, 16: b'\0'}, valid | {17: b'\0'})
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                L.response(fields, L.REGISTER)
        with self.assertRaises(ValueError): L.response(valid, L.ACK)

    def test_packet_truncation_duplicate_tlv_and_size_rejected(self):
        for data in (b'', UP[:6], UP[:-1], UP+b'\0',
                     bytes.fromhex('020100200008000204000000000010'),
                     bytes.fromhex('02010020000e000204000000000002040000000000')):
            with self.subTest(data=data), self.assertRaises(ValueError): L.packet(data)

    def test_invalid_indication_domain_state_or_token(self):
        valid = L.packet(IND)[3]
        for changes in ({2:b'msm/adsp/root_pd'}, {1:b'\0'*4}, {1:b'\0'}, {3:b'\0'}, {4:b'\0'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                L.indication(valid | changes)

    def test_invalid_request_parameters(self):
        for txn, enable in ((0, True), (65536, True), (True, True), (1, 1)):
            with self.assertRaises(ValueError): L.register(txn, enable)
        for txn, tid in ((0, 1), (3, -1), (3, 65536), (3, True)):
            with self.assertRaises(ValueError): L.acknowledge(txn, tid)


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.sock = Mock(); self.sock.getsockname.return_value=(1,16388)
        self.sock.sendto.side_effect=lambda data, peer: len(data)
        self.factory=Mock(return_value=self.sock)
        self.kw=dict(expected_boot=BOOT,create=self.factory,clock=lambda:0,boot=lambda:BOOT)
        self.queue=[UP,UNREGISTER]
        def recv(size):
            if not self.queue:raise socket.timeout('quiet')
            data=self.queue.pop(0)
            if isinstance(data,Exception):raise data
            return data if isinstance(data,tuple) else (data,(5,3))
        self.sock.recvfrom.side_effect=recv

    def query(self,**kwargs):return L.query(INVENTORY,DOMAINS,**(self.kw|kwargs))
    def sends(self):return [c.args[0] for c in self.sock.sendto.call_args_list]

    def test_one_register_same_socket_unregister_close_no_sensor_claim(self):
        d=self.query()
        self.assertEqual(self.sends(),[TRUE,FALSE])
        self.sock.bind.assert_called_once_with((1,0));self.sock.close.assert_called_once()
        self.assertTrue(d['complete']);self.assertTrue(d['registered_acknowledged'])
        self.assertTrue(d['unregister_acknowledged']);self.assertFalse(d['listener_registered'])
        self.assertTrue(d['socket_closed']);self.assertEqual(d['domain_state'],'UP')
        self.assertFalse(d['DSP_started']);self.assertFalse(d['SSC_service_verified'])
        self.assertFalse(d['accelerometer_verified'])

    def test_indication_before_register_reply_acknowledged(self):
        self.queue=[IND,ACK_REPLY,UP,UNREGISTER]
        d=self.query();self.assertEqual(self.sends(),[TRUE,ACK,FALSE])
        self.assertEqual(d['indications'][0]['indication_transaction'],0x1234)
        self.assertTrue(d['complete'])

    def test_indication_during_cleanup_out_of_order_ack_response(self):
        self.queue=[UP,IND,UNREGISTER,ACK_REPLY]
        d=self.query();self.assertEqual(self.sends(),[TRUE,FALSE,ACK])
        self.assertTrue(d['complete'])

    def test_queued_indication_after_unregister_response_drained(self):
        self.queue=[UP,UNREGISTER,IND,ACK_REPLY]
        d=self.query();self.assertEqual(self.sends(),[TRUE,FALSE,ACK])
        self.assertTrue(d['complete'])

    def test_missing_initial_state_unregisters_but_remains_unknown(self):
        self.queue=[NO_STATE,UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        d=e.exception.evidence;self.assertFalse(d['complete']);self.assertTrue(d['unregister_acknowledged'])
        self.assertEqual(d['domain_state'],'UNKNOWN');self.assertEqual(self.sends(),[TRUE,FALSE])
        self.sock.close.assert_called_once()

    def test_actual_error9_not_recast_as_down_or_up(self):
        self.queue=[ERROR9,UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertIn('result=1 error=9',str(e.exception))
        self.assertEqual(e.exception.evidence['raw_packets'][0]['hex'],ERROR9.hex())
        self.assertFalse(e.exception.evidence['complete']);self.sock.close.assert_called_once()

    def test_register_timeout_late_reply_then_verified_cleanup_not_pass(self):
        self.queue=[socket.timeout('register timeout'),UP,UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        d=e.exception.evidence;self.assertTrue(d['unregister_acknowledged'])
        self.assertFalse(d['complete']);self.assertNotIn('state_value',d)
        self.assertEqual(self.sends(),[TRUE,FALSE]);self.sock.close.assert_called_once()

    def test_unregister_timeout_closes_and_does_not_claim_remote_cleanup(self):
        self.queue=[UP,socket.timeout('unregister timeout')]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        d=e.exception.evidence;self.assertTrue(d['socket_closed'])
        self.assertFalse(d['unregister_acknowledged']);self.assertFalse(d['complete'])
        self.assertTrue(d['listener_registered'])
        self.assertEqual(self.sends(),[TRUE,FALSE])

    def test_foreign_peer_no_ack_and_raw_retained(self):
        self.queue=[(IND,(7,3)),UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertEqual(e.exception.evidence['raw_packets'][0]['peer'],[7,3])
        self.assertEqual(self.sends(),[TRUE,FALSE]);self.sock.close.assert_called_once()

    def test_foreign_domain_no_ack_then_unregister(self):
        bad=bytearray(IND);bad[20]^=1
        self.queue=[bytes(bad),UNREGISTER]
        with self.assertRaises(L.S.EvidenceError):self.query()
        self.assertEqual(self.sends(),[TRUE,FALSE])

    def test_duplicate_indication_no_second_ack(self):
        self.queue=[IND,IND,UNREGISTER,ACK_REPLY]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertIn('duplicate/excess',str(e.exception))
        self.assertEqual(self.sends(),[TRUE,ACK,FALSE]);self.sock.close.assert_called_once()

    def test_failed_ack_prevents_success(self):
        bad=bytearray(ACK_REPLY);bad[-4]=1;bad[-2]=9
        self.queue=[IND,bytes(bad),UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertFalse(e.exception.evidence['complete']);self.sock.close.assert_called_once()

    def test_missing_ack_prevents_success_even_with_register_reply(self):
        self.queue=[IND,UP,socket.timeout('ACK'),UNREGISTER,socket.timeout('ACK')]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertFalse(e.exception.evidence['complete']);self.sock.close.assert_called_once()

    def test_bad_response_type_transaction_method_or_duplicate_rejected(self):
        for index in (0,1,3):
            self.setUp();bad=bytearray(UP);bad[index]^=1;self.queue=[bytes(bad),UNREGISTER]
            with self.subTest(index=index),self.assertRaises(L.S.EvidenceError):self.query()
            self.sock.close.assert_called_once()
        self.setUp();self.queue=[UP,UP,UNREGISTER]
        with self.assertRaises(L.S.EvidenceError):self.query()

    def test_malformed_reply_preserved_then_cleanup(self):
        self.queue=[b'bad',UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertEqual(e.exception.evidence['raw_packets'][0]['hex'],'626164')
        self.assertEqual(self.sends(),[TRUE,FALSE])

    def test_boot_changed_before_socket_sends_nothing(self):
        with self.assertRaises(L.S.EvidenceError):self.query(boot=lambda:OTHER)
        self.factory.assert_not_called()

    def test_boot_changed_after_send_never_unregisters_against_new_boot(self):
        with self.assertRaises(L.S.EvidenceError) as e:
            self.query(boot=Mock(side_effect=[BOOT,BOOT,OTHER,OTHER]))
        self.assertEqual(self.sends(),[TRUE]);self.assertFalse(e.exception.evidence['complete'])
        self.sock.close.assert_called_once()

    def test_boot_changed_during_quiet_drain_invalidates_success(self):
        with self.assertRaises(L.S.EvidenceError) as e:
            self.query(boot=Mock(side_effect=[BOOT]*6+[OTHER]))
        self.assertFalse(e.exception.evidence['complete']);self.sock.close.assert_called_once()

    def test_unbound_socket_failure_does_not_send_unregister(self):
        self.sock.bind.side_effect=OSError('bind')
        with self.assertRaises(L.S.EvidenceError):self.query()
        self.sock.sendto.assert_not_called();self.sock.close.assert_called_once()

    def test_socket_creation_failure_no_send(self):
        self.factory.side_effect=OSError('create')
        with self.assertRaises(L.S.EvidenceError):self.query()
        self.sock.sendto.assert_not_called()

    def test_registration_send_error_still_attempts_same_client_cleanup(self):
        self.sock.sendto.side_effect=[OSError('send'),len(FALSE)]
        self.queue=[UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertEqual(self.sends(),[TRUE,FALSE]);self.assertTrue(e.exception.evidence['unregister_acknowledged'])
        self.sock.close.assert_called_once()

    def test_short_send_rejected_then_cleanup(self):
        self.sock.sendto.side_effect=[1,len(FALSE)];self.queue=[UNREGISTER]
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertIn('incomplete',str(e.exception));self.sock.close.assert_called_once()

    def test_packet_bound_stops_without_infinite_receive_or_register_retry(self):
        self.queue=[IND,ACK_REPLY,UP,UNREGISTER]
        with patch.object(L,'MAX_PACKETS',2),self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertIn('packet bound',str(e.exception))
        self.assertEqual(self.sends(),[TRUE,ACK,FALSE]);self.sock.close.assert_called_once()

    def test_indication_bound_stops_and_retains_first_event(self):
        self.queue=[IND,ACK_REPLY,IND[:-2]+b'\x35\x12',UNREGISTER]
        with patch.object(L,'MAX_INDICATIONS',1),self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertEqual(len(e.exception.evidence['indications']),1)
        self.assertEqual(self.sends(),[TRUE,ACK,FALSE]);self.sock.close.assert_called_once()

    def test_expired_registration_budget_sends_nothing(self):
        with self.assertRaises(L.S.EvidenceError):
            self.query(clock=Mock(side_effect=[0,3,3]))
        self.sock.sendto.assert_not_called();self.sock.close.assert_called_once()

    def test_deadline_not_extended_by_indication(self):
        now=[0.0]
        def recv(_):
            now[0]=3
            return IND,(5,3)
        self.sock.recvfrom.side_effect=recv
        # Both phases reject packets received after their own deadlines.
        def timeout_recv(_):raise socket.timeout('cleanup')
        def send(data,_):
            if data==FALSE:self.sock.recvfrom.side_effect=timeout_recv
            return len(data)
        self.sock.sendto.side_effect=send
        with self.assertRaises(L.S.EvidenceError):self.query(clock=lambda:now[0])
        self.assertEqual(self.sends(),[TRUE,FALSE]);self.sock.close.assert_called_once()

    def test_failed_close_keeps_evidence_noncomplete(self):
        self.sock.close.side_effect=OSError('close')
        with self.assertRaises(L.S.EvidenceError) as e:self.query()
        self.assertFalse(e.exception.evidence['complete']);self.assertFalse(e.exception.evidence['socket_closed'])

    def test_bad_endpoint_evidence_creates_no_socket(self):
        d=copy.deepcopy(INVENTORY);d['complete']=False
        with self.assertRaises(ValueError):L.query(d,DOMAINS,**self.kw)
        self.factory.assert_not_called()


if __name__=='__main__':unittest.main()
