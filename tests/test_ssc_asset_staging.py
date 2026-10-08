import importlib.util
import json
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('stage_assets',
    Path(__file__).resolve().parents[1]/'userspace/sensors/stage-assets.py')
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def sources():
    config='vendor/etc/sensors/config/accel.json'
    sf={'apnhlos/image/adsp.mdt':b'firmware',
        'apnhlos/image/adsp_dtb.mdt':b'dtb',
        'dsp/adsp/libsns_dynamic_loader_skel.so':b'dynamic-loader',
        'dsp/adsp/libsns_remote_proc_state_skel.so':b'remote-state',
        'dsp/cdsp/unused.so':b'do-not-install',
        'persist/sensors/registry/registry/sensors_registry':b'',
        'persist/sensors/registry/registry/sns_reg_config':json.dumps({'sns_reg_config':{
            'owner':'NA','/'+config:{'type':'int','data':'1640995200'}}}).encode()}
    vf={config:b'configuration','vendor/etc/sensors/sns_reg_config':b'version=6',
        'vendor/etc/sensors/hals.conf':b'android-only'}
    sm=dict(purpose='READ_ONLY_STOCK_SENSOR_ASSETS',firmware_installed=False,remoteproc_started=False,
            temporary_mounts_removed=True,cleanup_errors=[],skipped_links=[],boot_id='same-boot',
            files={n:{'archive_mtime':123} for n in sf})
    vm=dict(purpose='READ_ONLY_VENDOR_SENSOR_CONFIG',device_deployment=False,
            temporary_mount_and_loop_removed=True,boot_id='same-boot',
            files={n:{'archive_mtime':1640995200} for n in vf})
    return (sm,sf),(vm,vf)


class AssetStagingTests(unittest.TestCase):
    def test_exact_mapping_preserves_input_and_registry_mtimes(self):
        s,v=sources();r=M.plan(s,v)
        marker=M.PREFIX+'sensors/registry/sensors_registry'
        self.assertIn(marker,r)
        self.assertNotIn(M.PREFIX+'sensors/registry/registry/sensors_registry',r)
        self.assertEqual(r[marker]['mtime'],123)
        self.assertEqual(r[M.PREFIX+'sensors/config/accel.json']['mtime'],1640995200)
        self.assertEqual(r[M.PREFIX+'sensors/sns_reg.conf']['bytes'],b'version=6')

    def test_excludes_cdsp_and_android_hal(self):
        s,v=sources();r=M.plan(s,v)
        self.assertFalse(any('/cdsp/' in n or n.endswith('hals.conf') for n in r))

    def test_missing_config_refused(self):
        s,v=sources();del v[1]['vendor/etc/sensors/config/accel.json']
        with self.assertRaisesRegex(ValueError,'input set'):M.plan(s,v)

    def test_extra_config_refused(self):
        s,v=sources();v[1]['vendor/etc/sensors/config/unregistered.json']=b'new'
        with self.assertRaisesRegex(ValueError,'input set'):M.plan(s,v)

    def test_changed_timestamp_refused(self):
        s,v=sources();v[0]['files']['vendor/etc/sensors/config/accel.json']['archive_mtime']=0
        with self.assertRaisesRegex(ValueError,'timestamp'):M.plan(s,v)

    def test_boot_mismatch_refused(self):
        s,v=sources();v[0]['boot_id']='other-boot'
        with self.assertRaisesRegex(ValueError,'unqualified'):M.plan(s,v)

    def test_incomplete_cleanup_refused(self):
        s,v=sources();v[0]['temporary_mount_and_loop_removed']=False
        with self.assertRaisesRegex(ValueError,'unqualified'):M.plan(s,v)

    def test_missing_marker_refused(self):
        s,v=sources();del s[1]['persist/sensors/registry/registry/sensors_registry']
        with self.assertRaisesRegex(ValueError,'marker'):M.plan(s,v)

    def test_missing_sensor_library_refused(self):
        s,v=sources();del s[1]['dsp/adsp/libsns_dynamic_loader_skel.so']
        with self.assertRaisesRegex(ValueError,'sensor PD library'):M.plan(s,v)

    def test_missing_firmware_refused(self):
        s,v=sources();del s[1]['apnhlos/image/adsp_dtb.mdt']
        with self.assertRaisesRegex(ValueError,'ADSP MDT'):M.plan(s,v)


if __name__ == '__main__':
    unittest.main()
