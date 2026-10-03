"""Test306 lifecycle and identity failures with mocked transport, never a device."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from test_sm5440_condition_device_gate import fixture, raw, BOOT

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-306-adc-condition-comparison'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('condition306_runner_tests', R / 'host_flow.py')
b = load('condition306_package_tests', R / 'build_package.py')


def identity_fixture(phase='candidate'):
    s, _ = fixture()
    s.update(sample_mode_before='0x01', sample_mode_after='0x01',
             sample_ibus_ua='0', sample_faults='0x0')
    if phase == 'baseline':
        s.pop('condition_test')
        s.update(fault='1', startup_pending='2')
    sections = dict(boot=BOOT, uname='Linux gts9 7.2.0-rc3-gts9wifi-dirty',
                    cmdline=m.PLAN['runtime_cmdline'], uptime='30.1 100.3',
                    identity=m.PLAN[phase+'_config_sha256']+'  -\n'+m.PLAN[phase+'_notes_sha256']+'  /sys/kernel/notes',
                    battery='POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\n'
                            'POWER_SUPPLY_CAPACITY=20\nPOWER_SUPPLY_VOLTAGE_NOW=3800000\nPOWER_SUPPLY_TEMP=313\n'
                            'POWER_SUPPLY_VOLTAGE_MAX_DESIGN=4440000',
                    usb='POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=Unknown [SDP] DCP CDP PD\n'
                        'POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000',
                    dcc='absent', failed='', services='active\nactive\nactive',
                    roles='[sink]\n[device]', network='1: usb0    inet 169.254.42.1/16', snapshot=raw(s))
    return ''.join('@@'+k+'\n'+v+'\n' for k, v in sections.items())


class IdentityTests(unittest.TestCase):
    def setUp(self):
        m.configure()

    def test_different_baseline_candidate_configs_are_checked(self):
        self.assertNotEqual(m.PLAN['baseline_config_sha256'], m.PLAN['candidate_config_sha256'])
        for phase in ('baseline', 'candidate'):
            self.assertEqual(m.identity(identity_fixture(phase), phase)[1], BOOT)
            with self.assertRaises(ValueError):
                m.identity(identity_fixture(phase), 'candidate' if phase == 'baseline' else 'baseline')

    def test_changed_boot_and_config_refused(self):
        text = identity_fixture()
        with self.assertRaises(ValueError):
            m.identity(text, 'candidate', '2'*32)
        with self.assertRaises(ValueError):
            m.identity(text.replace(m.PLAN['candidate_config_sha256'], '0'*64), 'candidate')

    def test_actual_low_battery_refused_before_recovery(self):
        for old, new in [('POWER_SUPPLY_CAPACITY=20', 'POWER_SUPPLY_CAPACITY=0'),
                         ('POWER_SUPPLY_VOLTAGE_NOW=3800000', 'POWER_SUPPLY_VOLTAGE_NOW=3145000')]:
            with self.assertRaises(ValueError):
                m.identity(identity_fixture().replace(old, new), 'candidate')

    def test_usb_role_dcc_service_failed_unit_and_pump_refused(self):
        changes = [('[device]', '[host]'), ('@@dcc\nabsent', '@@dcc\npresent'),
                   ('usb0    inet 169.254.42.1/', 'usb0    inet 10.0.0.1/'),
                   ('@@failed\n\n', '@@failed\nupower.service failed\n'),
                   ('active\nactive\nactive', 'active\ninactive\nactive'),
                   ('sample_mode_after=0x01', 'sample_mode_after=0x05'),
                   ('sample_ibus_ua=0', 'sample_ibus_ua=100000'),
                   ('sample_faults=0x0', 'sample_faults=0x2')]
        for old, new in changes:
            with self.subTest(change=new), self.assertRaises(ValueError):
                m.identity(identity_fixture().replace(old, new), 'candidate')

    def test_unrestored_condition_refused(self):
        for key in ('condition_condition_error', 'condition_restore_error', 'last_sample_error'):
            with self.assertRaises(ValueError):
                m.identity(identity_fixture().replace(key+'=0', key+'=-5'), 'candidate')

    def test_diagnostic_cannot_be_retained_as_baseline(self):
        with self.assertRaises(ValueError):
            m.identity(identity_fixture('baseline')+'condition_test=1\n', 'baseline')

    def test_pc_usb_policy_and_float_design_not_waived(self):
        for old, new in [('POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000', 'POWER_SUPPLY_INPUT_CURRENT_LIMIT=1800000'),
                         ('[SDP]', '[DCP]'), ('POWER_SUPPLY_ONLINE=1', 'POWER_SUPPLY_ONLINE=0'),
                         ('POWER_SUPPLY_VOLTAGE_MAX_DESIGN=4440000', 'POWER_SUPPLY_VOLTAGE_MAX_DESIGN=4500000')]:
            with self.assertRaises(ValueError):
                m.identity(identity_fixture().replace(old, new), 'candidate')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        m.configure()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.r = Path(temp.name)
        ctx = mock.patch.object(m, 'R', self.r)
        ctx.start(); self.addCleanup(ctx.stop)
        ctx = mock.patch.object(m, 'verify_inputs')
        self.verify = ctx.start(); self.addCleanup(ctx.stop)
        # No real transport is allowed by any of these tests.
        ctx = mock.patch.object(m.p, 'Recorder')
        self.rec = ctx.start(); self.addCleanup(ctx.stop)
        m.p.SERIAL = 'R52X10045LT'

    def arm(self):
        m.write(self.r / 'mutation-state.json', dict(rollback_required=True))

    def test_success_always_restores_no_candidate_retention(self):
        def install():
            self.arm()
            return {'condition': {'verdict': 'OFF_CONDITION_COMPARISON_CAPTURED'}}
        with mock.patch.object(m, 'install_once', side_effect=install) as one, \
                mock.patch.object(m, 'restore', return_value={'boot_id': '2'*32}) as restore:
            m.run()
        one.assert_called_once(); restore.assert_called_once_with(from_recovery=True)
        self.assertFalse(m.read(self.r / 'mutation-state.json')['rollback_required'])
        self.verify.assert_called_once_with(require_push=True)

    def test_first_failure_after_mutation_restores_and_preserves_failure(self):
        def fail():
            self.arm()
            raise ValueError('ADC timeout')
        with mock.patch.object(m, 'install_once', side_effect=fail) as one, \
                mock.patch.object(m, 'restore', return_value={'boot_id': '2'*32}) as restore:
            with self.assertRaisesRegex(RuntimeError, 'first non-clean'):
                m.run()
        one.assert_called_once(); restore.assert_called_once()
        self.assertEqual(m.read(self.r / 'first-failure.json')['error'], 'ADC timeout')

    def test_pre_mutation_failure_does_not_reboot_or_restore(self):
        with mock.patch.object(m, 'install_once', side_effect=ValueError('low battery')), \
                mock.patch.object(m, 'restore') as restore:
            with self.assertRaises(RuntimeError):
                m.run()
        restore.assert_not_called(); self.rec.assert_not_called()

    def test_failed_restore_does_not_retry_or_report_completion(self):
        def install():
            self.arm()
            return {}
        with mock.patch.object(m, 'install_once', side_effect=install), \
                mock.patch.object(m, 'restore', side_effect=TimeoutError('rescue lost')) as restore:
            with self.assertRaisesRegex(RuntimeError, 'manual TWRP'):
                m.run()
        restore.assert_called_once()
        self.assertTrue(m.read(self.r / 'mutation-state.json')['rollback_required'])
        self.assertTrue(m.read(self.r / 'recovery-required.json')['no_blind_retry'])

    def test_second_experiment_refused(self):
        self.arm()
        with mock.patch.object(m, 'install_once') as one, self.assertRaisesRegex(ValueError, 'one attempt'):
            m.run()
        one.assert_not_called()

    def test_expired_or_future_preflight_refused_before_transport(self):
        (self.r / 'preflight').mkdir()
        for stamp in (m.time.time()-1000, m.time.time()+1000):
            m.write(self.r / 'preflight/summary.json', {'verdict': 'READY_FOR_REGISTERED_ONE_BOOT', 'collected_at_epoch': stamp})
            with self.assertRaises(ValueError):
                m.install_once()
        self.rec.assert_not_called()

    def test_no_unregistered_restore(self):
        with self.assertRaisesRegex(ValueError, 'no registered mutation'):
            m.restore()
        self.rec.assert_not_called()

    def test_recovery_entry_failure_is_registered_for_cleanup(self):
        (self.r / 'preflight').mkdir()
        m.write(self.r / 'preflight/summary.json', {'verdict': 'READY_FOR_REGISTERED_ONE_BOOT',
                                                 'collected_at_epoch': m.time.time(), 'boot_id': BOOT})
        self.rec.return_value.adb.return_value = (identity_fixture('baseline'), 0)
        with mock.patch.object(m.h, 'enter_recovery', side_effect=TimeoutError('recovery unavailable')):
            with self.assertRaises(TimeoutError):
                m.install_once()
        state = m.read(self.r / 'mutation-state.json')
        self.assertTrue(state['rollback_required'])
        self.assertEqual(state['phase'], 'recovery-requested-no-kernel-write')


class PartitionAndStageTests(unittest.TestCase):
    def setUp(self):
        m.configure()

    def partition_text(self, values):
        return ''.join(v+'  /dev/block/by-name/'+k+'\n' for k, v in values.items())

    def test_only_recognized_baseline_and_candidate_boot_restorable(self):
        for key in ('baseline_partitions', 'candidate_partitions'):
            self.assertEqual(m.restoration_layout(self.partition_text(m.PACKAGE[key])), m.PACKAGE[key]['boot'])
        for key in ('boot', 'vendor_boot', 'dtbo'):
            values = dict(m.PACKAGE['candidate_partitions'], **{key: '0'*64})
            with self.assertRaises(ValueError):
                m.restoration_layout(self.partition_text(values))

    def test_missing_or_duplicate_partitions_refused(self):
        text = self.partition_text(m.PACKAGE['candidate_partitions'])
        for bad in (text.split('\n', 1)[1], text+text):
            with self.assertRaises(ValueError):
                m.restoration_layout(bad)

    def test_staging_must_be_exact_content_and_file_set(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'boot').write_bytes(b'sealed')
            seal = {'boot': {'bytes': 6, 'sha256': hashlib.sha256(b'sealed').hexdigest()}}
            with mock.patch.object(m, 'STAGED', seal):
                m.verify_stage(path)
                (path / 'extra').write_text('extra')
                with self.assertRaises(ValueError):
                    m.verify_stage(path)
                (path / 'extra').unlink()
                (path / 'boot').write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    m.verify_stage(path)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        m.configure()
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.text = identity_fixture()
        _, pair = fixture()
        records = [dict(_BOOT_ID=BOOT, MESSAGE='Linux version 7.2.0-rc3-gts9wifi-dirty',
                        PRIORITY='6', _SOURCE_BOOTTIME_TIMESTAMP='0'),
                   dict(json.loads(pair), PRIORITY='6', _SOURCE_BOOTTIME_TIMESTAMP='318000')]
        self.kernel = ''.join(json.dumps(r)+'\n' for r in records)
        self.windows = 'ProblemCode : 0\n'
        self.before = '2'*32
        self.boots_before = '0 '+self.before+' boot\n'
        self.boots_after = '-1 '+self.before+' boot\n0 '+BOOT+' boot\n'
        self.calls = []
        recorder = mock.Mock(folder=self.folder)
        recorder.adb.side_effect = self.adb
        recorder.ps.side_effect = lambda *args, **kwargs: (self.windows, 0)
        recorder.command.return_value = ('', 255)  # bounded host-only NCM timeout
        self.rec = recorder
        ctx = mock.patch.object(m.p, 'Recorder', return_value=recorder)
        ctx.start(); self.addCleanup(ctx.stop)
        ctx = mock.patch.object(m.time, 'sleep')
        self.sleep = ctx.start(); self.addCleanup(ctx.stop)

    def adb(self, name, script, **kwargs):
        self.calls.append(name)
        if name.startswith('readiness-') or name == 'current-state':
            return self.text, 0
        if name == 'kernel-json':
            return self.kernel, 0
        if name == 'boots-after':
            return self.boots_after, 0
        if name == 'thermal':
            sec = m.h.g.baseline.sections(self.text)
            return ('@@boot\n'+BOOT+'\n@@zones\n'
                    '/sys/class/thermal/thermal_zone45|sm5714-battery|enabled\n'
                    '@@pack-temperature\n31300\n@@battery\n'+sec['battery']), 0
        raise AssertionError('unexpected device command: '+name)

    def admit(self):
        return m.admission(self.folder, 'candidate', self.before, self.boots_before)

    def test_full_mocked_admission_preserves_one_pair_and_host_only_timeout(self):
        result, _ = self.admit()
        self.assertEqual(result['condition']['verdict'], 'OFF_CONDITION_COMPARISON_CAPTURED')
        self.assertEqual(result['host_NCM_probe_status'], 255)
        self.assertEqual(result['boot_attribution'], 'attributed')
        self.rec.command.assert_called_once(); self.sleep.assert_not_called()
        self.assertEqual(self.calls.count('kernel-json'), 1)
        self.assertFalse(result['charging_authorized'])

    def test_unchanged_or_extra_boot_refused(self):
        for before, boots_after in [(BOOT, self.boots_after),
                                    (self.before, '-2 '+self.before+' boot\n-1 '+'3'*32+' boot\n0 '+BOOT+' boot\n')]:
            self.boots_after = boots_after
            with self.assertRaises(ValueError):
                m.admission(self.folder, 'candidate', before, self.boots_before)

    def test_code43_stops_even_when_device_shell_works(self):
        self.windows = 'ProblemCode : 43\n'
        with self.assertRaisesRegex(ValueError, 'Code43'):
            self.admit()
        self.assertIn('kernel-json', self.calls)

    def test_empty_journal_and_cpu_fault_refused(self):
        original = self.kernel
        row = json.loads(original.splitlines()[-1])
        row.update(MESSAGE='watchdog: BUG: soft lockup - CPU#4 stuck', PRIORITY='3')
        for text in ('', original+json.dumps(row)+'\n'):
            self.kernel = text
            with self.assertRaises(ValueError):
                self.admit()

    def test_restore_error_stops_without_readiness_wait(self):
        self.text = self.text.replace('condition_restore_error=0', 'condition_restore_error=-5')
        with self.assertRaisesRegex(ValueError, 'first ADC/restore error'):
            self.admit()
        self.assertEqual(self.calls, ['readiness-00'])
        self.sleep.assert_not_called()

    def test_manual_recovery_cannot_fabricate_candidate_attribution(self):
        self.text = identity_fixture('baseline')
        result, _ = m.admission(self.folder, 'baseline', None, None)
        self.assertEqual(result['boot_attribution'], 'missing_failed_candidate_history')
        self.assertNotIn('condition', result)


class PackageTests(unittest.TestCase):
    def fixture(self, root):
        ref = root / 'reference/boot-tests/test-306'
        ref.mkdir(parents=True)
        mount = root / 'scripts/twrp-mount-debian.sh'
        mount.parent.mkdir(); mount.write_text('accepted mount')
        baseline = ref.parent / 'test-292-passive-observation'
        baseline.mkdir()
        (baseline / 'staged-files.json').write_text(json.dumps({'mount-debian.sh': {'sha256': b.sha(mount)}}))
        artifacts = {}
        for name in ('boot.img', 'rollback-boot.img', 'modules-x710.tar.gz'):
            target = root / name
            target.write_text(name)
            artifacts[name] = {'path': name}
        for name in ('candidate-modules.sha256', 'rollback-modules.sha256', 'module-swap.sh'):
            (ref / name).write_text(name)
        return ref, {'artifacts': artifacts}

    def test_partial_stage_completed_without_rewriting_existing_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); ref, package = self.fixture(root)
            dest = root / 'stage'; dest.mkdir()
            existing = dest / 'candidate-boot.img'; existing.write_bytes((root / 'boot.img').read_bytes())
            stamp = existing.stat().st_mtime_ns
            with mock.patch.object(b, 'ROOT', root), mock.patch.object(b, 'R', ref):
                result = b.stage(package, dest)
                b.stage(package, dest)
            self.assertEqual(existing.stat().st_mtime_ns, stamp)
            self.assertEqual(len(result), 7)

    def test_stage_drift_or_missing_source_refused_before_any_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); ref, package = self.fixture(root)
            dest = root / 'stage'; dest.mkdir()
            (dest / 'candidate-boot.img').write_text('unknown')
            with mock.patch.object(b, 'ROOT', root), mock.patch.object(b, 'R', ref):
                with self.assertRaises(ValueError):
                    b.stage(package, dest)
                self.assertEqual(len(list(dest.iterdir())), 1)
                (dest / 'candidate-boot.img').unlink()
                (root / 'modules-x710.tar.gz').unlink()
                with self.assertRaises(FileNotFoundError):
                    b.stage(package, dest)
                self.assertEqual(list(dest.iterdir()), [])

    def test_exact_module_count_and_safe_archive_members(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'modules.tar'
            def archive(count, extra=None):
                with tarfile.open(path, 'w') as tf:
                    for i in range(count):
                        info = tarfile.TarInfo(b.RELEASE+'/kernel/m'+str(i)+'.ko')
                        info.size = 1; tf.addfile(info, io.BytesIO(b'x'))
                    if extra:
                        tf.addfile(extra)
            archive(181)
            self.assertEqual(len(b.archive_manifest(path)), 181)
            archive(180)
            with self.assertRaises(ValueError): b.archive_manifest(path)
            for name in (b.RELEASE+'/../escape', '/absolute', b.RELEASE+'/link'):
                extra = tarfile.TarInfo(name)
                if name.endswith('/link'):
                    extra.type = tarfile.SYMTYPE; extra.linkname = '/unsafe'
                archive(181, extra)
                with self.assertRaises(ValueError): b.archive_manifest(path)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ref = self.root / 'registration'; self.ref.mkdir()
        (self.root / 'input').write_bytes(b'qualified')
        (self.ref / 'INPUTS.json').write_text(json.dumps({'input': hashlib.sha256(b'qualified').hexdigest()}))
        for name, value in [('ROOT', self.root), ('R', self.ref)]:
            ctx = mock.patch.object(m, name, value)
            ctx.start(); self.addCleanup(ctx.stop)
        ctx = mock.patch.object(m, 'verify_stage')
        ctx.start(); self.addCleanup(ctx.stop)

    def test_drifted_registered_input_refused(self):
        (self.root / 'input').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError, 'registered input drift'):
            m.verify_inputs()

    def test_unpushed_registration_refused(self):
        with mock.patch.object(m.subprocess, 'check_output', side_effect=['test', 'new', 'old']):
            with self.assertRaisesRegex(ValueError, 'pushed'):
                m.verify_inputs(require_push=True)

    def test_uncommitted_registration_refused(self):
        with mock.patch.object(m.subprocess, 'check_output', side_effect=['test', 'same', 'same', ' M input']):
            with self.assertRaisesRegex(ValueError, 'uncommitted'):
                m.verify_inputs(require_push=True)


if __name__ == '__main__':
    unittest.main()
