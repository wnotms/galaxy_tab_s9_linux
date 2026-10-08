"""Execute the namespace-explicit module recovery against temporary manifests."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'userspace/sensors/recovery-modules.py'
spec=importlib.util.spec_from_file_location('ssc_recovery_modules',SOURCE);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
MACHINE='3c2a1b8f2d624db4b5ffdc836050fcf6'

class RecoveryModules(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'etc').mkdir();(self.root/'etc/machine-id').write_text(MACHINE)
        self.base=self.root/'usr/lib/modules';self.base.mkdir(parents=True);self.current=self.base/'7.2.0-test'
        self.saved=self.base/'.gts9-test366-original';self.tested=self.base/'.gts9-test366-tested'
        self.baseline=self.root/'baseline.sha256';self.candidate=self.root/'candidate.sha256'
        self.tree(self.saved,self.baseline,'baseline');self.tree(self.current,self.candidate,'candidate')
    def tree(self,path,manifest,text):
        path.mkdir();rows=[]
        for i in range(181):
            name=str(i);data=(text+name).encode();(path/name).write_bytes(data);rows.append(hashlib.sha256(data).hexdigest()+'  '+name+'\n')
        manifest.write_text(''.join(rows))
    def run_restore(self,namespace='gts9-test366'):
        script=helper.command(str(self.root),'7.2.0-test',namespace,str(self.baseline),str(self.candidate),MACHINE)
        return subprocess.run(['sh','-c',script],capture_output=True,text=True)
    def test_correct_slot_and_idempotent_after_partition_failure(self):
        self.assertEqual(self.run_restore().returncode,0);self.assertFalse(self.saved.exists());self.assertTrue(self.tested.exists());self.assertEqual((self.current/'0').read_text(),'baseline0')
        self.assertEqual(self.run_restore().returncode,0)
    def test_wrong_historical_slot_refuses_candidate_and_preserves_backup(self):
        self.assertNotEqual(self.run_restore('gts9-test364').returncode,0);self.assertTrue(self.saved.exists());self.assertFalse(self.tested.exists());self.assertEqual((self.current/'0').read_text(),'candidate0')
    def test_corrupt_baseline_refuses_before_rename(self):
        (self.saved/'0').write_text('bad');self.assertNotEqual(self.run_restore().returncode,0);self.assertTrue(self.saved.exists());self.assertFalse(self.tested.exists())
    def test_unknown_current_modules_refused(self):
        (self.current/'0').write_text('unknown');self.assertNotEqual(self.run_restore().returncode,0);self.assertTrue(self.saved.exists());self.assertFalse(self.tested.exists())
    def test_existing_tested_slot_not_overwritten(self):
        self.tested.mkdir();self.assertNotEqual(self.run_restore().returncode,0);self.assertTrue(self.saved.exists());self.assertEqual((self.current/'0').read_text(),'candidate0')
    def test_wrong_machine_refused(self):
        (self.root/'etc/machine-id').write_text('unknown');self.assertNotEqual(self.run_restore().returncode,0);self.assertTrue(self.saved.exists())
    def test_symlink_backup_refused(self):
        other=self.base/'original';self.saved.rename(other);self.saved.symlink_to(other);self.assertNotEqual(self.run_restore().returncode,0);self.assertFalse(self.tested.exists())
    def test_extra_file_refused(self):
        (self.saved/'extra').write_text('bad');self.assertNotEqual(self.run_restore().returncode,0);self.assertFalse(self.tested.exists())
    def test_unexpected_extra_symlink_refused(self):
        (self.saved/'extra.ko').symlink_to('/tmp/unknown');self.assertNotEqual(self.run_restore().returncode,0);self.assertFalse(self.tested.exists())
    def test_untrusted_namespace_release_or_paths_refused(self):
        for ns,release,path in [('gts9-test366; reboot','7.2.0-test',str(self.root)),('gts9-test366','../../x',str(self.root)),('gts9-test366','7.2.0-test','/mnt/../debian')]:
            with self.assertRaises(ValueError):helper.command(path,release,ns,str(self.baseline),str(self.candidate),MACHINE)

if __name__=='__main__':unittest.main()
