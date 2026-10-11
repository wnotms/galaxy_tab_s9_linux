import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_registry_mutation_evidence as fixture

ROOT = Path(__file__).resolve().parents[1]
R = ROOT/'reference/boot-tests/test-401-fedora-mtime-cache'
OLD = ROOT/'reference/boot-tests/test-400-fedora-adsp-comparison'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


H = load('cache401_host', R/'host_flow.py')
E = H.callback_evidence
D = load('cache401_desktop', R/'desktop.py')
A = load('cache401_assets', R/'assets.py')


class ScopeTests(unittest.TestCase):
    def test_exact_kernel_firmware_provider_module_pair_reused(self):
        old = json.loads((OLD/'PACKAGE.json').read_text())
        for key in ('candidate_partitions','baseline_partitions','candidate_build_link','modules'):
            self.assertEqual(old[key], H.PACKAGE[key])
        for name in ('vendor_boot.img','rollback-vendor_boot.img','hexagonrpcd-trace','original-assets.tar.gz'):
            self.assertEqual(old['artifacts'][name],H.PACKAGE['artifacts'][name])
        for k in ('kernel_rebuilt','config_changed','dtb_changed','modules_changed','firmware_changed_over400'):
            self.assertFalse(H.PACKAGE[k])
        self.assertEqual(H.PLAN['test'],'Test401')
        self.assertEqual(H.PLAN['ssc_readiness_seconds'],30)
        self.assertFalse(H.PLAN['PPS']);self.assertFalse(H.PLAN['pump_ON'])
        self.assertEqual(H.PLAN['baseline_config_sha256'],H.PLAN['candidate_config_sha256'])
        self.assertEqual(H.PACKAGE['artifacts']['firmware-assets.tar.gz'],old['artifacts']['sensor-assets.tar.gz'])
        self.assertEqual(H.PLAN['firmware_candidate_archive_sha256'],old['artifacts']['sensor-assets.tar.gz']['sha256'])

    def test_only_one_cache_member_changed_over400(self):
        old=json.loads((OLD/'asset-manifest.json').read_text());new=H.read(R/'asset-manifest.json')
        self.assertEqual(set(old),set(new));self.assertEqual(len(new),328)
        changed=[n for n in old if old[n]!=new[n]]
        self.assertEqual(changed,[fixture.E.PREFIX+'registry/sns_reg_config'])
        n=changed[0]
        self.assertEqual(old[n]['mode'],new[n]['mode']);self.assertEqual(old[n]['mtime'],new[n]['mtime'])

    def test_snapshot_reference_uses_unchanged_installer_applied_mode(self):
        archive=H.read(R/'asset-manifest.json');installed=H.read(R/'snapshot-manifest.json')
        self.assertEqual(installed,{n:dict(row,mode=0o644)for n,row in archive.items()})
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'file';A.atomic(p,b'actual-mode')
            self.assertEqual(p.stat().st_mode & 0o777,0o644)

    def test_actual_nine_file_overlay_restores_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'root';inc=Path(folder)/'incoming'
            (root/'etc').mkdir(parents=True);inc.mkdir()
            (root/'etc/machine-id').write_text(D.MACHINE)
            other=root/'etc/other';other.write_text('keep')
            manifest=H.read(R/'desktop-manifest.json')
            self.assertEqual(set(manifest),D.ALLOWED);self.assertEqual(len(manifest),9)
            for row in manifest.values():(inc/row['incoming']).write_bytes((ROOT/row['source']).read_bytes())
            D.install(root,inc,manifest);D.restore(root)
            self.assertTrue(all(not (root/n).exists()for n in manifest));self.assertEqual(other.read_text(),'keep')

    def test_snapshot_preserved_before_rejecting_wrong_profile(self):
        data={'registry/group':b'old'};before=fixture.snapshot(data)
        with tempfile.TemporaryDirectory() as folder:
            rec=Mock(folder=Path(folder));rec.adb.return_value=json.dumps(before),0
            with patch.object(H,'read',return_value=fixture.manifest({'registry/group':b'bad'})):
                with self.assertRaisesRegex(ValueError,'qualified profile'):
                    H.registry_snapshot(rec,fixture.BOOT,'before')
            self.assertEqual(H.read(rec.folder/'registry-before.json'),before)

    def test_foreign_failed_and_unquiescent_snapshots_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=Mock(folder=Path(folder))
            good=fixture.snapshot({'registry/group':b'old'},'after')
            for raw,status in [(json.dumps(good),1),('bad',0),
                (json.dumps(dict(good,producers_inactive=False)),0),
                (json.dumps(dict(good,boot_id='22222222-2222-4222-8222-222222222222')),0)]:
                rec.adb.return_value=raw,status
                with self.assertRaises(ValueError):H.registry_snapshot(rec,fixture.BOOT,'after')


class CallbackIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.before={'registry/group':b'old','sns_reg.conf':b'version=6\n'}
        self.after={'registry/group':b'new','sns_reg.conf':b'version=6\n'}
        self.calls=[fixture.opened(fixture.V+'group','w'),fixture.write(b'new'),fixture.close(),
                    fixture.opened(fixture.V+'group'),fixture.read(b'new'),fixture.close()]
        self.metadata=H.read(R/'registry-metadata.json')
        self.raw=json.dumps({'_BOOT_ID':fixture.BOOT.replace('-',''),
                             '_SYSTEMD_UNIT':fixture.E.UNIT,'MESSAGE':'test fixture'})
        p=patch.object(E.old.returned,'inspect',side_effect=lambda *a:dict(fixture.frames(self.calls),faults=[]))
        p.start();self.addCleanup(p.stop)
        # Statuses also need every source row attributed; real frame tests run separately.
        for c in self.calls:c['response_to']['buffers_hex']=list(c['response_to']['buffers_hex'])

    def inspect(self):
        return E.inspect(self.raw,fixture.BOOT,self.metadata,fixture.manifest(self.before),
            fixture.snapshot(self.before),fixture.snapshot(self.after,'after'))

    def test_generated_bytes_checked_without_old_immutable_cache_rule(self):
        r=self.inspect();self.assertTrue(r['complete'],r['faults'])
        self.assertEqual(r['contents']['changed_members'],['registry/group'])
        self.assertFalse(r['metadata_coverage_complete']);self.assertFalse(r['full_file_read_coverage_claimed'])
        self.assertFalse(r['SSC_publication_proved'])

    def test_failed_write_is_fatal_in_both_status_and_mutation(self):
        self.calls[1]['status']=1;r=self.inspect()
        self.assertFalse(r['complete']);self.assertIn('status',{f['source']for f in r['faults']})

    def test_unexplained_final_bytes_stop(self):
        self.after['registry/group']=b'wrong';self.assertFalse(self.inspect()['complete'])

    def test_unknown_config_stat_and_readdir_reply_stop(self):
        self.raw=json.dumps({'_BOOT_ID':fixture.BOOT.replace('-',''),'_SYSTEMD_UNIT':fixture.E.UNIT,
            'MESSAGE':'stat(/vendor/etc/sensors/config/unknown.json) -> size=1 mtime=1.000000000'})
        r=self.inspect();self.assertFalse(r['complete']);self.assertIn('metadata',{f['source']for f in r['faults']})
        self.raw=json.dumps({'_BOOT_ID':fixture.BOOT.replace('-',''),'_SYSTEMD_UNIT':fixture.E.UNIT,'MESSAGE':'fixture'})
        self.calls.append(fixture.call(28,[b''],[b'bad']))
        self.assertFalse(self.inspect()['complete'])

    def test_unknown_status_never_waived(self):
        self.calls.append(fixture.call(26,[b'bad'],status=69))
        self.assertFalse(self.inspect()['complete'])


if __name__=='__main__':unittest.main()
