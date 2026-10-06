#!/usr/bin/env python3
import importlib.util,unittest
from pathlib import Path
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('guard328',Path(__file__).with_name('guard.py'));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class GuardTests(unittest.TestCase):
    def setUp(self):
        self.s=dict(battery={'POWER_SUPPLY_HEALTH':'Good','POWER_SUPPLY_PRESENT':'1','POWER_SUPPLY_TEMP':'247','POWER_SUPPLY_CAPACITY':'79','POWER_SUPPLY_VOLTAGE_NOW':'4110000'},adc=dict(mode=4,adc_enabled=True,vbus_mv=9000,ibus_ua=1500000,vbat_uv=4110000,die_decic=300),tcpm={'POWER_SUPPLY_ONLINE':'2','POWER_SUPPLY_USB_TYPE':'PD [PD_PPS]','POWER_SUPPLY_CURRENT_MAX':'3000000','POWER_SUPPLY_CURRENT_NOW':'1800000','POWER_SUPPLY_VOLTAGE_NOW':'9000000'})
    def bad(self,group,key,value):
        self.s[group][key]=value
        with self.assertRaises(ValueError):g.check(self.s,True)
    def test_clean(self):self.assertTrue(g.check(self.s,True))
    def test_soc80(self):self.bad('battery','POWER_SUPPLY_CAPACITY','80')
    def test_temperature(self):self.bad('battery','POWER_SUPPLY_TEMP','420')
    def test_vbat(self):self.bad('adc','vbat_uv',4400000)
    def test_vbus(self):self.bad('adc','vbus_mv',10501)
    def test_current_fraction(self):self.bad('adc','ibus_ua',1800625)
    def test_die(self):self.bad('adc','die_decic',850)
    def test_reverse_mode(self):self.bad('adc','mode',8)
    def test_adc_disabled(self):self.bad('adc','adc_enabled',False)
    def test_fixed_not_pps(self):self.bad('tcpm','POWER_SUPPLY_USB_TYPE','[PD]')
    def test_contract_current(self):self.bad('tcpm','POWER_SUPPLY_CURRENT_NOW','3000000')
    def test_fixed_online_is_not_pps(self):self.bad('tcpm','POWER_SUPPLY_ONLINE','1')
    def test_source_gone(self):self.bad('tcpm','POWER_SUPPLY_ONLINE','0')
    def test_settle_mismatch(self):self.bad('tcpm','POWER_SUPPLY_VOLTAGE_NOW','10000000')
    def test_continuous_math(self):
        r={0x10:4,0x1c:11,0x1e:153,0x1f:64,0x22:90,0x23:0,0x27:128,0x28:0,0x26:20}
        d=g.decoded(r);self.assertEqual(d['ibus_ua'],1800000);self.assertEqual(d['vbat_uv'],4096000);self.assertEqual(d['die_decic'],325)
    def test_fault_messages(self):
        for msg in ['direct-charge start failed: -110','retained fault=0x80','fixed fallback failed: -5','Kernel panic','soft lockup','stopping direct charge: cap=80']:self.assertTrue(g.fault(msg))
        self.assertFalse(g.fault('direct charge started: PPS 9000 mV/1800 mA'))
    def fake(self):
        self.clock=0
        def clock():return self.clock
        def sleep(n):self.clock+=n
        return clock,sleep
    def test_bounded_clean_and_cleanup(self):
        clock,sleep=self.fake();hw=Mock();hw.sample.return_value=self.s;hw.stop.return_value={'pump_mode':1};emit=Mock()
        result=g.observe(hw,lambda:[],emit,clock,sleep)
        self.assertGreaterEqual(result['active_seconds'],30);hw.stop.assert_called_once()
    def test_first_fault_stops_and_cleans(self):
        clock,sleep=self.fake();hw=Mock();emit=Mock()
        with self.assertRaises(ValueError):g.observe(hw,lambda:[{'MESSAGE':'direct-charge start failed: -5'}],emit,clock,sleep)
        hw.sample.assert_not_called();hw.stop.assert_called_once();self.assertEqual(self.clock,0)
    def test_i2c_failure_cleanup(self):
        clock,sleep=self.fake();hw=Mock();hw.sample.side_effect=OSError('I2C');emit=Mock()
        with self.assertRaises(OSError):g.observe(hw,lambda:[],emit,clock,sleep)
        hw.stop.assert_called_once()
    def test_cleanup_failure_never_pass(self):
        clock,sleep=self.fake();hw=Mock();hw.sample.return_value=self.s;hw.stop.side_effect=ValueError('OFF not proved')
        with self.assertRaises(ValueError):g.observe(hw,lambda:[],Mock(),clock,sleep)
    def test_unexpected_second_start(self):
        clock,sleep=self.fake();hw=Mock();hw.sample.return_value=self.s
        with self.assertRaises(ValueError):g.observe(hw,lambda:[{'MESSAGE':'direct charge started: PPS 9000 mV/1800 mA'}],Mock(),clock,sleep)
        hw.stop.assert_called_once()
    def test_first_start_event_after_mode_is_not_second_start(self):
        clock,sleep=self.fake();hw=Mock();hw.sample.return_value=self.s;calls=iter([[],[{'MESSAGE':'direct charge started: PPS 9000 mV/1800 mA'}]])
        result=g.observe(hw,lambda:next(calls,[]),Mock(),clock,sleep);self.assertEqual(result['verdict'],'PPS_30S_OBSERVED')
    def test_persistent_off_refusal(self):
        clock,sleep=self.fake();hw=Mock();off=dict(self.s,adc=dict(self.s['adc'],mode=0));hw.sample.return_value=off
        seq=iter([[{'MESSAGE':'direct charge started: PPS 9000 mV/1800 mA'}]])
        with self.assertRaises(ValueError):g.observe(hw,lambda:next(seq,[]),Mock(),clock,sleep)
        self.assertLess(self.clock,4);hw.stop.assert_called_once()
if __name__=='__main__':unittest.main()
