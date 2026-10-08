"""Test366: real transaction fixtures, bounded QRTR protocol and recovery wiring."""
import importlib.util
import json
from pathlib import Path
import socket
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-366-ssc-escape-trace'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


Q = load('ssc366_qrtr_tests', ROOT / 'userspace/sensors/qrtr-snapshot.py')
D = load('ssc366_desktop_tests', R / 'desktop.py')
M = load('ssc366_runtime_tests', R / 'runtime.py')
H = load('ssc366_flow_tests', R / 'host_flow.py')
O = load('ssc365_reused_runtime_fixtures', ROOT / 'tests/test_ssc_runtime_transaction.py')
G = load('ssc364_reused_identity_fixtures', ROOT / 'tests/test_early_adsp_controlled_boot.py')


class QRTRTests(unittest.TestCase):
    def test_native_header_encoding(self):
        self.assertEqual(Q.packet(Q.NEW_LOOKUP), b'\x0a\0\0\0' + b'\0' * 16)
        self.assertIsNone(Q.decode(struct.pack('<5I', 4, 0, 0, 0, 0)))
        self.assertEqual(Q.decode(struct.pack('<5I', 4, 400, 1, 2, 12))['service'], 400)

    def test_malformed_control_rejected(self):
        for data in (b'', bytes(19), bytes(21), Q.packet(5)):
            with self.assertRaises(ValueError): Q.decode(data)

    def query(self, packets):
        sock = Mock(); sock.getsockname.return_value = (1, 123)
        sock.recvfrom.side_effect = packets
        create = Mock(return_value=sock)
        return sock, create

    def test_complete_listing_keeps_raw_and_closes_lookup(self):
        sock, create = self.query([(struct.pack('<5I', 4, 400, 1, 2, 12), (1, Q.CTRL)),
                                   (Q.packet(4), (1, Q.CTRL))])
        result = Q.query(create=create, clock=lambda: 0)
        self.assertTrue(result['complete']); self.assertEqual(len(result['raw_packets']), 2)
        self.assertEqual(result['services'][0]['port'], 12)
        self.assertEqual(sock.sendto.call_args_list[-1].args, (Q.packet(11), (1, Q.CTRL)))
        sock.close.assert_called_once()

    def test_timeout_is_incomplete_not_empty_complete(self):
        sock, create = self.query([socket.timeout()])
        result = Q.query(create=create, clock=lambda: 0)
        self.assertFalse(result['complete']); sock.close.assert_called_once()

    def test_foreign_nameserver_and_malformed_reply_close_socket(self):
        for packet in ((Q.packet(4), (2, Q.CTRL)), (bytes(3), (1, Q.CTRL))):
            sock, create = self.query([packet])
            with self.assertRaises(Q.LookupFault) as caught: Q.query(create=create, clock=lambda: 0)
            self.assertEqual(caught.exception.raw[0]['hex'], packet[0].hex())
            sock.close.assert_called_once()

    def test_packet_count_and_time_are_bounded(self):
        packet = (struct.pack('<5I', 4, 400, 1, 2, 12), (1, Q.CTRL))
        sock, create = self.query([packet] * 256)
        result = Q.query(create=create, clock=lambda: 0)
        self.assertFalse(result['complete']); self.assertEqual(sock.recvfrom.call_count, 256)
        for seconds in (0, 4):
            with self.assertRaises(ValueError): Q.query(seconds, create=create)


class DesktopOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'root'; self.incoming = Path(self.tmp.name) / 'incoming'
        (self.root / 'etc').mkdir(parents=True); self.incoming.mkdir()
        (self.root / 'etc/machine-id').write_text(D.MACHINE)
        self.manifest = {}; self.originals = {}
        for i, name in enumerate(sorted(D.ALLOWED)):
            data = ('candidate' + name).encode(); incoming = 'overlay-' + str(i)
            (self.incoming / incoming).write_bytes(data)
            original = None
            if name.startswith('usr/local/libexec/'):
                old = ('original' + name).encode(); p = self.root / name
                p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(old)
                original = D.digest(old); self.originals[name] = old
            self.manifest[name] = dict(incoming=incoming, sha256=D.digest(data),
                                       mode=0o644, original_sha256=original)

    def install(self): return D.install(self.root, self.incoming, self.manifest)

    def test_install_restore_exact_originals_and_absent_owned_files(self):
        self.install(); result = D.restore(self.root)
        self.assertEqual(result['verdict'], 'EXACT_DESKTOP_FILES_RESTORED')
        for name in D.ALLOWED:
            if name in self.originals: self.assertEqual((self.root / name).read_bytes(), self.originals[name])
            else: self.assertFalse((self.root / name).exists())
        self.assertEqual(D.restore(self.root)['verdict'], 'NO_DESKTOP_LEDGER_NO_MUTATION')

    def test_wrong_original_refused_before_ledger_or_copy(self):
        name = next(iter(self.originals)); (self.root / name).write_bytes(b'different')
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.root / D.STATE).exists())

    def test_incoming_symlink_and_bad_content_rejected(self):
        row = next(iter(self.manifest.values())); p = self.incoming / row['incoming']
        p.write_bytes(b'different')
        with self.assertRaises(ValueError): self.install()
        p.unlink(); p.symlink_to(self.root / 'etc/machine-id')
        with self.assertRaises(ValueError): self.install()

    def test_partial_install_failure_can_restore(self):
        original = D.atomic; count = 0
        def fail(path, *args, **kwargs):
            nonlocal count
            count += 1
            if count == 4: raise OSError('mock disk failure')
            return original(path, *args, **kwargs)
        with patch.object(D, 'atomic', side_effect=fail):
            with self.assertRaises(OSError): self.install()
        D.restore(self.root)
        for name, value in self.originals.items(): self.assertEqual((self.root / name).read_bytes(), value)

    def test_corrupt_original_backup_stops_before_any_restore(self):
        self.install(); backup = next((self.root / D.BACKUPS).iterdir()); backup.write_bytes(b'corrupt')
        name = next(iter(self.originals)); before = (self.root / name).read_bytes()
        with self.assertRaises(ValueError): D.restore(self.root)
        self.assertEqual((self.root / name).read_bytes(), before)

    def test_unknown_current_file_and_backup_and_ledger_refused(self):
        self.install(); name = next(iter(self.originals)); p = self.root / name; candidate = p.read_bytes()
        p.write_bytes(b'unknown')
        with self.assertRaises(ValueError): D.restore(self.root)
        p.write_bytes(candidate)
        backup = self.root / D.BACKUPS / 'unknown'; backup.write_bytes(b'unknown')
        with self.assertRaises(ValueError): D.restore(self.root)
        self.assertEqual(p.read_bytes(), candidate); backup.unlink()
        ledger = self.root / D.STATE; state = json.loads(ledger.read_text())
        state['created_dirs'].append('etc/ssh'); ledger.write_text(json.dumps(state))
        with self.assertRaises(ValueError): D.restore(self.root)

    def test_wrong_machine_and_extra_target_and_double_install_refused(self):
        (self.root / 'etc/machine-id').write_text('unknown')
        with self.assertRaises(ValueError): self.install()
        (self.root / 'etc/machine-id').write_text(D.MACHINE)
        extra = self.manifest | {'etc/ssh/sshd_config': next(iter(self.manifest.values()))}
        with self.assertRaises(ValueError): D.install(self.root, self.incoming, extra)
        self.install()
        with self.assertRaises(ValueError): self.install()


class AssetTransactionTests(G.AssetTransactionTests):
    def setUp(self):
        assets = load('ssc366_assets_tests', R / 'assets.py')
        patcher = patch.object(G, 'A', assets)
        patcher.start(); self.addCleanup(patcher.stop)
        super().setUp()


class TraceRuntimeTests(O.RuntimeTransactionTests):
    """Exercise retained transaction invariants against the new actual runtime."""
    def setUp(self):
        patcher = patch.multiple(O, M=M, PLAN=H.PLAN | {'boot_id': '11111111-1111-1111-1111-111111111111'})
        patcher.start(); self.addCleanup(patcher.stop)
        super().setUp()
        self.runner.plan = dict(self.runner.plan)
        for name, key in (('usr/local/lib/gts9-test366/hexagonrpcd', 'trace_sha256'),
                          ('usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4', 'trace_library_sha256')):
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(name.encode())
            self.runner.plan[key] = M.sha(p)
        p = self.root / 'usr/bin/stdbuf'; p.parent.mkdir(parents=True, exist_ok=True); p.touch()
        self.bad_unit = False

    def invoke(self, argv, **kwargs):
        if argv[:2] == ['systemctl', 'show']:
            return 'original-daemon' if self.bad_unit else '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test366/hexagonrpcd'
        return super().invoke(argv, **kwargs)

    def test_corrupt_trace_or_library_blocks_gate_and_launch(self):
        self.prepare()
        for name in ('usr/local/lib/gts9-test366/hexagonrpcd', 'usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4'):
            p = self.root / name; original = p.read_bytes(); p.write_bytes(b'bad')
            with self.assertRaises(ValueError): self.runner.start()
            self.assertFalse(self.runner.path(M.GATE).exists()); self.assertFalse(self.state()['started'])
            p.write_bytes(original)

    def test_unresolved_trace_unit_blocks_gate_and_launch(self):
        self.prepare(); self.bad_unit = True
        with self.assertRaises(ValueError): self.runner.start()
        self.assertFalse(self.runner.path(M.GATE).exists()); self.assertFalse(self.state()['started'])

    def test_lost_launch_reply_cannot_replay_start(self):
        self.prepare(); original = self.invoke
        def lost(argv, **kwargs):
            if argv[:2] == ['systemctl', 'start']:
                raise OSError('lost actual launch reply')
            return original(argv, **kwargs)
        self.runner.invoke = lost
        with self.assertRaises(OSError): self.runner.start()
        self.assertTrue(self.state()['started'])
        with self.assertRaises(ValueError): self.runner.start()


class TraceFlowTests(unittest.TestCase):
    def packet(self, phase='candidate'):
        value = G.ControlledBootGateTests().packet()
        value['config_sha256'] = H.PLAN[phase + '_config_sha256']
        value['notes_sha256'] = H.PLAN[phase + '_notes_sha256']
        value['failed_units'] = ''
        return value

    def test_native_sample_parser_and_noise_rejection(self):
        self.assertEqual(H.sample('Accelerometer sensor measurement: X=0 Y=9.8 Z=0 m/s²')['y'], 9.8)
        self.assertIsNone(H.sample('SSC service not available'))
        with self.assertRaises(ValueError): H.sample('Accelerometer sensor measurement: X=nan Y=0 Z=0 m/s²')

    def test_baseline_gnome_allowed_but_candidate_admission_text_only(self):
        value = self.packet('baseline'); value['services']['gdm'] = 'active'; value['services']['gts9-palm'] = 'active'
        H.identity(value, 'baseline', value['boot_id'])
        value.update(config_sha256=H.PLAN['candidate_config_sha256'], notes_sha256=H.PLAN['candidate_notes_sha256'])
        with self.assertRaises(ValueError): H.identity(value, 'candidate')

    def test_correct_namespace_recovery_guard_before_partition_writes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(H, 'R', Path(tmp)):
            (Path(tmp) / 'mutation-state.json').write_text(json.dumps({'rollback_required': True}))
            rec = Mock(); rec.folder = Path(tmp)
            def adb(name, command, **kwargs):
                if name == 'twrp-identity': return 'gts9wifi Linux 4.19 uid=0', 0
                if name == 'partitions-before': return 'fixture', 0
                if name == 'restore-modules':
                    self.assertIn('.gts9-test366-original', command)
                    self.assertNotIn('test364', command)
                    raise ValueError('wrong/corrupt backup')
                return '', 0
            rec.adb.side_effect = adb
            with patch.object(H.p, 'Recorder', return_value=rec), patch.object(H, 'transfer'), \
                 patch.object(H, 'restore_layout', return_value=H.PACKAGE['candidate_partitions']), \
                 patch.object(H, 'write_partition') as write_partition:
                with self.assertRaises(ValueError): H.restore(True)
                write_partition.assert_not_called()

    def test_new_image_driver_profile_and_no_charging_scope(self):
        q = json.loads((ROOT / 'reference/desktop-bringup/ssc-keyboard-candidate/QUALIFICATION.json').read_text())
        self.assertEqual(H.PACKAGE['artifacts']['boot.img'], q['boot'])
        self.assertEqual(H.PLAN['candidate_notes_sha256'], q['notes_sha256'])
        self.assertFalse(H.PLAN['PPS']); self.assertFalse(H.PLAN['pump_ON'])
        source = (R / 'host_flow.py').read_text()
        self.assertNotIn("test-364-early-adsp-socinfo/host_flow.py", source)
        self.assertEqual(D.STATE, 'var/lib/gts9-test366/desktop.json')
        self.assertIn('test366', (R / 'assets.py').read_text())

    def test_boundary_and_evidence_faults_still_attempt_runtime_stop_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(H, 'R', Path(tmp)):
            boot = '11111111-1111-1111-1111-111111111111'
            (Path(tmp) / 'mutation-state.json').write_text(json.dumps({'phase': 'accepted-candidate-kept-text', 'boot_id': boot}))
            rec = Mock(); rec.folder = Path(tmp)
            with patch.object(H.p, 'Recorder', return_value=rec), \
                 patch.object(H, 'snapshot', side_effect=ValueError('boundary identity')), \
                 patch.object(H, 'collect_runtime', side_effect=OSError('evidence unavailable')), \
                 patch.object(H, 'qrtr', side_effect=OSError('lookup unavailable')), \
                 patch.object(H, 'runtime', side_effect=OSError('stop reply lost')) as runtime, \
                 patch.object(H, 'restore') as restore:
                with self.assertRaisesRegex(ValueError, 'boundary identity'): H.discover()
                runtime.assert_called_once_with(rec, 'deactivate', boot)
                restore.assert_called_once()
            self.assertTrue(json.loads((Path(tmp) / 'first-runtime-failure.json').read_text())['no_retry'])

    def test_first_malformed_sample_stops_without_another_launch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(H, 'R', Path(tmp)):
            value = self.packet(); boot = value['boot_id']
            (Path(tmp) / 'mutation-state.json').write_text(json.dumps({'phase': 'accepted-candidate-kept-text', 'boot_id': boot}))
            (Path(tmp) / 'runtime-packages.json').write_bytes((R / 'runtime-packages.json').read_bytes())
            rec = Mock(); rec.folder = Path(tmp)
            def adb(name, command, **kwargs):
                if name.startswith('trace-size-'): return '0', 0
                if name.startswith('accelerometer-'): return 'Accelerometer sensor measurement: X=nan Y=0 Z=0 m/s²', 0
                return '', 0
            rec.adb.side_effect = adb
            wanted = ['runtime.py', 'capture.py', 'map-socinfo.py', 'qrtr-snapshot.py', 'runtime-packages.json', 'runtime-overrides.json']
            wanted += [x['filename'] for x in H.read(R / 'runtime-packages.json')]
            with patch.object(H.p, 'Recorder', return_value=rec), patch.object(H, 'snapshot', return_value=value), \
                 patch.object(H, 'native_gate'), patch.object(H, 'wifi'), \
                 patch.object(H, 'verify_stage', return_value={n: {'sha256': '0' * 64} for n in wanted}), \
                 patch.object(H, 'runtime') as runtime, patch.object(H, 'qrtr'), \
                 patch.object(H, 'collect_runtime'), patch.object(H, 'restore') as restore:
                with self.assertRaisesRegex(ValueError, 'invalid accelerometer'): H.discover()
                self.assertEqual([c.args[1] for c in runtime.call_args_list], ['prepare', 'start', 'deactivate'])
                restore.assert_called_once()


if __name__ == '__main__': unittest.main()
