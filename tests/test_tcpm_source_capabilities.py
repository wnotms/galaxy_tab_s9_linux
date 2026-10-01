"""Current partner capability evidence, not PPS negotiation/activation."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import tcpm_source_capabilities as cap


def log(objects, count=None, attached=1):
    count = len(objects) if count is None else count
    lines = ['[ 10.000000] PD RX, header: ' + hex((count << 12) | 0x1a1) + f' [{attached}]']
    lines += [f'[ 10.000001] PDO {i}: type {kind}, {value}' for i, (kind, value) in enumerate(objects)]
    return '\n'.join(lines) + '\n'


FIXED = [(0, '5000 mV, 3000 mA [E]'), (0, '9000 mV, 3000 mA []'),
         (0, '20000 mV, 3250 mA []')]
PPS = FIXED + [(3, 'PPS 3300-11000 mV, 4500 mA')]
ATTRS = '''PD_PARTNER_LINK=/sys/devices/virtual/usb_power_delivery/pd1
PDO_PATH=/sys/devices/virtual/usb_power_delivery/pd1/source-capabilities/1:fixed_supply
voltage=5000mV
maximum_current=3000mA
PDO_PATH=/sys/devices/virtual/usb_power_delivery/pd1/source-capabilities/2:fixed_supply
voltage=9000mV
maximum_current=3000mA
PDO_PATH=/sys/devices/virtual/usb_power_delivery/pd1/source-capabilities/3:fixed_supply
voltage=20000mV
maximum_current=3250mA
'''


class SourceCapabilityTests(unittest.TestCase):
    def parse(self, raw, **kw):
        flags = dict(same_boot=True, owner_confirmed=True, fresh_log_boundary=True)
        flags.update(kw)
        parsed = cap.parse_source_capabilities(raw, **flags)
        self.assertFalse(parsed['PPS_request_authorized'])
        self.assertFalse(parsed['pump_ON_authorized'])
        return parsed

    def unknown(self, raw):
        self.assertEqual(self.parse(raw)['classification'], 'UNKNOWN')

    def test_complete_fixed_source_has_no_advertised_pps(self):
        p = self.parse(log(FIXED))
        self.assertEqual(p['classification'], 'NO_PPS_ADVERTISED')
        self.assertEqual(p['objects'][2]['voltage_mv'], 20000)

    def test_pps_source_preserves_position_voltage_and_current(self):
        p = self.parse(log(PPS))
        self.assertEqual(p['classification'], 'PPS_ADVERTISED')
        self.assertEqual(p['objects'][3]['position'], 4)
        self.assertEqual(p['objects'][3]['minimum_voltage_mv'], 3300)
        self.assertEqual(p['objects'][3]['maximum_voltage_mv'], 11000)
        self.assertEqual(p['objects'][3]['maximum_current_ma'], 4500)

    def test_no_false_negative_for_empty_or_missing_header(self):
        self.unknown('')
        self.unknown(log(FIXED).split('\n', 1)[1])

    def test_missing_object_is_unknown(self):
        self.unknown(log(FIXED, count=4))

    def test_duplicate_and_orphan_object_is_unknown(self):
        raw = log(FIXED)
        self.unknown(raw.replace('PDO 1:', 'PDO 0:'))
        self.unknown(raw + '[ 10.000002] PDO 3: type 0, 15000 mV, 3000 mA []\n')

    def test_overflow_is_unknown(self):
        self.unknown(log(FIXED) + '[ 10.000002] overflow\n')

    def test_all_attribution_gates_are_required(self):
        for name in ('same_boot', 'owner_confirmed', 'fresh_log_boundary'):
            self.assertEqual(self.parse(log(PPS), **{name: False})['classification'], 'UNKNOWN')
        self.assertEqual(cap.parse_source_capabilities(log(PPS))['classification'], 'UNKNOWN')

    def test_detached_source_frame_is_unknown(self):
        self.unknown(log(FIXED, attached=0))

    def test_repeated_identical_source_frames_retained(self):
        p = self.parse(log(PPS) * 2)
        self.assertEqual(p['classification'], 'PPS_ADVERTISED')
        self.assertEqual(len(p['source_frames']), 2)

    def test_changing_source_offer_is_unknown(self):
        self.unknown(log(FIXED) + log(PPS))

    def test_malformed_and_truncated_log_is_unknown(self):
        self.unknown(log(FIXED).replace('PDO 2:', 'PDO bad:'))
        self.unknown(log(FIXED) + 'truncated line')

    def test_extended_header_not_mistaken_for_source_caps(self):
        self.unknown(log(FIXED).replace('0x31a1', '0xb1a1'))

    def test_vsafe5_must_be_first(self):
        self.unknown(log([(0, '9000 mV, 3000 mA []')]))

    def test_fixed_voltage_and_type_order(self):
        self.unknown(log(FIXED[:2] + [FIXED[1]]))
        self.unknown(log(PPS + [FIXED[2]]))

    def test_unsupported_avs_or_epr_is_unknown(self):
        self.unknown(log(FIXED + [(3, 'EPR AVS 15000-48000 mV 140 W peak_current: 0')]))

    def test_pps_invalid_range_or_step_is_unknown(self):
        for value in ('PPS 11000-3300 mV, 3000 mA', 'PPS 3300-11001 mV, 3000 mA',
                      'PPS 3300-11000 mV, 3020 mA', 'PPS 3300-11000 mV, 0 mA'):
            self.unknown(log(FIXED + [(3, value)]))

    def test_variable_and_battery_are_not_called_fixed_only(self):
        for kind, unit in ((1, 'mW'), (2, 'mA')):
            p = self.parse(log(FIXED + [(kind, '5000-12000 mV, 3000 ' + unit)]))
            self.assertEqual(p['classification'], 'NO_PPS_ADVERTISED')
            self.assertNotEqual(p['objects'][-1]['kind'], 'fixed')

    def test_detach_or_reset_invalidates_old_source(self):
        for event in ('state change SNK_READY -> SNK_UNATTACHED',
                      'state change SNK_READY -> HARD_RESET_SEND', 'AMS SOFT_RESET finished'):
            self.unknown(log(PPS) + '[ 11.000000] ' + event + '\n')

    def test_negotiated_limit_is_distinct_from_advertised_voltage(self):
        p = self.parse(log(FIXED) + '[ 10.100000] Setting voltage/current limit 9000 mV 1500 mA\n')
        self.assertEqual(p['limits'][0]['voltage_mv'], 9000)
        self.assertEqual(p['objects'][-1]['voltage_mv'], 20000)

    def test_reported_rp_budget_does_not_imply_measured_draw(self):
        p = self.parse('[ 9.000000] Setting voltage/current limit 5000 mV 3000 mA\n' + log(FIXED))
        self.assertEqual(p['classification'], 'NO_PPS_ADVERTISED')
        self.assertEqual(p['limits'][0]['current_ma'], 3000)
        self.assertFalse(p['limits_are_measured_draw'])

    def test_partner_sysfs_corroborates_current_complete_source(self):
        self.assertEqual(len(cap.corroborate_partner(self.parse(log(FIXED)), ATTRS)), 3)

    def test_pps_partner_corroboration(self):
        attrs = ATTRS + '''PDO_PATH=/sys/devices/virtual/usb_power_delivery/pd1/source-capabilities/4:programmable_supply
minimum_voltage=3300mV
maximum_voltage=11000mV
maximum_current=4500mA
'''
        self.assertEqual(cap.corroborate_partner(self.parse(log(PPS)), attrs)[-1]['kind'], 'programmable_supply')

    def test_partner_wrong_values_or_missing_objects_fail(self):
        for attrs in (ATTRS.replace('9000mV', '5000mV'), ATTRS.split('PDO_PATH=')[0],
                      ATTRS.replace('/3:fixed_supply', '/4:fixed_supply')):
            with self.assertRaises(ValueError):
                cap.corroborate_partner(self.parse(log(FIXED)), attrs)

    def test_partner_missing_duplicate_or_foreign_symlink_fails(self):
        for attrs in (ATTRS.split('\n', 1)[1], ATTRS.split('\n')[0] + '\n' + ATTRS,
                      ATTRS.replace('PD_PARTNER_LINK=/sys/devices', 'PD_PARTNER_LINK=/sys/class')):
            with self.assertRaises(ValueError):
                cap.parse_partner_sysfs(attrs)

    def test_unknown_log_cannot_be_promoted_by_sysfs(self):
        with self.assertRaises(ValueError):
            cap.corroborate_partner(self.parse(''), ATTRS)


if __name__ == '__main__':
    unittest.main()
