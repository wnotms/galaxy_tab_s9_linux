import copy
import importlib.util
import json
from pathlib import Path
import unittest

R = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('test335_' + name, R / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


o = load('observe')
h = load('run')
P = json.loads((R / 'registration.json').read_text())


class GateTests(unittest.TestCase):
    def setUp(self):
        self.d = dict(boot=P['boot_id'], boot_end=P['boot_id'], direct='N', fixed_check='absent', pump=1, monotonic=0,
                      battery={'POWER_SUPPLY_HEALTH': 'Good', 'POWER_SUPPLY_PRESENT': '1', 'POWER_SUPPLY_VOLTAGE_MAX_DESIGN': '4440000', 'POWER_SUPPLY_CAPACITY': '69', 'POWER_SUPPLY_VOLTAGE_NOW': '4100000', 'POWER_SUPPLY_TEMP': '246', 'POWER_SUPPLY_CURRENT_NOW': '1000000', 'POWER_SUPPLY_STATUS': 'Charging'},
                      usb={'POWER_SUPPLY_ONLINE': '1', 'POWER_SUPPLY_USB_TYPE': '[PD]', 'POWER_SUPPLY_INPUT_CURRENT_LIMIT': '1500000'},
                      tcpm={'POWER_SUPPLY_ONLINE': '1', 'POWER_SUPPLY_USB_TYPE': '[PD]', 'POWER_SUPPLY_VOLTAGE_NOW': '9000000', 'POWER_SUPPLY_VOLTAGE_MAX': '9000000', 'POWER_SUPPLY_CURRENT_MAX': '1500000'},
                      pack={'mode': 'enabled', 'temp': '24600'}, roles=['[sink]', '[device]'])

    def reject(self, group, key, value):
        self.d[group][key] = value
        with self.assertRaises(ValueError):
            o.validate(self.d, P, 'charge')

    def test_clean_charge(self):
        self.assertEqual(o.validate(self.d, P, 'charge'), self.d)

    def test_unexplained_reboot(self):
        self.d['boot_end'] = '0' * 32
        with self.assertRaises(ValueError): o.validate(self.d, P)

    def test_pump_on(self):
        for value in (4, 8, 12):
            self.d['pump'] = value
            with self.assertRaises(ValueError): o.validate(self.d, P)

    def test_flags(self):
        for key in ('direct', 'fixed_check'):
            d = copy.deepcopy(self.d); d[key] = 'Y'
            with self.assertRaises(ValueError): o.validate(d, P)

    def test_soc_boundary(self): self.reject('battery', 'POWER_SUPPLY_CAPACITY', '80')
    def test_vbat_boundary(self): self.reject('battery', 'POWER_SUPPLY_VOLTAGE_NOW', '4300000')
    def test_temp_boundary(self): self.reject('battery', 'POWER_SUPPLY_TEMP', '380')
    def test_pack_disabled(self): self.reject('pack', 'mode', 'disabled')
    def test_pack_invalid(self): self.reject('pack', 'temp', '0')
    def test_negative_charging_current(self): self.reject('battery', 'POWER_SUPPLY_CURRENT_NOW', '-1')
    def test_input_ceiling(self): self.reject('usb', 'POWER_SUPPLY_INPUT_CURRENT_LIMIT', '1800000')
    def test_source_ceiling(self): self.reject('tcpm', 'POWER_SUPPLY_CURRENT_MAX', '1000000')
    def test_pps(self): self.reject('tcpm', 'POWER_SUPPLY_ONLINE', '2')
    def test_high_voltage(self): self.reject('tcpm', 'POWER_SUPPLY_VOLTAGE_NOW', '12000000')
    def test_host_role(self):
        self.d['roles'] = ['[sink]', '[host]']
        with self.assertRaises(ValueError): o.validate(self.d, P)

    def test_discharge(self):
        self.d['battery'].update(POWER_SUPPLY_STATUS='Discharging', POWER_SUPPLY_CURRENT_NOW='-1000000')
        self.d['usb']['POWER_SUPPLY_ONLINE'] = self.d['tcpm']['POWER_SUPPLY_ONLINE'] = '0'
        o.validate(self.d, P, 'discharge')

    def test_continuity_30s(self):
        start = previous = None
        for t in range(31):
            self.d['monotonic'] = t
            start, done, duration = o.progress(self.d, P, 'charge', start, previous)
            self.assertEqual(done, t == 30)
            previous = t
        self.assertEqual(duration, 30)

    def test_response_gap(self):
        self.d['monotonic'] = 4
        with self.assertRaises(ValueError): o.progress(self.d, P, 'charge', 0, 0)

    def test_detach_stops_observation(self):
        self.d['tcpm']['POWER_SUPPLY_ONLINE'] = '0'
        with self.assertRaises(ValueError): o.progress(self.d, P, 'charge', 0, None)

    def test_prior_stop_blocks_next_stage(self):
        raw = json.dumps(dict(kind='verdict', verdict='STOP', phase='charge'))
        with self.assertRaises(ValueError): h.accepted(raw, 1, 'charge')

    def test_missing_evidence(self):
        with self.assertRaises(ValueError): h.accepted(json.dumps(dict(kind='verdict', verdict='PASS', phase='charge')), 0, 'charge')

    def test_ssh_failure(self):
        with self.assertRaises(ValueError): h.accepted('', 255, 'charge')

    def test_wait_is_not_observation(self):
        self.d['tcpm']['POWER_SUPPLY_ONLINE'] = '0'
        self.d['monotonic'] = 180
        start, done, seconds = o.progress(self.d, P, 'charge', None, None)
        self.assertIsNone(start); self.assertFalse(done); self.assertEqual(seconds, 0)

    def test_discharge_continuity_15s(self):
        self.d['battery'].update(POWER_SUPPLY_STATUS='Discharging', POWER_SUPPLY_CURRENT_NOW='-1000000')
        self.d['usb']['POWER_SUPPLY_ONLINE'] = self.d['tcpm']['POWER_SUPPLY_ONLINE'] = '0'
        previous = start = None
        for t in range(16):
            self.d['monotonic'] = t
            start, done, seconds = o.progress(self.d, P, 'discharge', start, previous)
            self.assertEqual(done, t == 15)
            previous = t

    def journal(self, message='regulator: Not disabling unused regulators', priority=4):
        return json.dumps(dict(_BOOT_ID=P['boot_id'], __MONOTONIC_TIMESTAMP='1', PRIORITY=str(priority), MESSAGE=message))

    def test_known_warnings(self):
        for m in ('auxiliary aux_bridge: deferred probe pending: failed to acquire drm_bridge', 'regulator: Not disabling unused regulators', 'ramoops: attached 1 record'):
            self.assertEqual(len(o.inspect_journal(self.journal(m), P['boot_id'])), 1)

    def test_fault_signatures(self):
        for m in ('Kernel panic - not syncing', 'BUG: soft lockup', 'rcu: INFO: rcu_preempt detected stalls', 'CSD CPU non-responsive', 'Oops: failure', 'WARNING: CPU: unexpected trace'):
            with self.assertRaises(ValueError): o.inspect_journal(self.journal(m), P['boot_id'])

    def test_empty_journal(self):
        with self.assertRaises(ValueError): o.inspect_journal('', P['boot_id'])

    def test_mixed_journal(self):
        with self.assertRaises(ValueError): o.inspect_journal(self.journal().replace(P['boot_id'], '0' * 32), P['boot_id'])

    def test_new_error(self):
        with self.assertRaises(ValueError): o.inspect_journal(self.journal('i2c fault', 3), P['boot_id'])
        o.inspect_journal(self.journal('known startup', 3), P['boot_id'], {'known startup'})

    def test_scope_unchanged(self):
        self.assertFalse(P['PPS']); self.assertFalse(P['pump_ON']); self.assertFalse(P['flash']); self.assertFalse(P['reboot'])
        self.assertEqual(P['fixed9_input_max_ua'], 1500000)
        self.assertEqual(P['config_sha256'], '51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a')


if __name__ == '__main__': unittest.main()
