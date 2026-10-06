#!/usr/bin/env python3
import importlib.util,unittest
from pathlib import Path
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('current_guard',Path(__file__).resolve().parents[1]/'scripts/x710-pps-guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
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


class FixedReturnTests(unittest.TestCase):
    def setUp(self):
        self.tcpm = dict(POWER_SUPPLY_ONLINE='1', POWER_SUPPLY_USB_TYPE='PD [PD_PPS]',
                         POWER_SUPPLY_VOLTAGE_NOW='9000000', POWER_SUPPLY_VOLTAGE_MIN='9000000',
                         POWER_SUPPLY_VOLTAGE_MAX='9000000', POWER_SUPPLY_CURRENT_NOW='1500000',
                         POWER_SUPPLY_CURRENT_MAX='1500000')
        self.usb = dict(POWER_SUPPLY_ONLINE='1', POWER_SUPPLY_USB_TYPE='SDP DCP [PD]',
                        POWER_SUPPLY_INPUT_CURRENT_LIMIT='1500000')

    def test_pps_capability_at_fixed_online(self):
        for capability in ('PD', 'PD_PPS', 'PD_SPR_AVS', 'PD_PPS_SPR_AVS'):
            with self.subTest(capability=capability):
                self.tcpm['POWER_SUPPLY_USB_TYPE'] = '[' + capability + ']'
                g.check_fixed_return(self.tcpm, self.usb)

    def test_active_pps_avs_offline_or_unknown_blocked(self):
        for online in ('0', '2', '3', '4', ''):
            with self.subTest(online=online), self.assertRaises(ValueError):
                g.check_fixed_return(dict(self.tcpm, POWER_SUPPLY_ONLINE=online), self.usb)

    def test_invalid_fixed_voltage_or_current_blocked(self):
        for key, value in [('POWER_SUPPLY_VOLTAGE_NOW', '8720000'),
                           ('POWER_SUPPLY_VOLTAGE_MIN', '5000000'),
                           ('POWER_SUPPLY_VOLTAGE_MAX', '10500000'),
                           ('POWER_SUPPLY_CURRENT_NOW', '1800000'),
                           ('POWER_SUPPLY_CURRENT_MAX', '1800000'),
                           ('POWER_SUPPLY_CURRENT_NOW', '0'),
                           ('POWER_SUPPLY_USB_TYPE', '[SDP]')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                g.check_fixed_return(dict(self.tcpm, **{key: value}), self.usb)

    def test_switching_not_released_is_still_failure(self):
        for key, value in [('POWER_SUPPLY_ONLINE', '0'),
                           ('POWER_SUPPLY_USB_TYPE', '[PD_PPS]'),
                           ('POWER_SUPPLY_INPUT_CURRENT_LIMIT', '1800000'),
                           ('POWER_SUPPLY_INPUT_CURRENT_LIMIT', '0')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                g.check_fixed_return(self.tcpm, dict(self.usb, **{key: value}))

    def test_test330_fixed_protocol_does_not_prove_switching_release(self):
        import json
        evidence = (Path(__file__).resolve().parents[1] /
                    'reference/boot-tests/test-330-fedora-pps-short/pps-observation/events.jsonl.txt')
        samples = [row['data'] for line in evidence.read_text().splitlines()
                   if (row := json.loads(line))['kind'] == 'sample']
        fixed = [s['tcpm'] for s in samples
                 if s['tcpm'].get('POWER_SUPPLY_ONLINE') == '1'
                 and '[PD_PPS]' in s['tcpm'].get('POWER_SUPPLY_USB_TYPE', '')
                 and s['tcpm'].get('POWER_SUPPLY_VOLTAGE_NOW') == '9000000'
                 and s['tcpm'].get('POWER_SUPPLY_CURRENT_NOW') == '1500000']
        self.assertTrue(fixed)
        for source in fixed:
            # Fixture switching state is separate; raw source alone cannot pass cleanup.
            g.check_fixed_return(source, self.usb)
            with self.assertRaises(ValueError):
                g.check_fixed_return(source, dict(self.usb, POWER_SUPPLY_ONLINE='0'))

    def test_missing_evidence_blocked(self):
        for key in self.tcpm:
            t = dict(self.tcpm); del t[key]
            with self.subTest(key=key), self.assertRaises((ValueError, KeyError)):
                g.check_fixed_return(t, self.usb)

if __name__ == '__main__':
    unittest.main()
