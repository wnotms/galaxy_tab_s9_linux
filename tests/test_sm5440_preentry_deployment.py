"""Only the new Test339 admission/scoping adapter; no device access."""
import copy, importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-339-preentry-detach-wait'
spec=importlib.util.spec_from_file_location('bounded_deploy',R/'host_flow.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
class DeploymentTests(unittest.TestCase):
    def packet(self,candidate=False):
        raw=(R.parent/'test-338-bounded-direct-1p8a/preflight/current-state.txt').read_text()
        if candidate:
            raw=raw.replace(f.PLAN['baseline_notes_sha256'],f.PLAN['candidate_notes_sha256'])
            raw=raw.replace('@@cmdline\n','@@cmdline\n'+f.PLAN['cmdline_flag']+' ')
            raw=raw.replace('@@once\nabsent','@@once\nY')
        return raw
    def test_baseline(self):
        self.assertEqual(f.identity(self.packet(),'baseline')[1],'6dc80750ebdf41e7a4a898befdec7c63')
    def test_candidate(self):
        self.assertEqual(f.identity(self.packet(True),'candidate')[2]['soc'],58)
    def test_candidate_requires_unique_flag(self):
        self.assertRaises(ValueError,f.identity,self.packet(True).replace(f.PLAN['cmdline_flag'],'',1),'candidate')
        self.assertRaises(ValueError,f.identity,self.packet(True).replace(f.PLAN['cmdline_flag'],f.PLAN['cmdline_flag']+' '+f.PLAN['cmdline_flag'],1),'candidate')
    def test_candidate_requires_once_y(self):
        self.assertRaises(ValueError,f.identity,self.packet(True).replace('@@once\nY','@@once\nN'),'candidate')
    def test_baseline_forbids_once(self):
        self.assertRaises(ValueError,f.identity,self.packet().replace('@@once\nabsent','@@once\nY'),'baseline')
    def test_no_entry_soc_relaxation(self):
        self.assertRaises(ValueError,f.identity,self.packet(True).replace('POWER_SUPPLY_CAPACITY=58','POWER_SUPPLY_CAPACITY=80'),'candidate')
    def test_unique_339_modules_install_restore(self):
        import hashlib, io, tarfile
        from unittest.mock import patch
        import test_sm5440_module_staging as old
        fixture=old.ModuleStagingTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        data={f'new-{n:03}.ko':('new '+str(n)).encode() for n in range(181)}
        archive=fixture.work/'new.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,value in data.items():
                item=tarfile.TarInfo(old.RELEASE+'/'+name);item.size=len(value);tar.addfile(item,io.BytesIO(value))
        expected={n:hashlib.sha256(v).hexdigest() for n,v in data.items()};manifest=fixture.manifest('new.sha256',expected)
        with patch.object(old,'HELPER',R/'module-swap.sh'):
            result=fixture.call('install',manifest,archive);self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((fixture.base/'.gts9-test339-original').is_dir());self.assertFalse((fixture.base/'.gts9-test338-original').exists())
            self.assertEqual(fixture.current_hashes(),expected)
            result=fixture.call('restore',fixture.old_manifest);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(fixture.current_hashes(),fixture.old)

    def test_scope_and_namespace(self):
        self.assertTrue(f.authorized())
        self.assertEqual(f.h.TMP,'/tmp/gts9-test339')
        self.assertIn('gts9-test339',f.h.STAGE)
        self.assertNotEqual(json.loads((R/'staged-files.json').read_text())['module-swap.sh']['sha256'],json.loads((R.parent/'test-337-async-fixed-charge-restore/staged-files.json').read_text())['module-swap.sh']['sha256'])
if __name__=='__main__':unittest.main()
