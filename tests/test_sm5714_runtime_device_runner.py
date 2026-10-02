"""Execute the one-call physical runner's evidence parser without a device."""
import errno
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-298-tcpm-runtime-device'
spec=importlib.util.spec_from_file_location('runtime_device_runner',R/'host_flow.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BOOT='1'*32

def packet(mv=5000,ma=1800,ret=0):
    f=dict(format='sm5714-current-port-v1',ret=ret,charging_grant=0,values_are_not_physical_measurements=1)
    if ret==0:
        f.update(instance=1,source_generation=2,budget_generation=4,started_ms=30000,completed_ms=30001,online=1,usb_type=6,voltage_uv=mv*1000,current_ua=ma*1000,budget_mv=mv,budget_ma=ma,charge_requested=1,nr_source_pdos=1,source_pdo_1=hex(((mv//50)<<10)|(ma//10)))
    supply='POWER_SUPPLY_USB_TYPE=C [PD] PD_PPS\n' if ret==0 else 'POWER_SUPPLY_USB_TYPE=[C] PD PD_PPS\n'
    supply+='POWER_SUPPLY_VOLTAGE_NOW='+str(mv*1000)+'\nPOWER_SUPPLY_CURRENT_NOW='+str(ma*1000)+'\n'
    return '@@before\n'+BOOT+'\n@@runtime\n'+''.join(str(k)+'='+str(v)+'\n' for k,v in f.items())+'@@supply\n'+supply+'@@after\n'+BOOT+'\n'

class RuntimeDeviceRunnerTests(unittest.TestCase):
    def test_fixed_5v_actual_evidence_no_charging_grant(self):
        result=m.parse_runtime(packet(),BOOT);self.assertEqual(result['api_ret'],0);self.assertFalse(result['charging_authorized']);self.assertFalse(result['physical_voltage_verified'])
    def test_fixed_9v_valid_ceiling(self):self.assertEqual(m.parse_runtime(packet(9000,1500),BOOT)['api_ret'],0)
    def test_pc_without_capability_is_explicit_refusal(self):self.assertEqual(m.parse_runtime(packet(ret=-errno.ENODATA),BOOT)['verdict'],'PC_NO_PD_CAPABILITY_REFUSED')
    def test_no_data_cannot_conflict_with_real_pd(self):
        with self.assertRaises(ValueError):m.parse_runtime(packet(ret=-errno.ENODATA).replace('[C] PD','C [PD]'),BOOT)
    def test_first_unexplained_refusal_stops(self):
        for ret in (-errno.EAGAIN,-errno.EIO,-errno.ESHUTDOWN,-errno.EBUSY):
            with self.subTest(ret=ret),self.assertRaises(ValueError):m.parse_runtime(packet(ret=ret),BOOT)
    def test_no_extra_read_retry_module_or_activation(self):
        source=(R/'host_flow.py').read_text();operation=source.split('def observe_runtime(',1)[1].split('def install(',1)[0]
        self.assertEqual(operation.count("'one-runtime-call'"),1)
        for forbidden in ('while ','insmod','rmmod','set_property','retry'):self.assertNotIn(forbidden,operation)
        self.assertIn('gts9-test298',source)
    def test_changed_boot_stops(self):
        with self.assertRaises(ValueError):m.parse_runtime(packet().replace('@@after\n'+BOOT,'@@after\n'+'2'*32),BOOT)
    def test_ceiling_source_and_mirror_gates(self):
        cases=[packet().replace('usb_type=6','usb_type=8'),packet().replace('budget_mv=5000','budget_mv=12000'),packet(9000,1800),packet().replace('instance=1','instance=0'),packet().replace('current_ua=1800000','current_ua=1900000'),packet().replace('source_pdo_1=0x190b4','source_pdo_1=0x19032'),packet().replace('POWER_SUPPLY_CURRENT_NOW=1800000','POWER_SUPPLY_CURRENT_NOW=500000'),packet().replace('completed_ms=30001','completed_ms=32000')]
        for raw in cases:
            with self.subTest(raw=raw),self.assertRaises(ValueError):m.parse_runtime(raw,BOOT)
    def test_duplicate_or_grant_stops(self):
        for raw in [packet().replace('ret=0\n','ret=0\nret=0\n'),packet().replace('charging_grant=0','charging_grant=1')]:
            with self.assertRaises(ValueError):m.parse_runtime(raw,BOOT)
    def test_device_safety_and_unconditional_restore_retained(self):
        source=(R/'host_flow.py').read_text()
        for term in ('WindowsCode43','battery/temperature','pump mode not OFF','CPU/kernel failure','rollback-test263-boot.img','gts9-test298'):self.assertIn(term,source)
        swap=(R/'module-swap.sh').read_text();self.assertIn('.gts9-test298-original',swap);self.assertNotIn('.gts9-test296',swap)
