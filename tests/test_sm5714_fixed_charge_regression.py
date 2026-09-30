"""Ordinary fixed charging keeps the passive pump OFF and PC separate."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sm5714_fixed_charge_regression as regression
from test_sm5714_pd_telemetry import sample


def monitored():
    value = sample()
    value.update(passive_health='Good', passive_status='Not charging',
                 passive_online=1, passive_vbus_uv=9000000, passive_ibus_ua=0,
                 passive_die_deciC=280, failed_units='')
    return value


class FixedChargeRegressionTests(unittest.TestCase):
    def capture(self):
        # Retained first live host failure: the separator consumed the newline
        # after @@failed before parsing. Replay the exact captured evidence.
        root = Path(__file__).resolve().parents[1]
        return (root / 'reference/boot-tests/test-262-sm5714-fixed-charge-on-test260'
                / 'charging/sample-000.txt').read_text().split('\n@@kernel\n', 1)[0]

    def test_captured_empty_failed_section_at_eof(self):
        value = regression.parse(self.capture())
        self.assertEqual(value['failed_units'], '')
        self.assertEqual(value['usb_type'], 'SDP')
        self.assertIsNone(regression.safety(value, value['boot_id']))
        self.assertFalse(regression.charger_ready(value))

    def test_empty_failed_section_with_newline(self):
        self.assertEqual(regression.parse(self.capture() + '\n')['failed_units'], '')

    def test_missing_failed_section_still_fails_closed(self):
        with self.assertRaises(KeyError):
            regression.parse(self.capture().removesuffix('@@failed'))

    def test_captured_failed_unit_still_stops(self):
        value = regression.parse(self.capture() + '\nbad.service failed\n')
        self.assertEqual(regression.safety(value, value['boot_id']), 'systemd-failed-unit')

    def test_fixed_9v_safe_and_ready(self):
        value = monitored()
        self.assertIsNone(regression.safety(value, value['boot_id']))
        self.assertTrue(regression.charger_ready(value))

    def test_pc_sdp_cannot_start_charging_window(self):
        value = monitored()
        value.update(usb_type='SDP', tcpm_type='C', contract_voltage_uv=5000000,
                     contract_current_ua=500000, input_current_limit_ua=500000,
                     passive_vbus_uv=4910000)
        self.assertIsNone(regression.safety(value, value['boot_id']))
        self.assertFalse(regression.charger_ready(value))

    def test_offline_transition_does_not_start_window(self):
        value = monitored()
        value.update(usb_online=0, tcpm_online=0, passive_online=0,
                     contract_voltage_uv=0, passive_vbus_uv=0)
        self.assertIsNone(regression.safety(value, value['boot_id']))
        self.assertFalse(regression.charger_ready(value))

    def test_stale_5v_adc_cannot_confirm_9v_contract(self):
        value = monitored(); value['passive_vbus_uv'] = 4900000
        self.assertFalse(regression.charger_ready(value))

    def test_reported_voltage_above_9_5v_stops(self):
        value = monitored(); value['passive_vbus_uv'] = 9500001
        self.assertEqual(regression.safety(value, value['boot_id']), 'reported-VBUS-outside-bringup-limit')

    def test_passive_current_nonzero_or_charging_stops(self):
        for field, content in [('passive_ibus_ua', 1), ('passive_status', 'Charging'), ('passive_health', 'Unknown')]:
            with self.subTest(field=field):
                value = monitored(); value[field] = content
                self.assertIsNotNone(regression.safety(value, value['boot_id']))

    def test_bringup_pack_42c_and_vbat_4_3v_stop(self):
        for field, content in [('battery_temp_deciC', 420), ('battery_voltage_uv', 4300000)]:
            value = monitored(); value[field] = content
            self.assertIsNotNone(regression.safety(value, value['boot_id']))

    def test_die_temperature_and_systemd_fault_stop(self):
        for field, content in [('passive_die_deciC', 420), ('failed_units', 'bad.service failed')]:
            value = monitored(); value[field] = content
            self.assertIsNotNone(regression.safety(value, value['boot_id']))

    def test_pps_and_contract_over_9v_still_rejected(self):
        for field, content in [('tcpm_type', 'PD_PPS'), ('contract_voltage_uv', 12000000)]:
            value = monitored(); value[field] = content
            self.assertIsNotNone(regression.safety(value, value['boot_id']))

    def test_contract_loss_after_start_stops(self):
        value = monitored(); value['usb_online'] = 0
        self.assertEqual(regression.safety(value, value['boot_id'], attached=True), 'charger-or-contract-lost')

    def test_battery_watts_never_claim_input_power(self):
        value = monitored()
        self.assertEqual(value['battery_net_power_w'], 6)
        self.assertEqual(value['configured_input_ceiling_w'], 13.5)
        self.assertIsNone(value['measured_input_power_w'])


if __name__ == '__main__':
    unittest.main()
