import copy,json,unittest
from pathlib import Path
from sample_gate import validate_sample,gauge_entry_hint

class Gates(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[3]
        prior=json.loads((root/'reference/boot-tests/test-267-sm5440-cached-consumer-physical/restored-endpoint/summary.json').read_text())
        self.b=dict(prior['battery'],POWER_SUPPLY_STATUS='Discharging',POWER_SUPPLY_CURRENT_NOW='-500000')
        self.u={'POWER_SUPPLY_ONLINE':'0'};self.s=copy.deepcopy(prior['snapshot'])
    def check(self):validate_sample(self.b,self.u,self.s,306)
    def test_normal_discharge_retains_known_failed_monitor(self):self.check()
    def test_power_still_online_refused(self):
        self.u['POWER_SUPPLY_ONLINE']='1'
        with self.assertRaises(ValueError):self.check()
    def test_positive_or_zero_current_refused(self):
        for value in ['0','1000']:
            self.b['POWER_SUPPLY_CURRENT_NOW']=value
            with self.assertRaises(ValueError):self.check()
    def test_over_voltage_refused(self):
        self.b['POWER_SUPPLY_VOLTAGE_NOW']='4440001'
        with self.assertRaises(ValueError):self.check()
    def test_42C_or_fast_heating_refused(self):
        for value in ['420','406']:
            self.b['POWER_SUPPLY_TEMP']=value
            with self.assertRaises(ValueError):self.check()
    def test_invalid_sensor_or_health_refused(self):
        self.b['POWER_SUPPLY_HEALTH']='Unknown'
        with self.assertRaises(ValueError):self.check()
    def test_new_fault_or_mode_change_refused(self):
        for key,val in [('fault','0'),('sample_faults','0x82'),('sample_mode_after','0x05')]:
            s=dict(self.s);s[key]=val
            with self.assertRaises(ValueError):validate_sample(self.b,self.u,s,306)
    def test_old_ADC_is_not_readiness_hint(self):
        self.assertFalse(gauge_entry_hint(self.b))
        self.b['POWER_SUPPLY_CAPACITY']='79';self.b['POWER_SUPPLY_VOLTAGE_NOW']='4299000'
        self.assertTrue(gauge_entry_hint(self.b))
        self.b['POWER_SUPPLY_VOLTAGE_NOW']='4300000';self.assertFalse(gauge_entry_hint(self.b))
if __name__=='__main__':unittest.main()
