"""Dynamic thermal identity/device-normal endpoint, no hardcoded zone numbers."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import json
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-300-passive-thermal-registration'
spec=importlib.util.spec_from_file_location('thermal300',R/'host_flow.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BOOT='1'*32
RAW='@@boot\n'+BOOT+'\n@@zones\n/sys/class/thermal/thermal_zone0|cpu0-thermal|enabled\n/sys/class/thermal/thermal_zone37|sm5714-battery|enabled\n@@pack-temperature\n31800\n@@battery\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_TEMP=318\n'
class ThermalDeviceRunnerTests(unittest.TestCase):
    def test_actual_names_and_pack_temperature_accept(self):self.assertEqual(m.parse_thermal(RAW,BOOT)['pack_millic'],31800)
    def test_zone_number_can_change(self):self.assertTrue(m.parse_thermal(RAW.replace('zone37','zone45'),BOOT)['pack_zone'].endswith('zone45'))
    def test_passive_zone_must_be_absent_even_if_disabled(self):
        with self.assertRaises(ValueError):m.parse_thermal(RAW.replace('@@pack-temperature','/sys/class/thermal/thermal_zone39|sm5440-passive|disabled\n@@pack-temperature'),BOOT)
    def test_missing_or_disabled_pack_refuses(self):
        for raw in [RAW.replace('sm5714-battery','other'),RAW.replace('sm5714-battery|enabled','sm5714-battery|disabled')]:
            with self.assertRaises(ValueError):m.parse_thermal(raw,BOOT)
    def test_invalid_unsafe_inconsistent_sensor_refuses(self):
        for raw in [RAW.replace('31800','No data available'),RAW.replace('31800','42000'),RAW.replace('31800','30000'),RAW.replace('HEALTH=Good','HEALTH=Unknown')]:
            with self.assertRaises(ValueError):m.parse_thermal(raw,BOOT)
    def test_changed_boot_refuses(self):
        with self.assertRaises(ValueError):m.parse_thermal(RAW,'2'*32)
    def test_retention_only_after_endpoint_with_recovery_available(self):
        source=(R/'host_flow.py').read_text();self.assertLess(source.index("admitted['thermal_endpoint']=observe_thermal"),source.index("write(R/'installed-status.json'"))
        for term in ['WindowsCode43','pump mode not OFF','CPU/kernel failure','rollback-test263-boot.img','gts9-test300']:self.assertIn(term,source)
        self.assertNotIn('insmod',source);self.assertNotIn('rmmod',source)

    def test_new_kernel_cannot_waive_old_thermal_warning(self):
        message='thermal thermal_zone37: Unable to get temperature, disabling!'
        raw=json.dumps({'MESSAGE':message,'PRIORITY':'3'})+'\n'
        def scan(*args,**kwargs):return dict(suspects=[dict(row=0,message=message)],fault_counts={})
        with mock.patch.object(m.h.g.evidence,'inspect_journal',side_effect=scan),mock.patch.object(m.h.g,'startup_triplets',return_value=[]),mock.patch.dict(m.h.PLAN,{'before_boot_id':BOOT}):
            with self.assertRaises(ValueError):m.scan_journal(raw,BOOT,500,{'fault':'1'})
            self.assertEqual(len(m.scan_journal(raw,BOOT,500,{'fault':'1'},baseline_thermal_warning=True)['known_startup_refusal']),1)
            with self.assertRaises(ValueError):m.scan_journal(raw,'2'*32,20,{'fault':'1'},baseline_thermal_warning=True)
