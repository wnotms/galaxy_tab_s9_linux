"""Full-battery passive scope boundaries, replaying a preserved device snapshot."""
import sys
import unittest
from pathlib import Path
from device_gate import properties, validate_device
from snapshot_gate import validate_snapshot

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'reference/boot-tests/test-263-sm5440-adc-snapshot/attempt-01'

class Gates(unittest.TestCase):
    def setUp(self):
        raw = (OLD / 'observation/sample-000.txt').read_text()
        self.b = properties(raw.split('@@battery\n')[1].split('@@passive\n')[0])
        self.p = properties(raw.split('@@passive\n')[1].split('@@power-role\n')[0])
        self.s = raw.split('@@snapshot\n')[1].split('@@snapshot-after\n')[0]

    def device(self):
        validate_device(self.b, self.p, '[sink]', '[device]')

    def vbat(self, uv):
        data = dict(x.split('=',1) for x in self.s.splitlines())
        a = [int(x,16) for x in data['sample_adc'].split()]
        bits = (uv-2048000)//500
        a[9], a[10] = bits>>5, (bits&31)<<3
        data['sample_adc']=' '.join(f'{x:02x}' for x in a)
        data['sample_vbat_uv']=str(uv)
        return '\n'.join(f'{k}={v}' for k,v in data.items())+'\n'

    def test_actual_known_snapshot_retains_all_gates(self):
        self.device(); validate_snapshot(self.s)

    def test_full_SOC_is_passive_not_charging_power_qualification(self):
        self.b['POWER_SUPPLY_CAPACITY']='100'; self.device()

    def test_SOC_impossible_refused(self):
        self.b['POWER_SUPPLY_CAPACITY']='101'
        with self.assertRaises(ValueError):self.device()

    def test_float_voltage_boundary(self):
        self.b['POWER_SUPPLY_VOLTAGE_NOW']='4440000';self.device()
        self.b['POWER_SUPPLY_VOLTAGE_NOW']='4440001'
        with self.assertRaises(ValueError):self.device()

    def test_raw_ADC_at_float_boundary(self):
        validate_snapshot(self.vbat(4440000))
        with self.assertRaises(ValueError):validate_snapshot(self.vbat(4440500))

    def test_42C_refused(self):
        self.b['POWER_SUPPLY_TEMP']='420'
        with self.assertRaises(ValueError):self.device()

    def test_nonzero_pump_current_refused(self):
        self.p['POWER_SUPPLY_CURRENT_NOW']='625'
        with self.assertRaises(ValueError):self.device()

    def test_changed_role_refused(self):
        with self.assertRaises(ValueError):validate_device(self.b,self.p,'[sink]','[host]')

    def test_9V_not_part_of_PC_regression(self):
        self.p['POWER_SUPPLY_VOLTAGE_NOW']='9000000'
        with self.assertRaises(ValueError):self.device()

    def test_stale_snapshot_refused(self):
        with self.assertRaises(ValueError):validate_snapshot(self.s.replace('sample_age_ms=156','sample_age_ms=2501'))

    def test_active_or_fault_snapshot_refused(self):
        for src,dst in [('sample_mode_after=0x01','sample_mode_after=0x0d'),('fault=0','fault=1')]:
            with self.subTest(src=src):
                self.assertIn(src,self.s)
                with self.assertRaises(ValueError):validate_snapshot(self.s.replace(src,dst))

    def test_module_transaction_only_changes_slot_names(self):
        before=(ROOT/'reference/boot-tests/test-263-sm5440-adc-snapshot/attempt-01/STAGED_FILES.json').read_text()
        helper=Path(__file__).with_name('module-swap.sh').read_text()
        # Original proven adapter is preserved in Windows; registration changes
        # only new test267 backup slots, not the transaction implementation.
        original=Path('/mnt/d/android/gts9-active/gts9-test263/module-swap.sh').read_text()
        self.assertEqual(helper,original.replace('test263','test267'))
        self.assertIn('.gts9-test267-original',helper)

if __name__=='__main__': unittest.main()
