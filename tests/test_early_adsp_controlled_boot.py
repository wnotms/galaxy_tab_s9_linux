"""Host-only fault/boundary tests for Test364; never contact a device."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT/'reference/boot-tests/test-364-early-adsp-socinfo'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


A = load('early364_assets_tests', R/'assets.py')
H = load('early364_flow_tests', R/'host_flow.py')


class AssetTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'root'; (self.root/'etc').mkdir(parents=True)
        (self.root/'etc/machine-id').write_text(A.MACHINE)
        self.archive = Path(self.tmp.name)/'assets.tar'
        self.names = [A.FW+'adsp.mdt', A.PREFIX+'/sensors/config/test.json']
        self.manifest = {}
        with tarfile.open(self.archive, 'w') as tar:
            for n in self.names:
                data = n.encode(); info = tarfile.TarInfo(n); info.size=len(data); info.mtime=1640995200
                tar.addfile(info, io.BytesIO(data))
                self.manifest[n] = dict(bytes=len(data),sha256=A.digest(data),mtime=info.mtime)
        self.sha = A.digest(self.archive.read_bytes())

    def install(self): return A.install(self.root,self.archive,self.sha,self.manifest)

    def test_install_exact_owned_then_restore(self):
        d=self.install(); self.assertEqual(d['owned_files'],2)
        self.assertFalse(d['services_started']); self.assertFalse(d['remoteproc_started'])
        for n in self.names: self.assertEqual(int((self.root/n).stat().st_mtime),1640995200)
        A.restore(self.root)
        for n in self.names: self.assertFalse((self.root/n).exists())

    def test_preserves_preexisting_identical_firmware(self):
        p=self.root/self.names[0]; A.atomic(p,self.names[0].encode(),mtime=1640995200)
        self.assertEqual(self.install()['owned_files'],1)
        A.restore(self.root); self.assertTrue(p.exists())

    def test_existing_different_firmware_rejected_before_ledger(self):
        A.atomic(self.root/self.names[0],b'other',mtime=1640995200)
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.root/A.STATE).exists())

    def test_matching_bytes_wrong_mtime_rejected_before_ledger(self):
        A.atomic(self.root/self.names[0],self.names[0].encode(),mtime=1)
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.root/A.STATE).exists())

    def test_wrong_machine(self):
        (self.root/'etc/machine-id').write_text('wrong')
        with self.assertRaises(ValueError): self.install()

    def test_wrong_archive(self):
        self.sha='0'*64
        with self.assertRaises(ValueError): self.install()

    def test_prior_registry_not_overwritten(self):
        (self.root/A.PREFIX).mkdir(parents=True)
        with self.assertRaises(ValueError): self.install()

    def test_duplicate_install_refused(self):
        self.install()
        with self.assertRaises(ValueError): self.install()

    def test_partial_install_restorable(self):
        original=A.atomic
        def failing(path,*args,**kw):
            if str(path).endswith('test.json'): raise OSError('mock disk fault')
            return original(path,*args,**kw)
        with patch.object(A,'atomic',side_effect=failing):
            with self.assertRaises(OSError): self.install()
        self.assertEqual(json.loads((self.root/A.STATE).read_text())['phase'],'copy-started')
        A.restore(self.root)
        self.assertFalse((self.root/self.names[0]).exists())

    def test_modified_owned_firmware_not_deleted(self):
        self.install(); (self.root/self.names[0]).write_bytes(b'new')
        with self.assertRaises(ValueError): A.restore(self.root)
        self.assertTrue((self.root/A.PREFIX).exists())

    def test_copied_registry_changes_removed_original_persist_untouched(self):
        p=self.root/'mnt/vendor/persist/sensors'; p.mkdir(parents=True); (p/'owner').write_text('keep')
        self.install(); (self.root/self.names[1]).write_bytes(b'copied update')
        A.restore(self.root); self.assertEqual((p/'owner').read_text(),'keep')

    def test_malicious_ledger_directory_fails_before_removal(self):
        self.install(); p=self.root/A.STATE; d=json.loads(p.read_text()); d['created_dirs'].append('etc');p.write_text(json.dumps(d))
        with self.assertRaises(ValueError): A.restore(self.root)
        self.assertTrue((self.root/self.names[0]).exists())

    def test_path_traversal_and_symlink_escape(self):
        for n in ('../escape','/etc/passwd','usr/../etc/passwd','usr//bad'):
            with self.assertRaises(ValueError): A.target(self.root,n)
        (self.root/'usr').symlink_to(Path(self.tmp.name))
        with self.assertRaises(ValueError): self.install()

    def test_symlink_tar_entry_refused(self):
        with tarfile.open(self.archive,'w') as tar:
            info=tarfile.TarInfo(self.names[0]);info.type=tarfile.SYMTYPE; info.linkname='/etc/passwd';tar.addfile(info)
        self.sha=A.digest(self.archive.read_bytes())
        with self.assertRaises(ValueError): self.install()

    def test_missing_manifest_member(self):
        self.manifest['usr/lib/firmware/qcom/sm8550/absent']=dict(bytes=0,mtime=1,sha256=A.digest(b''))
        with self.assertRaises(ValueError): self.install()


class ControlledBootGateTests(unittest.TestCase):
    def packet(self):
        return dict(boot_id='11111111-1111-1111-1111-111111111111', machine_id=H.PLAN['machine_id'],uname=H.PLAN['release'],
            config_sha256=H.PLAN['candidate_config_sha256'],notes_sha256=H.PLAN['candidate_notes_sha256'],cmdline=H.PLAN['runtime_cmdline'],
            dcc_absent=True,direct_default='N',battery=dict(POWER_SUPPLY_HEALTH='Good',POWER_SUPPLY_PRESENT='1',POWER_SUPPLY_VOLTAGE_MAX_DESIGN='4440000',
            POWER_SUPPLY_CAPACITY='60',POWER_SUPPLY_TEMP='300',POWER_SUPPLY_VOLTAGE_NOW='4100000'),
            services=dict(ssh='active',**{'gts9-adbd':'active','gts9-usb-acm':'active','gdm':'inactive','gts9-pen':'inactive','gts9-palm':'inactive'}),
            roles=dict(power_role='[sink] source',data_role='[device] host'),network='1: usb0 inet 169.254.42.1/16',host_key=H.PLAN['host_ed25519_key'],
            adsp=[dict(state='running',firmware='qcom/sm8550/adsp.mdt')],
            native_socinfo=dict(boot_id='11111111-1111-1111-1111-111111111111',family='Snapdragon',machine='SM8550',soc_id='519',info_fmt='0x00000010',hardware_platform='8',hardware_platform_subtype='0',platform_version='1'))

    def test_clean_native_identity(self):
        d=self.packet(); self.assertEqual(H.identity(d,'candidate'),'1'*32)
        self.assertEqual(H.native_gate(d)['soc_id'],'519\n')

    def test_dcc_restored(self):
        d=self.packet();d['dcc_absent']=False
        with self.assertRaises(ValueError):H.identity(d,'candidate')

    def test_charge_optin_rejected(self):
        d=self.packet();d['cmdline']+=' sm5440_fedora.direct_charge_once=1'
        with self.assertRaises(ValueError):H.identity(d,'candidate')

    def test_direct_active_rejected(self):
        d=self.packet();d['direct_default']='Y'
        with self.assertRaises(ValueError):H.identity(d,'candidate')

    def test_hot_battery_stops(self):
        d=self.packet();d['battery']['POWER_SUPPLY_TEMP']='420'
        with self.assertRaises(ValueError):H.identity(d,'candidate')

    def test_host_role_rejected(self):
        d=self.packet();d['roles']['data_role']='device [host]'
        with self.assertRaises(ValueError):H.identity(d,'candidate')

    def test_adsp_offline_rejected(self):
        d=self.packet();d['adsp'][0]['state']='offline'
        with self.assertRaises(ValueError):H.native_gate(d)

    def test_native_identity_must_be_real_complete(self):
        d=self.packet();del d['native_socinfo']['platform_version']
        with self.assertRaises(ValueError):H.native_gate(d)

    def test_stale_native_boot_rejected(self):
        d=self.packet();d['native_socinfo']['boot_id']='22222222-2222-2222-2222-222222222222'
        with self.assertRaises(ValueError):H.native_gate(d)

    def test_unexpected_boot_rejected(self):
        with self.assertRaises(ValueError):H.identity(self.packet(),'candidate','2'*32)

    def test_whitelist_partition_write(self):
        rec=Mock()
        for n in ('vbmeta','init_boot','dtbo','misc'):
            with self.assertRaises(ValueError):H.write_partition(rec,n,'boot.img','a'*64,'b'*64)
        rec.adb.assert_not_called()

    def test_wrong_partition_image_pair_rejected(self):
        with self.assertRaises(ValueError):H.write_partition(Mock(),'boot','vendor_boot.img','a'*64,H.PACKAGE['artifacts']['vendor_boot.img']['sha256'])

    def test_unknown_restore_partition_never_overwritten(self):
        raw=''.join(v+'  /dev/block/by-name/'+n+'\n' for n,v in H.PACKAGE['baseline_partitions'].items())
        self.assertEqual(H.restore_layout(raw),H.PACKAGE['baseline_partitions'])
        with self.assertRaises(ValueError):H.restore_layout(raw.replace(H.PACKAGE['baseline_partitions']['dtbo'],'f'*64))

    def test_first_failure_blocks_install_before_device_call(self):
        with patch.object(H,'verify_inputs'),patch.object(H,'verify_stage'),patch.object(Path,'exists',return_value=True),patch.object(H.p,'Recorder') as rec:
            with self.assertRaises(ValueError):H.install()
            rec.assert_not_called()

    def test_unchanged_or_extra_boot_never_attributed(self):
        e=H.h.g.evidence
        before='1'*32;after='2'*32;other='3'*32
        fmt=lambda ids:'\n'.join(str(i)+' '+b+' Thu 2026-10-08 00:00:00 UTC—Thu 2026-10-08 00:01:00 UTC' for i,b in enumerate(ids))
        self.assertNotEqual(e.attribute(before,before,fmt([before]),fmt([before])),'attributed')
        self.assertNotEqual(e.attribute(before,after,fmt([before]),fmt([before,other,after])),'attributed')


if __name__=='__main__':unittest.main()
