import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-386-diag-minimal-overlay'
spec=importlib.util.spec_from_file_location('diag386_desktop',R/'desktop.py')
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)

class MinimalOverlayTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'root';self.incoming=Path(self.tmp.name)/'incoming'
        (self.root/'etc').mkdir(parents=True);self.incoming.mkdir()
        (self.root/'etc/machine-id').write_text(D.MACHINE+'\n')
        self.manifest=json.loads((R/'desktop-manifest.json').read_text())
        for row in self.manifest.values():
            (self.incoming/row['incoming']).write_bytes((ROOT/row['source']).read_bytes())
    def install(self):return D.install(self.root,self.incoming,self.manifest)
    def test_real_registered_five_file_install_and_complete_restore(self):
        self.assertEqual(set(self.manifest),D.ALLOWED)
        result=self.install();self.assertEqual(result['files'],5)
        for name,row in self.manifest.items():
            p=self.root/name;self.assertEqual(D.digest(p.read_bytes()),row['sha256'])
            self.assertEqual(p.stat().st_mode&0o777,row['mode'])
        result=D.restore(self.root);self.assertFalse(result['services_started'])
        for name in self.manifest:self.assertFalse((self.root/name).exists())
        self.assertFalse((self.root/D.STATE).exists())
        self.assertEqual((self.root/'etc/machine-id').read_text(),D.MACHINE+'\n')
    def test_old_eight_file_rpc_scope_is_rejected_before_mutation(self):
        self.manifest['usr/local/lib/gts9-test386/hexagonrpcd']=next(iter(self.manifest.values()))
        with self.assertRaisesRegex(ValueError,'file set'):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_missing_one_file_is_not_silently_accepted(self):
        self.manifest.pop(next(iter(self.manifest)))
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_wrong_machine_cannot_write(self):
        (self.root/'etc/machine-id').write_text('other')
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_corrupt_incoming_bytes_rejected_before_ledger(self):
        row=next(iter(self.manifest.values()));(self.incoming/row['incoming']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists())
    def test_unowned_existing_target_rejected_without_overwrite(self):
        name=next(iter(self.manifest));p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'foreign')
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(p.read_bytes(),b'foreign');self.assertFalse((self.root/D.STATE).exists())
    def test_no_second_install_into_owned_ledger(self):
        self.install()
        with self.assertRaises(ValueError):self.install()
    def test_restore_checks_all_files_before_removing_any(self):
        self.install();name=sorted(self.manifest)[-1];(self.root/name).write_bytes(b'foreign-new')
        with self.assertRaises(ValueError):D.restore(self.root)
        self.assertTrue(all((self.root/n).exists() for n in self.manifest))
        self.assertTrue((self.root/D.STATE).exists())
    def test_partial_install_can_restore_without_deleting_foreign_files(self):
        original=D.atomic;fail=sorted(self.manifest)[2]
        def atomic(path,data,mode=0o600):
            if path==self.root/fail:raise OSError('injected copy fault')
            return original(path,data,mode)
        with patch.object(D,'atomic',side_effect=atomic):
            with self.assertRaises(OSError):self.install()
        D.restore(self.root)
        self.assertFalse((self.root/D.STATE).exists());self.assertTrue(all(not (self.root/n).exists() for n in self.manifest))
    def test_qualified_original_file_bytes_mode_and_mtime_restored(self):
        name=sorted(self.manifest)[0];p=self.root/name;p.parent.mkdir(parents=True);p.write_bytes(b'original');p.chmod(0o600)
        before=p.stat();self.manifest[name]['original_sha256']=D.digest(b'original')
        self.install();D.restore(self.root)
        self.assertEqual(p.read_bytes(),b'original');self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(p.stat().st_mtime_ns,before.st_mtime_ns)
    def test_target_parent_symlink_escape_rejected(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir();(self.root/'usr').symlink_to(outside)
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/D.STATE).exists());self.assertEqual(list(outside.iterdir()),[])
    def test_restore_without_ledger_is_non_mutating(self):
        result=D.restore(self.root);self.assertEqual(result['verdict'],'NO_DESKTOP_LEDGER_NO_MUTATION')

if __name__=='__main__':unittest.main()
