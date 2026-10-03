"""Test309 pure evidence and mocked lifecycle; import never contacts hardware."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_sm5440_condition_device_runner as inherited


ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reference/boot-tests/test-309-ordinary-program-acceptance'
BOOT = '1' * 32


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('ordinary309_tests', R / 'host_flow.py')
g = m.gate
c = load('ordinary309_controls', R / 'read-controls.py')
b = load('ordinary309_package', R / 'build_package.py')


def identity(phase='candidate'):
    snapshot = dict(pump_enable_supported='0', sample_valid='1',
                    sample_mode_before='0x01', sample_mode_after='0x01',
                    sample_ibus_ua='0', sample_faults='0x0', last_sample_error='0')
    sections = dict(boot=BOOT, uname='Linux gts9 7.2.0-rc3-gts9wifi-dirty',
        cmdline=m.PLAN['runtime_cmdline'], uptime='30.1 100.3',
        identity=m.PLAN[phase+'_config_sha256']+'  -\n'+m.PLAN[phase+'_notes_sha256']+'  /sys/kernel/notes',
        battery='POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\n'
            'POWER_SUPPLY_CAPACITY=20\nPOWER_SUPPLY_VOLTAGE_NOW=3800000\nPOWER_SUPPLY_TEMP=313\n'
            'POWER_SUPPLY_VOLTAGE_MAX_DESIGN=4440000',
        usb='POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_USB_TYPE=Unknown [SDP] DCP CDP PD\n'
            'POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000',
        dcc='absent', failed='', services='active\nactive\nactive',
        roles='[sink]\n[device]', network='1: usb0    inet 169.254.42.1/16',
        snapshot='\n'.join(k+'='+v for k,v in snapshot.items()))
    return ''.join('@@'+k+'\n'+v+'\n' for k,v in sections.items())


def registers():
    return dict(boot_id_before=BOOT, boot_id_after=BOOT, bound_driver='sm5714-battery',
                register_data_writes=False, only_atomic_pointer_reads=True,
                stable_registers={'0x0d': '0x01', '0x0e': '0x00', '0x13': '0x6c',
                                  '0x14': '0x05', '0x15': '0x90',
                                  '0x18': '0x20', '0x1a': '0xed'})


def journal(messages):
    return '\n'.join(json.dumps(dict(_BOOT_ID=BOOT, MESSAGE=message,
        _SOURCE_BOOTTIME_TIMESTAMP=str(stamp))) for stamp, message in messages)


class GateTests(unittest.TestCase):
    def setUp(self):
        m.configure()

    def test_baseline_candidate_identity_and_new_config_are_distinct(self):
        for phase in ('baseline', 'candidate'):
            m.identity(identity(phase), phase)
            with self.assertRaises(ValueError):
                m.identity(identity(phase), 'candidate' if phase == 'baseline' else 'baseline')

    def test_critical_battery_and_lpcharge_stop(self):
        for old, new in [('POWER_SUPPLY_CAPACITY=20', 'POWER_SUPPLY_CAPACITY=0'),
                         ('POWER_SUPPLY_VOLTAGE_NOW=3800000', 'POWER_SUPPLY_VOLTAGE_NOW=2775000'),
                         ('POWER_SUPPLY_TEMP=313', 'POWER_SUPPLY_TEMP=420'),
                         (m.PLAN['runtime_cmdline'], m.PLAN['runtime_cmdline'] + ' lpcharge=1')]:
            with self.subTest(change=new), self.assertRaises(ValueError):
                m.identity(identity().replace(old, new), 'candidate')

    def test_unrestored_diagnostic_or_pump_state_rejected(self):
        for old, new in [('pump_enable_supported=0', 'pump_enable_supported=1'),
                         ('sample_mode_after=0x01', 'sample_mode_after=0x05'),
                         ('sample_ibus_ua=0', 'sample_ibus_ua=100000'),
                         ('last_sample_error=0', 'last_sample_error=-5')]:
            with self.subTest(change=new), self.assertRaises(ValueError):
                m.identity(identity().replace(old, new), 'candidate')
        with self.assertRaises(ValueError):
            m.identity(identity() + 'condition_test=1\n', 'candidate')

    def test_pc_control_masks_and_aicl_reduction(self):
        data = registers()
        self.assertEqual(g.program_controls(json.dumps(data), BOOT)['input_limit_ma'], 500)
        data['stable_registers']['0x15'] = '0x88'
        self.assertEqual(g.program_controls(json.dumps(data), BOOT)['input_limit_ma'], 300)

    def test_identity_allows_aicl_reduction_but_refuses_above_pc_cap(self):
        m.identity(identity().replace('POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000',
                                     'POWER_SUPPLY_INPUT_CURRENT_LIMIT=300000'), 'candidate')
        for value in (0, 550000, 1800000, 310000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.identity(identity().replace('POWER_SUPPLY_INPUT_CURRENT_LIMIT=500000',
                        'POWER_SUPPLY_INPUT_CURRENT_LIMIT='+str(value)), 'candidate')

    def test_test307_actual_bad_controls_refused(self):
        for reg, value in [('0x13', '0x64'), ('0x15', '0x44'),
                           ('0x18', '0x97'), ('0x1a', '0x55'),
                           ('0x0d', '0x05'), ('0x0e', '0x80'), ('0x14', '0x07')]:
            data = registers(); data['stable_registers'][reg] = value
            with self.subTest(reg=reg), self.assertRaises(ValueError):
                g.program_controls(json.dumps(data), BOOT)

    def test_missing_provider_boot_or_control_evidence_refused(self):
        for key, value in [('boot_id_before', '2'*32), ('boot_id_after', '2'*32),
                           ('bound_driver', 'other'), ('register_data_writes', True),
                           ('only_atomic_pointer_reads', False)]:
            data = registers(); data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                g.program_controls(json.dumps(data), BOOT)
        data = registers(); del data['stable_registers']['0x18']
        with self.assertRaises(ValueError):
            g.program_controls(json.dumps(data), BOOT)

    def test_no_recovery_and_one_natural_recovery_classified(self):
        clean = journal([(0, 'Linux version 7.2')])
        self.assertFalse(g.program_history(clean, BOOT)['recovery_observed'])
        recovered = journal([(100, 'sm5714 2-0049: ordinary program mismatch: Q4=64'),
                             (200, 'sm5714 2-0049: ordinary program recovery: verified')])
        self.assertTrue(g.program_history(recovered, BOOT)['recovery_observed'])

    def test_second_missing_late_or_failed_recovery_stops(self):
        mismatch = 'sm5714 2-0049: ordinary program mismatch: Q4=64'
        recovered = 'sm5714 2-0049: ordinary program recovery: verified'
        for messages in ([(100, mismatch)], [(100, recovered)],
                         [(100, mismatch), (200, recovered), (300, mismatch)],
                         [(100, mismatch), (5_000_101, recovered)],
                         [(100, mismatch), (200, 'sm5714 2-0049: ordinary program recovery: charging intentionally off')],
                         [(100, 'sm5714 2-0049: ordinary program recovery inhibited: -5')],
                         [(100, 'sm5714 2-0049: cannot open Q4 charging path: -5')]):
            with self.subTest(messages=messages), self.assertRaises(ValueError):
                g.program_history(journal(messages), BOOT)

    def test_empty_or_mixed_program_journal_refused(self):
        for text in ('', journal([(0, 'Linux version')]).replace(BOOT, '2'*32)):
            with self.assertRaises(ValueError):
                g.program_history(text, BOOT)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        m.configure()
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        ctx = mock.patch.object(m, 'R', self.folder); ctx.start(); self.addCleanup(ctx.stop)
        ctx = mock.patch.object(m, 'verify_inputs'); ctx.start(); self.addCleanup(ctx.stop)
        ctx = mock.patch.object(m.p, 'Recorder'); self.rec = ctx.start(); self.addCleanup(ctx.stop)
        m.p.SERIAL = 'gts9wifi-0001'

    def arm(self):
        m.write(self.folder/'mutation-state.json', {'rollback_required': True})

    def test_success_retains_without_another_reboot_or_rollback(self):
        def install():
            self.arm(); return {'boot_id': BOOT}
        with mock.patch.object(m, 'install_once', side_effect=install), mock.patch.object(m, 'restore') as restore:
            result = m.run()
        restore.assert_not_called()
        self.assertIn('DEVICE_SCOPE_COMPLETED', result['verdict'])
        self.assertFalse(m.read(self.folder/'mutation-state.json')['rollback_required'])

    def test_post_acceptance_record_error_does_not_reflash_device(self):
        def install():
            self.arm(); return {'boot_id': BOOT}
        original = m.write
        def publication(path, value):
            if path.name == 'installed-status.json': raise OSError('host disk error')
            return original(path, value)
        with mock.patch.object(m, 'install_once', side_effect=install), \
                mock.patch.object(m, 'write', side_effect=publication), \
                mock.patch.object(m, 'restore') as restore:
            result = m.run()
        restore.assert_not_called()
        self.assertTrue(result['device_scope_completed'])
        self.assertFalse(m.read(self.folder/'mutation-state.json')['rollback_required'])

    def test_first_post_mutation_failure_restores_once(self):
        def fail():
            self.arm(); raise ValueError('program mismatch')
        with mock.patch.object(m, 'install_once', side_effect=fail), \
                mock.patch.object(m, 'restore', return_value={}) as restore:
            with self.assertRaisesRegex(RuntimeError, 'first non-clean'):
                m.run()
        restore.assert_called_once_with(from_recovery=False)
        self.assertEqual(m.read(self.folder/'first-failure.json')['error'], 'program mismatch')

    def test_pre_mutation_failure_never_reboots(self):
        with mock.patch.object(m, 'install_once', side_effect=ValueError('low battery')), \
                mock.patch.object(m, 'restore') as restore:
            with self.assertRaises(RuntimeError): m.run()
        restore.assert_not_called(); self.rec.assert_not_called()

    def test_failed_restore_stays_pending_without_retry(self):
        def fail():
            self.arm(); raise ValueError('program mismatch')
        with mock.patch.object(m, 'install_once', side_effect=fail), \
                mock.patch.object(m, 'restore', side_effect=ValueError('unsafe battery')) as restore:
            with self.assertRaisesRegex(RuntimeError, 'manual TWRP'): m.run()
        restore.assert_called_once()
        self.assertTrue(m.read(self.folder/'mutation-state.json')['rollback_required'])
        self.assertTrue(m.read(self.folder/'recovery-required.json')['no_blind_retry'])

    def test_second_attempt_refused_before_transport(self):
        self.arm()
        with mock.patch.object(m, 'install_once') as install, self.assertRaises(ValueError): m.run()
        install.assert_not_called(); self.rec.assert_not_called()

    def test_unsafe_live_entry_does_not_write_bcb(self):
        (self.folder/'preflight').mkdir()
        m.write(self.folder/'preflight/summary.json', {'verdict':'READY_FOR_REGISTERED_ONE_BOOT',
            'collected_at_epoch':m.time.time(), 'boot_id':BOOT})
        self.rec.return_value.adb.return_value = (identity('baseline').replace(
            'POWER_SUPPLY_CAPACITY=20', 'POWER_SUPPLY_CAPACITY=0'), 0)
        with mock.patch.object(m.h, 'enter_recovery') as enter, self.assertRaises(ValueError): m.install_once()
        enter.assert_not_called()
        self.assertFalse((self.folder/'mutation-state.json').exists())

    def test_unsafe_rollback_does_not_write_bcb(self):
        self.arm();self.rec.return_value.adb.return_value = ('POWER_SUPPLY_CAPACITY=0', 0)
        with mock.patch.object(m.h, 'enter_recovery') as enter, self.assertRaises((ValueError,KeyError)): m.restore()
        enter.assert_not_called()


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        m.configure()
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.text = identity()
        self.kernel = json.dumps(dict(_BOOT_ID=BOOT, MESSAGE='Linux version 7.2.0-rc3-gts9wifi-dirty',
            PRIORITY='6', _SOURCE_BOOTTIME_TIMESTAMP='0')) + '\n'
        self.windows = 'ProblemCode : 0\n'
        self.before = '2'*32
        self.boots_before = '0 '+self.before+' boot\n'
        self.boots_after = '-1 '+self.before+' boot\n0 '+BOOT+' boot\n'
        self.calls = []
        recorder = mock.Mock(folder=self.folder)
        recorder.adb.side_effect=self.adb
        recorder.ps.side_effect=lambda *a, **k:(self.windows,0)
        recorder.command.return_value=('',255)
        self.rec=recorder
        ctx=mock.patch.object(m.p,'Recorder',return_value=recorder);ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(m.time,'sleep');self.sleep=ctx.start();self.addCleanup(ctx.stop)

    def adb(self, name, script, **kwargs):
        self.calls.append(name)
        if name.startswith('readiness-') or name=='current-state':return self.text,0
        if name=='kernel-json':return self.kernel,0
        if name=='boots-after':return self.boots_after,0
        if name=='program-controls':return json.dumps(registers()),0
        if name=='thermal':
            sec=m.h.g.baseline.sections(self.text)
            return '@@boot\n'+BOOT+'\n@@zones\n/thermal37|sm5714-battery|enabled\n@@pack-temperature\n31300\n@@battery\n'+sec['battery'],0
        raise AssertionError('unexpected device command: '+name)

    def test_complete_mocked_admission_has_no_adc_invocation_or_extra_wait(self):
        result,_=m.admission(self.folder,'candidate',self.before,self.boots_before)
        self.assertEqual(result['program_controls']['input_limit_ma'],500)
        self.assertFalse(result['program_history']['recovery_observed'])
        self.assertEqual(result['host_NCM_probe_status'],255)
        self.sleep.assert_not_called();self.rec.command.assert_called_once()
        self.assertEqual(self.calls.count('kernel-json'),1)
        self.assertEqual(self.calls.count('program-controls'),1)

    def test_unchanged_or_unexpected_boot_stops(self):
        for before,history in [(BOOT,self.boots_after),(self.before,'-2 '+self.before+' boot\n-1 '+'3'*32+' boot\n0 '+BOOT+' boot\n')]:
            self.boots_after=history
            with self.assertRaises(ValueError):m.admission(self.folder,'candidate',before,self.boots_before)

    def test_code43_cpu_stall_and_register_failure_stop(self):
        original=self.kernel
        self.windows='ProblemCode : 43\n'
        with self.assertRaises(ValueError):m.admission(self.folder,'candidate',self.before,self.boots_before)
        self.windows='ProblemCode : 0\n'
        row=json.loads(original);row.update(MESSAGE='watchdog: BUG: soft lockup - CPU#4 stuck',PRIORITY='0',_SOURCE_BOOTTIME_TIMESTAMP='100')
        self.kernel=original+json.dumps(row)+'\n'
        with self.assertRaises(ValueError):m.admission(self.folder,'candidate',self.before,self.boots_before)
        self.kernel=original
        with mock.patch.object(m,'controls',side_effect=ValueError('Q4 lost')):
            with self.assertRaises(ValueError):m.admission(self.folder,'candidate',self.before,self.boots_before)



class ReadControlTests(unittest.TestCase):
    def setUp(self):
        self.ioctls = []
        self.boot = mock.Mock();self.boot.read_text.return_value=BOOT
        self.node = mock.Mock(name='node');self.node.name='2-0049'
        self.node.resolve.return_value = '/provider'
        self.node.__truediv__ = mock.Mock()
        driver = mock.Mock();driver.resolve.return_value.name='sm5714-battery'
        compatible = mock.Mock();compatible.read_bytes.return_value=b'siliconmitus,sm5714\0'
        self.node.__truediv__.side_effect=lambda key:{'driver':driver,'of_node/compatible':compatible}[key]
        directory = mock.Mock();directory.glob.return_value=[self.node]
        provider = mock.Mock();provider.resolve.return_value='/provider'
        paths={'/proc/sys/kernel/random/boot_id':self.boot,'/sys/bus/i2c/devices':directory,
               '/sys/class/power_supply/sm5714-battery/device':provider}
        self.directory=directory;self.driver=driver
        ctx=mock.patch.object(c,'Path',side_effect=lambda x:paths[x]);ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(c.os,'open',return_value=3);self.open=ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(c.os,'close');self.close=ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(c.fcntl,'ioctl',side_effect=self.ioctl);ctx.start();self.addCleanup(ctx.stop)

    def ioctl(self, fd, op, packet):
        self.assertEqual((fd,op,packet.nmsgs),(3,0x0707,2))
        write,read=packet.msgs[0],packet.msgs[1]
        self.assertEqual((write.addr,write.flags,write.length),(0x49,0,1))
        self.assertEqual((read.addr,read.flags,read.length),(0x49,1,1))
        self.ioctls.append(write.buf[0]);read.buf[0]=0

    def test_exact_seven_atomic_pointer_reads_and_fd_cleanup(self):
        result=c.capture()
        self.assertEqual(self.ioctls,list(c.REGISTERS))
        self.assertFalse(result['register_data_writes']);self.close.assert_called_once_with(3)

    def test_wrong_driver_fails_before_bus_access(self):
        self.driver.resolve.return_value.name='other'
        with self.assertRaises(ValueError):c.capture()
        self.open.assert_not_called()

    def test_bus_failure_closes_fd_without_retry(self):
        with mock.patch.object(c.fcntl,'ioctl',side_effect=OSError('I2C fault')) as call:
            with self.assertRaises(OSError):c.capture()
        call.assert_called_once();self.close.assert_called_once_with(3)


class PackageTests(inherited.PackageTests):
    def setUp(self):
        ctx=mock.patch.object(inherited,'b',b);ctx.start();self.addCleanup(ctx.stop)


class RegistrationTests(inherited.RegistrationTests):
    def setUp(self):
        ctx=mock.patch.object(inherited,'m',m);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()


if __name__ == '__main__':
    unittest.main()
