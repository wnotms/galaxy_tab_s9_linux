"""Exercise the failed configured/offline capture and conservative recovery gates."""
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from adbd_cable_evidence import CableCycle, DISABLE_WARNING, review_adbd

BOOT = '461c1408e42643afae5b48162771d077'
SHA = '0' * 64


class AdbdCableEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cycle = CableCycle(BOOT, 834, SHA)

    def sample(self, start, online=False, native_seen=False, **changes):
        args = dict(online=online, native_seen=native_seen, started=start, ended=start+.5,
                    uptime=start+100, boot=BOOT, pid=834, sha256=SHA,
                    udc_binding='a600000.usb', udc_state='configured')
        args.update(changes)
        return self.cycle.sample(**args)

    def returned(self):
        self.sample(0); self.sample(11); self.sample(12, online=True)

    def recover(self, now=13, **changes):
        args = dict(native_boot=BOOT, native_pid=834, native_sha256=SHA, ncm_boot=BOOT, now=now)
        args.update(changes)
        return self.cycle.recovered(**args)

    def test_configured_udc_with_offline_supply_and_absent_host_is_unplug(self):
        self.returned(); self.assertTrue(self.cycle.return_seen)

    def test_host_absence_with_online_supply_does_not_prove_unplug(self):
        self.sample(0, online=True); self.assertIsNone(self.cycle.first_off_end)

    def test_offline_supply_with_host_still_present_does_not_prove_unplug(self):
        self.sample(0, native_seen=True); self.assertIsNone(self.cycle.first_off_end)

    def test_return_detected_before_native_transport_returns(self):
        self.returned(); self.assertEqual(self.cycle.last_off_start, 11)

    def test_short_unplug_stops(self):
        self.sample(0); self.sample(9)
        with self.assertRaises(ValueError): self.sample(10, online=True)

    def test_recovery_uses_last_off_command_start_without_fake_delay(self):
        self.returned(); self.assertEqual(self.recover(now=70), 59)

    def test_recovery_over60_stops(self):
        self.returned()
        with self.assertRaises(ValueError): self.recover(now=71.01)

    def test_changed_wifi_boot_stops(self):
        with self.assertRaises(ValueError): self.sample(0, boot='1'*32)

    def test_changed_daemon_pid_stops(self):
        with self.assertRaises(ValueError): self.sample(0, pid=835)

    def test_changed_daemon_hash_stops(self):
        with self.assertRaises(ValueError): self.sample(0, sha256='1'*64)

    def test_changed_udc_binding_stops(self):
        with self.assertRaises(ValueError): self.sample(0, udc_binding='')

    def test_non_monotonic_host_bounds_stops(self):
        self.sample(1)
        with self.assertRaises(ValueError): self.sample(1.1)

    def test_changed_native_boot_stops(self):
        self.returned()
        with self.assertRaises(ValueError): self.recover(native_boot='1'*32)

    def test_missing_ncm_boot_stops(self):
        self.returned()
        with self.assertRaises(ValueError): self.recover(ncm_boot='')

    def test_observation_is_elapsed_after_recovery(self):
        self.returned(); self.recover(now=13)
        self.assertFalse(self.cycle.observed(162.99)); self.assertTrue(self.cycle.observed(163))

    def test_observation_without_recovery_stops(self):
        with self.assertRaises(ValueError): self.cycle.observed(10000)

    def journal(self, texts=None):
        texts = texts or [(20, 900, 'I', 'UsbFfs-monitor thread spawned'),
                          (20.01, 900, 'I', 'USB event: FUNCTIONFS_DISABLE'),
                          (20.01, 900, 'W', DISABLE_WARNING),
                          (20.15, 901, 'I', 'USB event: FUNCTIONFS_ENABLE'),
                          (20.16, 902, 'I', 'UsbFfs-worker thread spawned')]
        return '\n'.join(json.dumps(dict(_BOOT_ID=BOOT, _PID='834', PRIORITY='6',
                         __MONOTONIC_TIMESTAMP=str(round(at*1e6)),
                         MESSAGE=f'09-28 22:19:38.752   834   {tid} {level} gts9-adbd-reconnect: usb.cpp:347 {text}'))
                         for at,tid,level,text in texts)

    def review(self, raw=None, **changes):
        args = dict(expected_boot=BOOT, expected_pid=834, source_floor=10, allow_pre_enable_disable=True)
        args.update(changes)
        return review_adbd(self.journal() if raw is None else raw, **args)

    def test_bounded_warning_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError): self.review(allow_pre_enable_disable=False)

    def test_exact_warning_with_monitor_disable_enable_worker_is_bounded(self):
        self.assertEqual(len(self.review()['new_pre_enable_disable_warnings']), 1)

    def test_warning_without_matching_monitor_context_stops(self):
        with self.assertRaises(ValueError): self.review(self.journal().replace('thread spawned','other event'))

    def test_warning_without_enable_stops(self):
        with self.assertRaises(ValueError): self.review(self.journal().replace('FUNCTIONFS_ENABLE','FUNCTIONFS_SUSPEND'))

    def test_warning_enable_after5s_stops(self):
        raw=self.journal().replace('20150000','26000000')
        with self.assertRaises(ValueError): self.review(raw)

    def test_warning_without_worker_stops(self):
        with self.assertRaises(ValueError): self.review(self.journal().replace('UsbFfs-worker','Other-worker'))

    def test_warning_outside_observed_physical_transition_stops(self):
        with self.assertRaises(ValueError): self.review(warning_source_range=(21,30))

    def test_repeat_warning_stops(self):
        second = self.journal([(21,900,'I','UsbFfs-monitor thread spawned'),
                               (21.01,900,'I','USB event: FUNCTIONFS_DISABLE'),
                               (21.01,900,'W',DISABLE_WARNING),
                               (21.15,901,'I','USB event: FUNCTIONFS_ENABLE'),
                               (21.16,902,'I','UsbFfs-worker thread spawned')])
        with self.assertRaisesRegex(ValueError, 'multiple pre-enable'):
            self.review(self.journal()+'\n'+second)

    def test_other_warning_stops(self):
        with self.assertRaises(ValueError): self.review(self.journal().replace(DISABLE_WARNING,'received FUNCTIONFS_ENABLE while not bound?'))

    def test_error_at_info_journal_priority_stops(self):
        with self.assertRaises(ValueError): self.review(self.journal([(20,900,'E','failed to submit read')]))

    def test_empty_or_malformed_journal_stops(self):
        for raw in ('', '{'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): self.review(raw)

    def test_changed_journal_boot_or_pid_stops(self):
        for old,new in ((BOOT,'1'*32), ('"_PID": "834"','"_PID": "999"')):
            with self.subTest(new=new), self.assertRaises(ValueError): self.review(self.journal().replace(old,new))

    def test_actual_cycle01_full_journal_replay(self):
        root = Path(__file__).resolve().parents[1]
        raw=(root/'reference/boot-tests/test-253-adbd-usb-reconnect/attempt-03/cycle-01/adbd-journal-json.txt').read_text()
        report=self.review(raw, source_floor=1480)
        self.assertEqual(report['new_pre_enable_disable_warnings'][0]['enable_source_seconds'],1510.565311)


class AdbdCableRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('adbd_cable_observer', root/'scripts/adbd-cable-observer.py')
        cls.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.runner)

    def test_proposed_registration_blocks_before_device_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp)/'policy.json'; plan.write_text('{"owner_adopted":false}')
            with patch.object(self.runner.subprocess, 'Popen') as popen, self.assertRaises(ValueError):
                self.runner.load_registration(plan)
            popen.assert_not_called()

    def test_actual_snapshot_records_configured_offline(self):
        snap = f'{BOOT}\n1500.2 12000.0\nconfigured\n834\n{SHA} /proc/834/exe\na600000.usb\n0\n'
        value = self.runner.parse_snapshot(snap)
        self.assertFalse(value['online']); self.assertEqual(value['udc_state'], 'configured')

    def test_incomplete_snapshot_and_shell_are_not_success(self):
        with self.assertRaises(ValueError): self.runner.parse_snapshot(BOOT+'\n')
        with self.assertRaises(ValueError): self.runner.native_identity(BOOT+'\n')

    def test_first_wifi_identity_failure_stops_before_recovery(self):
        class Recorder:
            def __init__(self): self.calls=[]; self.snapshots=0
            def command(self, name, argv, **kwargs):
                self.calls.append(name)
                if name.endswith('wifi') or name=='initial-wifi-state':
                    self.snapshots+=1
                    boot=BOOT if self.snapshots==1 else '1'*32
                    return f'{boot}\n5000 30000\nconfigured\n834\n{SHA} /proc/834/exe\na600000.usb\n1\n',0
                return '',0
            def adb(self, name, *args, **kwargs): self.calls.append(name); return BOOT,0
            def ps(self, name, *args, **kwargs): self.calls.append(name); return '',0
            def host_adb(self, name, *args, **kwargs): self.calls.append(name); return 'List of devices attached\n',0
        class Process:
            pid=123; returncode=-15
            def poll(self): return None
            def terminate(self): pass
            def wait(self, **kwargs): return -15
        rec=Recorder()
        policy=dict(boot_id=BOOT,daemon_pid=834,daemon_sha256=SHA,wifi_address='192.0.2.1')
        previous_policy=self.runner.p.P
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'cycle-01'
            with patch.object(self.runner.p,'baseline',return_value={}), \
                 patch.object(self.runner.subprocess,'Popen',return_value=Process()), \
                 self.assertRaises(ValueError):
                self.runner.run_cycle(folder,policy,recorder=rec,clock=lambda:100,sleep=lambda _:None)
            self.assertEqual(json.loads((folder/'failure.json').read_text())['verdict'],'stopped')
            self.assertFalse(any(name.startswith('recovery-') for name in rec.calls))
            self.assertEqual(sum(name=='initial-native-shell' for name in rec.calls),1)
            self.assertEqual(self.runner.p.P, previous_policy)
