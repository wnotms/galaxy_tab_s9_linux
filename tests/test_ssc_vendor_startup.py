import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('vendor_startup', ROOT/'userspace/sensors/read-vendor-sensor-startup.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
FLOW_SPEC = importlib.util.spec_from_file_location('startup395_flow',
    ROOT/'reference/boot-tests/test-395-stock-sensor-startup/host_flow.py')
FLOW = importlib.util.module_from_spec(FLOW_SPEC)
FLOW_SPEC.loader.exec_module(FLOW)


class VendorStartupTests(unittest.TestCase):
    def tree(self, directory='lib64', name='libsns_client.so', data=b'input'):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        path = root/directory/name
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
        return root, path

    def test_exact_selected_scope(self):
        for directory, name in [('bin', 'sscrpcd'), ('bin/hw', 'vendor.sensors-service'),
                                ('etc/init', 'sensors.rc'), ('lib64', 'libadsprpc.so'),
                                ('lib/hw', 'sensors.ssc.so')]:
            self.assertTrue(M.selected(directory, name))
        for directory, name in [('bin', 'sh'), ('lib64', 'libcamera.so'),
                                ('lib64', '../libsns.so'), ('vendor/lib64', 'libsns.so')]:
            self.assertFalse(M.selected(directory, name))

    def test_original_bytes_hash_and_mtime(self):
        root, path = self.tree(data=b'\x00\xff\r\n')
        data, files, inventory = M.inspect_tree(root)
        name = 'vendor/lib64/libsns_client.so'
        self.assertEqual(data[name], path.read_bytes())
        self.assertEqual(files[name]['sha256'], M.hashlib.sha256(data[name]).hexdigest())
        self.assertEqual(files[name]['source_mtime_ns'], path.stat().st_mtime_ns)
        self.assertIsNone(inventory['lib/hw'])

    def test_elf_machine_is_metadata_not_executed(self):
        elf = bytearray(20)
        elf[:6] = b'\x7fELF\x02\x01'
        elf[18:20] = (183).to_bytes(2, 'little')
        root, _ = self.tree(data=elf)
        self.assertEqual(M.inspect_tree(root)[1]['vendor/lib64/libsns_client.so']['elf_machine'], 183)

    def test_selected_symlink_refused(self):
        root, path = self.tree()
        path.with_name('libsns_other.so').symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            M.inspect_tree(root)

    def test_linked_parent_refused(self):
        root, path = self.tree()
        (root/'lib').symlink_to(path.parent)
        with self.assertRaisesRegex(ValueError, 'linked'):
            M.inspect_tree(root)

    def test_unselected_symlink_never_followed(self):
        root, _ = self.tree()
        (root/'lib64/libcamera.so').symlink_to('/missing')
        self.assertEqual(len(M.inspect_tree(root)[1]), 1)

    def test_file_total_and_member_bounds(self):
        root, _ = self.tree()
        for name, limit in [('MAX_FILE_BYTES', 1), ('MAX_TOTAL_BYTES', 1), ('MAX_FILES', 0)]:
            with self.subTest(name=name), patch.object(M, name, limit):
                with self.assertRaisesRegex(ValueError, 'export bound'):
                    M.inspect_tree(root)

    def test_empty_selected_set_refused(self):
        root, path = self.tree(name='libcamera.so')
        with self.assertRaisesRegex(ValueError, 'no stock'):
            M.inspect_tree(root)

    def mount(self, failure=None):
        calls, state = [], {'mounted': False}
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        work = Path(temp.name)/'owned'
        work.mkdir()
        def run(argv):
            calls.append(argv)
            if argv[0] == failure:
                raise RuntimeError('injected ' + failure)
            if argv[0] == 'losetup' and '--show' in argv:
                return '/dev/loop7'
            if argv[0] == 'blkid':
                return 'ext4'
            if argv[0] == 'mount':
                state['mounted'] = True
            if argv[0] == 'umount':
                state['mounted'] = False
            return ''
        layout = SimpleNamespace(run=run, read=lambda _: '1',
            mounted=lambda p: [['/dev/loop7', str(p), 'ext4', 'ro,nosuid,nodev,noexec,noload']]
                if state['mounted'] else [])
        return calls, state, work, layout

    def test_success_unmount_before_detach(self):
        calls, state, work, layout = self.mount()
        with patch.object(M.tempfile, 'mkdtemp', return_value=str(work)):
            with M.readonly_vendor(layout, '/dev/super', {'offset': 4096, 'bytes': 4096}):
                self.assertTrue(state['mounted'])
        self.assertEqual(calls[-2:], [['umount', str(work)], ['losetup', '--detach', '/dev/loop7']])
        self.assertFalse(work.exists())
        self.assertIn('ro,nosuid,nodev,noexec,noload', calls[2])
        self.assertIn('--read-only', calls[0])

    def test_read_failure_still_cleans_owned_mount(self):
        calls, state, work, layout = self.mount()
        with patch.object(M.tempfile, 'mkdtemp', return_value=str(work)):
            with self.assertRaisesRegex(RuntimeError, 'read failure'):
                with M.readonly_vendor(layout, '/dev/super', {'offset': 4096, 'bytes': 4096}):
                    raise RuntimeError('read failure')
        self.assertFalse(state['mounted'])
        self.assertEqual(calls[-1], ['losetup', '--detach', '/dev/loop7'])

    def test_mount_failure_detaches_unmounted_loop(self):
        calls, state, work, layout = self.mount(failure='mount')
        with patch.object(M.tempfile, 'mkdtemp', return_value=str(work)):
            with self.assertRaisesRegex(RuntimeError, 'injected mount'):
                with M.readonly_vendor(layout, '/dev/super', {'offset': 4096, 'bytes': 4096}):
                    self.fail('failed mount entered')
        self.assertEqual(calls[-1], ['losetup', '--detach', '/dev/loop7'])
        self.assertFalse(work.exists())

    def test_unmount_failure_never_detaches_or_claims_cleanup(self):
        calls, state, work, layout = self.mount(failure='umount')
        with patch.object(M.tempfile, 'mkdtemp', return_value=str(work)):
            with self.assertRaisesRegex(RuntimeError, 'injected umount'):
                with M.readonly_vendor(layout, '/dev/super', {'offset': 4096, 'bytes': 4096}):
                    pass
        self.assertTrue(state['mounted'])
        self.assertTrue(work.exists())
        self.assertFalse(any('--detach' in c for c in calls))


class VendorStartupScopeTests(unittest.TestCase):
    def archive(self, *, wrong_hash=False, boot=None, cleaned=True, executed=False,
                duplicate=False, name='vendor/lib64/libsns_client.so', empty=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)/'stock.tar.gz'
        data = b'original ELF bytes'
        manifest = dict(boot_id=boot or FLOW.PLAN['boot_id'],
            purpose='READ_ONLY_X710_SENSOR_STARTUP_INPUTS',
            temporary_mount_and_loop_removed=cleaned, binaries_executed=executed,
            DSP_started=False, partitions_written=False, registry_written=False,
            files={} if empty else {name: dict(bytes=len(data),
                sha256='0'*64 if wrong_hash else hashlib.sha256(data).hexdigest())})
        with tarfile.open(path, 'w:gz') as archive:
            items = [('MANIFEST.json', json.dumps(manifest).encode())]
            if not empty:
                items += [(name, data)] * (2 if duplicate else 1)
            for filename, raw in items:
                info = tarfile.TarInfo(filename)
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
        return path

    def test_real_archive_bytes_verified(self):
        result = FLOW.archive_manifest(self.archive(), FLOW.PLAN['boot_id'])
        self.assertEqual(len(result['files']), 1)
        self.assertFalse(result['binaries_executed'])

    def test_hash_boot_cleanup_and_execution_refused(self):
        for changes in [dict(wrong_hash=True), dict(boot='other-boot'),
                        dict(cleaned=False), dict(executed=True), dict(duplicate=True)]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    FLOW.archive_manifest(self.archive(**changes), FLOW.PLAN['boot_id'])

    def test_path_traversal_and_unselected_payload_refused(self):
        for name in ['vendor/lib64/../libsns_client.so', '/vendor/lib64/libsns_client.so',
                     'vendor/lib64/libcamera.so']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                FLOW.archive_manifest(self.archive(name=name), FLOW.PLAN['boot_id'])

    def test_manifest_without_original_inputs_refused(self):
        with self.assertRaisesRegex(ValueError, 'disagreement'):
            FLOW.archive_manifest(self.archive(empty=True), FLOW.PLAN['boot_id'])

    def test_unpushed_registration_stops_before_adb(self):
        with patch.object(FLOW, 'verify', side_effect=ValueError('unpushed')), \
                patch.object(FLOW, 'snapshot') as snapshot:
            with self.assertRaisesRegex(ValueError, 'unpushed'):
                FLOW.run()
            snapshot.assert_not_called()

    def test_consumed_export_never_replayed(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        (folder/'execution').mkdir()
        with patch.object(FLOW, 'R', folder), patch.object(FLOW, 'verify'), \
                patch.object(FLOW, 'snapshot') as snapshot:
            with self.assertRaisesRegex(ValueError, 'already consumed'):
                FLOW.run()
            snapshot.assert_not_called()

    def test_stale_preflight_stops_before_adb(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        (folder/'preflight').mkdir()
        (folder/'preflight/summary.json').write_text(json.dumps(
            dict(verdict='READONLY_PREFLIGHT_PASS', epoch=0)))
        with patch.object(FLOW, 'R', folder), patch.object(FLOW, 'verify'), \
                patch.object(FLOW, 'snapshot') as snapshot:
            with self.assertRaisesRegex(ValueError, 'stale'):
                FLOW.run()
            snapshot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
