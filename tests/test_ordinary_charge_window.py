"""Actual Test335 packets plus synthetic clocks; no physical replay implied."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ordinary_charge_window import ChargeWindow

R = ROOT / 'reference/boot-tests/test-335-fixed9-switching-observation'
P = json.loads((R / 'registration.json').read_text())
ROWS = [json.loads(x) for x in (R / 'charge/events.jsonl').read_text().splitlines()]
FIRST = next(x for x in ROWS if x['kind'] == 'sample' and x['tcpm']['POWER_SUPPLY_VOLTAGE_NOW'] == '9000000')
HEALTHY = json.loads((R / 'device-completion-charge/summary.json').read_text())['endpoint']


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.w = ChargeWindow(P, 0)

    def sample(self, now, healthy=False):
        d = copy.deepcopy(HEALTHY if healthy else FIRST)
        d['monotonic'] = now
        return d

    def test_real_initial_negative_current_waits_then_full_30s(self):
        self.assertLess(int(FIRST['battery']['POWER_SUPPLY_CURRENT_NOW']), 0)
        self.assertEqual(self.w.advance(self.sample(0))['state'], 'SETTLING')
        self.assertEqual(self.w.advance(self.sample(1))['observation_seconds'], 0)
        for t in range(2, 33):
            r = self.w.advance(self.sample(t, True))
            self.assertEqual(r['complete'], t == 32)
        self.assertEqual(r['observation_seconds'], 30)

    def test_fixed_online_pps_source_capability_is_not_active_pps(self):
        for capability in ('PD_PPS', 'PD_PPS_SPR_AVS'):
            d = self.sample(0, True)
            d['tcpm']['POWER_SUPPLY_USB_TYPE'] = 'PD [' + capability + ']'
            self.assertEqual(ChargeWindow(P, 0).advance(d)['state'], 'OBSERVE')
            d['tcpm']['POWER_SUPPLY_ONLINE'] = '2'
            with self.assertRaises(ValueError):
                ChargeWindow(P, 0).advance(d)

    def test_actual336_fixed_capability_packet_still_fails_charge_recovery(self):
        raw = (ROOT / 'reference/boot-tests/test-336-pps-off-roundtrip/first-stop-evidence/current-state.txt').read_text()
        sec = {part.splitlines()[0]: '\n'.join(part.splitlines()[1:]) for part in raw.split('@@')[1:]}
        d = self.sample(0)
        d['boot'] = d['boot_end'] = sec['boot'].strip().replace('-', '')
        for name in ('battery', 'usb', 'tcpm'):
            d[name] = dict(line.split('=', 1) for line in sec[name].splitlines() if '=' in line)
        d['pack'] = dict(mode='enabled', temp='23600')
        self.assertEqual(d['tcpm']['POWER_SUPPLY_ONLINE'], '1')
        self.assertIn('[PD_PPS]', d['tcpm']['POWER_SUPPLY_USB_TYPE'])
        self.assertLess(int(d['battery']['POWER_SUPPLY_CURRENT_NOW']), 0)
        w = ChargeWindow(dict(P, boot_id=d['boot']), 0)
        for t in range(11):
            self.assertEqual(w.advance(dict(d, monotonic=t))['state'], 'SETTLING')
        with self.assertRaises(TimeoutError):
            w.advance(dict(d, monotonic=11))

    def test_negative_does_not_wait_forever(self):
        for t in range(11): self.w.advance(self.sample(t))
        with self.assertRaises(TimeoutError): self.w.advance(self.sample(11))
        with self.assertRaises(ValueError): self.w.advance(self.sample(12, True))

    def test_settling_boundary_is_inclusive(self):
        for t in range(10): self.w.advance(self.sample(t))
        self.assertEqual(self.w.advance(self.sample(10, True))['state'], 'OBSERVE')

    def test_observation_does_not_restart_after_negative_current(self):
        self.w.advance(self.sample(0, True))
        with self.assertRaises(ValueError): self.w.advance(self.sample(1))
        with self.assertRaises(ValueError): self.w.advance(self.sample(2, True))

    def test_detach_during_settling_stops(self):
        self.w.advance(self.sample(0)); d=self.sample(1); d['tcpm']['POWER_SUPPLY_ONLINE']='0'
        with self.assertRaises(ValueError): self.w.advance(d)

    def test_safety_faults_still_stop_during_settling(self):
        for group,key,value in [('battery','POWER_SUPPLY_TEMP','380'),('battery','POWER_SUPPLY_CAPACITY','80'),('battery','POWER_SUPPLY_VOLTAGE_NOW','4300000'),('pack','mode','disabled'),('usb','POWER_SUPPLY_INPUT_CURRENT_LIMIT','1800000'),('tcpm','POWER_SUPPLY_ONLINE','2')]:
            w=ChargeWindow(P,0); d=self.sample(0); d[group][key]=value
            with self.assertRaises(ValueError): w.advance(d)
            self.assertTrue(w.stopped)

    def test_boot_pump_role_and_response_faults(self):
        for key,value in [('boot_end','0'*32),('pump',4),('direct','Y'),('roles',['[sink]','[host]'])]:
            w=ChargeWindow(P,0); d=self.sample(0); d[key]=value
            with self.assertRaises(ValueError): w.advance(d)
        self.w.advance(self.sample(0))
        with self.assertRaises(ValueError): self.w.advance(self.sample(4,True))

    def test_offline_wait_is_not_observation(self):
        for t in range(241):
            d=self.sample(t); d['tcpm']['POWER_SUPPLY_ONLINE']='0'
            self.assertEqual(self.w.advance(d)['state'],'WAIT')
        with self.assertRaises(TimeoutError): self.w.advance(dict(d,monotonic=241))

    def test_unbounded_settling_and_short_observation_rejected(self):
        with self.assertRaises(ValueError): ChargeWindow(P,0,11)
        with self.assertRaises(ValueError): ChargeWindow(dict(P,charge_seconds=29),0)

    def test_invalid_clock_stops(self):
        for value in (float('nan'),float('inf'),-1):
            w=ChargeWindow(P,0)
            with self.assertRaises(ValueError): w.advance(self.sample(value,True))


if __name__ == '__main__': unittest.main()
