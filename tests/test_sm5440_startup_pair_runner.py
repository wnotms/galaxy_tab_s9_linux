"""New short physical scope admits evidence collection, never charging health."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-295-startup-paired-voltage'
spec=importlib.util.spec_from_file_location('startup_pair_runner',R/'host_flow.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class StartupPairRunnerTests(unittest.TestCase):
    def setUp(self):
        self.raw=(R/'preflight/current-state.txt').read_text()
        m.h.PLAN=json.loads((R.parent/'test-292-passive-observation/registration.json').read_text())
        self.notes=m.h.PLAN['baseline_notes_sha256']
    def check(self,raw=None):return m.identity(raw or self.raw,self.notes)
    def test_known_refusal_is_diagnostic_only(self):
        _,boot,wifi,snap=self.check();self.assertEqual(snap['fault'],'1');self.assertEqual(snap['pump_enable_supported'],'0')
    def test_pc_scope_does_not_wait_for_wifi_dhcp(self):
        import re
        raw=re.sub(r'.*wlp1s0.*\n','',self.raw)
        self.assertIsNone(self.check(raw)[2])
    def test_wrong_config(self):
        with self.assertRaises(ValueError):self.check(self.raw.replace(m.h.PLAN['config_sha256'],'0'*64))
    def test_boot_change(self):
        with self.assertRaises(ValueError):m.identity(self.raw,self.notes,'0'*32)
    def test_pump_mode(self):
        with self.assertRaises(ValueError):self.check(self.raw.replace('sample_mode_after=0x01','sample_mode_after=0x05'))
    def test_fault_not_exempted(self):
        with self.assertRaises(ValueError):self.check(self.raw.replace('sample_faults=0x0','sample_faults=0x4'))
    def test_temperature(self):
        with self.assertRaises(ValueError):self.check(self.raw.replace('POWER_SUPPLY_TEMP=318','POWER_SUPPLY_TEMP=420'))
    def test_dcc(self):
        with self.assertRaises(ValueError):self.check(self.raw.replace('@@dcc\nabsent','@@dcc\npresent'))
    def test_data_role(self):
        with self.assertRaises(ValueError):self.check(self.raw.replace('[device]','[host]'))
    def test_actual_baseline_refusal_classified_without_health_grant(self):
        snap=self.check()[3]
        raw=(R.parent/'test-292-passive-observation/final-diagnostic/kernel-json.txt').read_text()
        boot=json.loads(raw.splitlines()[0])['_BOOT_ID']
        scan=m.scan_journal(raw,boot,6500,snap)
        self.assertTrue(scan['known_startup_refusal'])
        self.assertFalse(scan['charging_authorized'])
    def test_new_fault_and_cpu_stall_stop(self):
        snap=self.check()[3]
        source=(R.parent/'test-292-passive-observation/final-diagnostic/kernel-json.txt').read_text()
        boot=json.loads(source.splitlines()[0])['_BOOT_ID']
        for message in ['watchdog: BUG: soft lockup - CPU#4 stuck','sm5440-passive 0-0063: passive ADC fault -5; OFF verification=-5']:
            rows=source.splitlines();row=json.loads(rows[-1]);row['MESSAGE']=message;row['PRIORITY']='3';rows.append(json.dumps(row))
            with self.assertRaises(ValueError):m.scan_journal('\n'.join(rows),boot,6500,snap)
    def test_no_new_observer_and_unconditional_registered_restore(self):
        source=(R/'host_flow.py').read_text()
        self.assertNotIn('insmod',source);self.assertNotIn('rmmod',source)
        self.assertIn("'rollback-test263-boot.img'",source)
