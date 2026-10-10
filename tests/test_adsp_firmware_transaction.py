import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'adsp_transaction_test', ROOT/'userspace/sensors/adsp_firmware_transaction.py')
TX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TX)
BASE = ROOT/'out/ssc-assets/sensor-assets.tar.gz'
CANDIDATE = ROOT/'out/ssc-fedora-adsp-profile/sensor-assets.tar.gz'
BOOT = '1f8302ac-b357-4e48-8b26-d786bb0de2dc'


class AdspFirmwareTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = TX.archive_files(BASE, TX.BASE_SHA)
        cls.new = TX.archive_files(CANDIDATE, TX.CANDIDATE_SHA)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'root'
        (self.root/'etc').mkdir(parents=True)
        (self.root/'etc/machine-id').write_text(TX.MACHINE)
        self.proc = Path(self.temp.name)/'proc'
        (self.proc/'sys/kernel/random').mkdir(parents=True)
        (self.proc/'self').mkdir()
        (self.proc/'sys/kernel/osrelease').write_text(TX.RECOVERY)
        (self.proc/'sys/kernel/random/boot_id').write_text(BOOT)
        (self.proc/'self/stat').write_text(str(os.getpid())+' (python) R')
        for i, (name, row) in enumerate(self.original.items()):
            p = self.root/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(row['data'])
            p.chmod(row['mode'])
            # Original device metadata, including nanoseconds, need not equal
            # the baseline archive timestamp. Restore the captured originals.
            os.utime(p, ns=(row['mtime_ns']+i+1, row['mtime_ns']+i+1))
        # Host runs without root. Emulate only kernel/owner/chown permissions;
        # bytes, modes, mtimes, rename, fsync, archives and fault paths are real.
        real_lstat = Path.lstat
        def root_lstat(path):
            s = real_lstat(path)
            return SimpleNamespace(st_mode=s.st_mode, st_nlink=s.st_nlink,
                                   st_size=s.st_size, st_uid=0, st_gid=0,
                                   st_mtime_ns=s.st_mtime_ns)
        for mocker in (patch.object(TX.os, 'geteuid', return_value=0),
                       patch.object(TX.os, 'uname', return_value=SimpleNamespace(release=TX.RECOVERY)),
                       patch.object(TX.os, 'fchown'), patch.object(Path, 'lstat', root_lstat)):
            mocker.start()
            self.addCleanup(mocker.stop)
        self.before = self.snapshots()

    def snapshots(self):
        return {n: TX.snapshot(self.root/n) for n in self.original}

    def install(self):
        return TX.install(self.root, BASE, CANDIDATE, self.proc)

    def restore(self):
        return TX.restore(self.root, BASE, CANDIDATE, self.proc)

    def test_complete_real_pair_and_exact_metadata_restore(self):
        result = self.install()
        self.assertEqual((result['firmware_files'], result['changed_bytes_files']), (52, 19))
        for name, row in self.new.items():
            self.assertEqual((self.root/name).read_bytes(), row['data'])
            self.assertEqual(TX.snapshot(self.root/name), {k: v for k, v in row.items() if k != 'data'})
        self.assertEqual(self.restore()['verdict'], 'EXACT_ORIGINAL_PAIR_RESTORED')
        self.assertEqual(self.snapshots(), self.before)
        self.assertEqual(json.loads((self.root/TX.STATE/'ledger.json').read_text())['phase'], 'restored')
        self.assertFalse(result['remoteproc_started'])

    def test_mainline_kernel_rejected_before_any_write(self):
        with patch.object(TX.os, 'uname', return_value=SimpleNamespace(release='7.2.0-rc3-gts9wifi-dirty')):
            with self.assertRaisesRegex(ValueError, 'actual qualified'):
                self.install()
        self.assertFalse((self.root/TX.STATE).exists())
        self.assertEqual(self.snapshots(), self.before)

    def test_nonroot_rejected(self):
        with patch.object(TX.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(ValueError, 'actual qualified'):
                self.install()

    def test_wrong_machine_rejected(self):
        (self.root/'etc/machine-id').write_text('wrong')
        with self.assertRaisesRegex(ValueError, 'wrong offline'):
            self.install()

    def test_missing_or_fabricated_proc_rejected(self):
        (self.proc/'self/stat').write_text('1 (not-this-process) R')
        with self.assertRaisesRegex(ValueError, 'proc bind'):
            self.install()
        (self.proc/'self/stat').unlink()
        with self.assertRaises(FileNotFoundError):
            self.install()

    def test_archive_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'archive identity'):
            TX.install(self.root, CANDIDATE, CANDIDATE, self.proc)
        self.assertFalse((self.root/TX.STATE).exists())

    def test_unknown_original_stops_before_backup(self):
        name = next(iter(self.original))
        (self.root/name).write_bytes(b'unknown original')
        with self.assertRaisesRegex(ValueError, 'installed original differs'):
            self.install()
        self.assertFalse((self.root/TX.STATE).exists())

    def test_symlink_firmware_rejected(self):
        p = self.root/next(iter(self.original))
        data = p.read_bytes()
        p.unlink()
        outside = Path(self.temp.name)/'outside'
        outside.write_bytes(data)
        p.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.install()

    def test_parent_symlink_rejected(self):
        p = self.root/'var'
        p.symlink_to(Path(self.temp.name))
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.install()

    def test_hardlinked_firmware_rejected(self):
        p = self.root/next(iter(self.original))
        os.link(p, Path(self.temp.name)/'link')
        with self.assertRaisesRegex(ValueError, 'hardlinked'):
            self.install()

    def test_partial_backup_failure_never_changes_firmware(self):
        real = TX.atomic
        count = 0
        def fail(path, *args, **kwargs):
            nonlocal count
            if path.name != 'ledger.json':
                count += 1
                if count == 4:
                    raise OSError('injected backup disk error')
            return real(path, *args, **kwargs)
        with patch.object(TX, 'atomic', fail):
            with self.assertRaisesRegex(OSError, 'backup disk'):
                self.install()
        self.assertEqual(self.snapshots(), self.before)
        self.assertEqual(self.restore()['verdict'], 'EXACT_ORIGINAL_PAIR_UNCHANGED')
        self.assertEqual(self.restore()['verdict'], 'EXACT_ORIGINAL_PAIR_UNCHANGED')

    def test_complete_backups_and_intent_precede_first_write(self):
        real = TX.atomic
        checked = []
        def observe(path, *args, **kwargs):
            if str(path.relative_to(self.root)).startswith(TX.FW):
                state = json.loads((self.root/TX.STATE/'ledger.json').read_text())
                self.assertEqual(state['phase'], 'installing')
                self.assertEqual(state['pending'], str(path.relative_to(self.root)))
                for n, row in self.original.items():
                    self.assertEqual((self.root/TX.STATE/Path(n).name).read_bytes(), row['data'])
                checked.append(path)
            return real(path, *args, **kwargs)
        with patch.object(TX, 'atomic', observe):
            self.install()
        self.assertEqual(len(checked), 52)

    def test_partial_replace_failure_restores_before_and_after_files(self):
        real = TX.atomic
        writes = 0
        def fail(path, *args, **kwargs):
            nonlocal writes
            if str(path.relative_to(self.root)).startswith(TX.FW):
                writes += 1
                if writes == 20:
                    raise OSError('injected replacement failure')
            return real(path, *args, **kwargs)
        with patch.object(TX, 'atomic', fail):
            with self.assertRaisesRegex(OSError, 'replacement'):
                self.install()
        self.assertNotEqual(self.snapshots(), self.before)
        self.restore()
        self.assertEqual(self.snapshots(), self.before)

    def test_crash_after_rename_before_completion_ledger_is_restorable(self):
        real = TX.atomic
        def fail(path, *args, **kwargs):
            result = real(path, *args, **kwargs)
            if str(path.relative_to(self.root)).startswith(TX.FW):
                raise OSError('injected post-rename failure')
            return result
        with patch.object(TX, 'atomic', fail):
            with self.assertRaisesRegex(OSError, 'post-rename'):
                self.install()
        self.restore()
        self.assertEqual(self.snapshots(), self.before)

    def test_corrupt_backup_stops_all_restore_writes(self):
        self.install()
        installed = self.snapshots()
        (self.root/TX.STATE/Path(sorted(self.original)[-1]).name).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'backup identity'):
            self.restore()
        self.assertEqual(self.snapshots(), installed)

    def test_unknown_current_file_stops_all_restore_writes(self):
        self.install()
        (self.root/sorted(self.original)[-1]).write_bytes(b'unknown change')
        installed = self.snapshots()
        with self.assertRaisesRegex(ValueError, 'unknown current'):
            self.restore()
        self.assertEqual(self.snapshots(), installed)

    def test_edited_ledger_path_rejected_before_restore(self):
        self.install()
        ledger = self.root/TX.STATE/'ledger.json'
        state = json.loads(ledger.read_text())
        state['files']['etc/passwd'] = state['files'].pop(next(iter(state['files'])))
        ledger.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'unqualified transaction'):
            self.restore()

    def test_edited_candidate_metadata_rejected_before_restore(self):
        self.install()
        ledger = self.root/TX.STATE/'ledger.json'
        state = json.loads(ledger.read_text())
        state['files'][next(iter(state['files']))]['after']['mtime_ns'] += 1
        ledger.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'unqualified firmware ledger'):
            self.restore()

    def test_interrupted_restore_is_resumable(self):
        self.install()
        real = TX.atomic
        writes = 0
        def fail(path, *args, **kwargs):
            nonlocal writes
            if str(path.relative_to(self.root)).startswith(TX.FW):
                writes += 1
                if writes == 4:
                    raise OSError('injected restore failure')
            return real(path, *args, **kwargs)
        with patch.object(TX, 'atomic', fail):
            with self.assertRaisesRegex(OSError, 'restore failure'):
                self.restore()
        self.restore()
        self.assertEqual(self.snapshots(), self.before)

    def test_installed_or_restored_transaction_cannot_be_replayed(self):
        self.install()
        with self.assertRaisesRegex(ValueError, 'prior transaction'):
            self.install()
        self.restore()
        with self.assertRaisesRegex(ValueError, 'prior transaction'):
            self.install()

    def test_calibration_and_other_firmware_untouched(self):
        untouched = (self.root/'usr/share/qcom/calibration', self.root/TX.FW/'cdsp.mdt')
        for path in untouched:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'unrelated original')
        self.install()
        self.restore()
        self.assertTrue(all(p.read_bytes() == b'unrelated original' for p in untouched))

    def test_cleanup_refuses_installed_pair(self):
        self.install()
        with self.assertRaisesRegex(ValueError, 'restored terminal'):
            TX.cleanup(self.root, BASE, CANDIDATE, self.proc)
        self.assertTrue((self.root/TX.STATE/'ledger.json').is_file())

    def test_cleanup_only_removes_verified_restored_backups(self):
        self.install()
        self.restore()
        TX.cleanup(self.root, BASE, CANDIDATE, self.proc)
        self.assertFalse((self.root/TX.STATE).exists())
        self.assertEqual(self.snapshots(), self.before)

    def test_cleanup_unknown_entry_stops_without_deleting_backups(self):
        self.install()
        self.restore()
        (self.root/TX.STATE/'unknown').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'unknown backup'):
            TX.cleanup(self.root, BASE, CANDIDATE, self.proc)
        self.assertTrue((self.root/TX.STATE/Path(next(iter(self.original))).name).exists())

    def test_cleanup_corrupt_backup_stops_without_deleting_other_backups(self):
        self.install()
        self.restore()
        (self.root/TX.STATE/Path(sorted(self.original)[-1]).name).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'changed backup'):
            TX.cleanup(self.root, BASE, CANDIDATE, self.proc)
        self.assertTrue((self.root/TX.STATE/Path(sorted(self.original)[0]).name).exists())

    def test_unchanged_asset_guard_and_separate_restore_order(self):
        spec = importlib.util.spec_from_file_location('qualified399_assets',
            ROOT/'reference/boot-tests/test-399-ssc-smp2p-provider/assets.py')
        assets = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(assets)
        manifest = json.loads((ROOT/'out/ssc-fedora-adsp-profile/PROFILE.json').read_text())['files']
        with self.assertRaisesRegex(ValueError, 'refusing existing different asset'):
            assets.install(self.root, CANDIDATE, TX.CANDIDATE_SHA, manifest)
        self.assertFalse((self.root/assets.STATE).exists())
        self.install()
        assets.install(self.root, CANDIDATE, TX.CANDIDATE_SHA, manifest)
        assets.restore(self.root)
        for name, row in self.new.items():
            self.assertEqual((self.root/name).read_bytes(), row['data'])
        self.restore()
        self.assertEqual(self.snapshots(), self.before)
        self.assertFalse((self.root/assets.PREFIX).exists())


class AbsentOriginalTransactionTests(unittest.TestCase):
    # Reuse fixture construction/permission seams without rerunning old cases.
    setUpClass = classmethod(AdspFirmwareTransactionTests.setUpClass.__func__)
    setUp = AdspFirmwareTransactionTests.setUp
    snapshots = AdspFirmwareTransactionTests.snapshots
    install = AdspFirmwareTransactionTests.install
    restore = AdspFirmwareTransactionTests.restore
    def absent(self):
        for name in self.original:
            (self.root/name).unlink()
        (self.root/TX.FW.rstrip('/')).rmdir()

    def install_absent(self):
        return TX.install(self.root, BASE, CANDIDATE, self.proc, 'absent')

    def restore_absent(self):
        return TX.restore(self.root, BASE, CANDIDATE, self.proc, 'absent')

    def test_absent_pair_created_then_removed_with_terminal_ledger(self):
        self.absent()
        d=self.install_absent()
        self.assertEqual(d['original_presence'],'absent')
        self.assertEqual(len(list((self.root/TX.STATE).iterdir())),1)
        for n,row in self.new.items():self.assertEqual((self.root/n).read_bytes(),row['data'])
        self.restore_absent()
        self.assertFalse((self.root/TX.FW.rstrip('/')).exists())
        TX.cleanup(self.root,BASE,CANDIDATE,self.proc,'absent')
        self.assertFalse((self.root/TX.STATE).exists())

    def test_absent_permission_cannot_overwrite_a_present_original(self):
        with self.assertRaisesRegex(ValueError,'absent original unexpectedly'):
            self.install_absent()
        self.assertEqual(self.snapshots(),self.before)

    def test_present_policy_cannot_assume_missing_original_is_backed_up(self):
        self.absent()
        with self.assertRaisesRegex(ValueError,'installed original differs'):self.install()
        self.assertFalse((self.root/TX.STATE).exists())

    def test_partial_absent_install_restores_only_recognized_created_files(self):
        self.absent(); real=TX.atomic;count=0
        def fail(p,*args,**kwargs):
            nonlocal count
            if str(p.relative_to(self.root)).startswith(TX.FW):
                count+=1
                if count==8:raise OSError('injected absent install failure')
            return real(p,*args,**kwargs)
        with patch.object(TX,'atomic',fail),self.assertRaises(OSError):self.install_absent()
        self.restore_absent()
        self.assertFalse((self.root/TX.FW.rstrip('/')).exists())

    def test_unknown_absent_candidate_file_stops_before_any_deletion(self):
        self.absent();self.install_absent()
        (self.root/sorted(self.new)[-1]).write_bytes(b'unknown')
        before={n:(self.root/n).read_bytes() for n in self.new}
        with self.assertRaisesRegex(ValueError,'unknown current'):self.restore_absent()
        self.assertEqual({n:(self.root/n).read_bytes() for n in self.new},before)

    def test_edited_presence_cannot_turn_present_restore_into_deletion(self):
        self.install()
        with self.assertRaisesRegex(ValueError,'unqualified transaction'):
            self.restore_absent()
        self.assertEqual(len(list((self.root/TX.FW.rstrip('/')).iterdir())),52)

    def test_unrelated_directory_file_is_not_recursively_removed(self):
        self.absent();self.install_absent()
        unknown=self.root/TX.FW/'unrelated';unknown.write_bytes(b'keep')
        with self.assertRaises(OSError):self.restore_absent()
        self.assertEqual(unknown.read_bytes(),b'keep')


if __name__ == '__main__':
    unittest.main()
